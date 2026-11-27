"""Innovation Dashboard: every raw idea as an expandable table.

The list is loaded once per page load into a State and then filtered in memory.
Searching and filtering therefore does not go back to Postgres - there are tens
of ideas, not millions, and a round trip per keystroke would be slower and
noisier than a list comprehension.

The table is a single gr.HTML rather than one Gradio component per idea. A
hundred ideas is a hundred rows of markup either way, but only one component to
build, diff and send - and rows expand with native <details>, so opening one
costs no round trip at all.

Access is checked in show_ideas() on every call, not by hiding the page.
"""

import html
import logging
import re
from datetime import datetime

import gradio as gr
import psycopg

from auth import is_dashboard_user
from idea_store import RawIdea, list_raw_ideas

ALL = "All departments"
SORTS = ["Newest first", "Oldest first", "Department", "Author"]


# --------------------------------------------------------------------------- #
# reading an idea
# --------------------------------------------------------------------------- #
def idea_title(idea: RawIdea) -> str:
    """The first line of the idea, without its leading '# '."""
    first_line, _, _ = idea.text.partition("\n")
    return first_line.removeprefix("# ").strip() or idea.id


def idea_sections(idea: RawIdea) -> list[tuple[str, str]]:
    """The idea's '## Heading' blocks as (heading, text) pairs.

    idea_store.to_markdown() writes exactly this shape, so parsing it is
    predictable. Anything that does not match is kept as an unlabelled block
    rather than dropped.
    """
    _, _, body = idea.text.partition("\n")
    pairs: list[tuple[str, str]] = []
    for block in re.split(r"\n(?=## )", body.strip()):
        block = block.strip()
        if not block:
            continue
        if block.startswith("## "):
            heading, _, text = block.partition("\n")
            pairs.append((heading[3:].strip(), text.strip()))
        else:
            pairs.append(("", block))
    return pairs


def author_name(idea: RawIdea) -> str:
    return idea.author_name or idea.author_id


def matches(idea: RawIdea, query: str | None, department: str | None) -> bool:
    query, department = query or "", department or ALL
    if department != ALL and (idea.department or "") != department:
        return False
    if not query.strip():
        return True
    needle = query.casefold()
    haystack = " ".join([
        idea.id, idea.text, idea.author_name or "", idea.department or "",
    ]).casefold()
    return needle in haystack


def sort_ideas(ideas: list[RawIdea], how: str | None) -> list[RawIdea]:
    if how == "Oldest first":
        return sorted(ideas, key=lambda i: i.created_at)
    if how == "Department":
        return sorted(ideas, key=lambda i: ((i.department or "~"), i.created_at))
    if how == "Author":
        return sorted(ideas, key=lambda i: ((i.author_name or "~"), i.created_at))
    return sorted(ideas, key=lambda i: i.created_at, reverse=True)


# --------------------------------------------------------------------------- #
# the table
# --------------------------------------------------------------------------- #
HEADER = """
<div class="it-head">
  <span>Idea</span><span>Title</span><span>Submitted by</span>
  <span>Department</span><span>Date</span>
</div>"""


def empty_block(title: str, detail: str) -> str:
    return (f'<div class="it-empty"><p class="t">{html.escape(title)}</p>'
            f'<p>{detail}</p></div>')


def row_html(idea: RawIdea, expand: bool) -> str:
    """One <details> row: a single line that opens into the full idea."""
    revised = ""
    if idea.version > 1 and idea.updated_at:
        revised = f'<span class="it-rev">v{idea.version}</span>'
    body = "".join(
        f'<div class="it-field"><dt>{html.escape(heading)}</dt>'
        f'<dd>{html.escape(text)}</dd></div>'
        if heading else
        f'<div class="it-field"><dd>{html.escape(text)}</dd></div>'
        for heading, text in idea_sections(idea)
    )
    stamp = f"{idea.created_at.astimezone():%d %b %Y}"
    full_stamp = f"Submitted {idea.created_at.astimezone():%d %b %Y at %H:%M}"
    if idea.updated_at and idea.version > 1:
        full_stamp += (f" · last updated "
                       f"{idea.updated_at.astimezone():%d %b %Y at %H:%M}")
    dept = idea.department or "—"
    return f"""
<details class="it-row"{" open" if expand else ""}>
  <summary>
    <span class="it-id">{html.escape(idea.id)}</span>
    <span class="it-title">{html.escape(idea_title(idea))}{revised}</span>
    <span class="it-author">{html.escape(author_name(idea))}</span>
    <span class="it-dept">{html.escape(dept)}</span>
    <span class="it-date">{html.escape(stamp)}</span>
  </summary>
  <div class="it-body">
    <dl>{body}</dl>
    <p class="it-stamp">{html.escape(full_stamp)} · {html.escape(idea.author_id)}</p>
  </div>
</details>"""


def table_html(ideas: list[RawIdea], query: str | None, department: str | None,
               how: str | None, expand: bool | None) -> str:
    """The whole table, including its own count line and empty states.

    Every argument is normalised first. On the very first page load Gradio
    calls this before the filter components hold a value, so it arrives as
    None - which used to raise and paint the whole dashboard with "Error"
    until the visitor pressed Refresh.
    """
    query = query or ""
    department = department or ALL
    how = how or SORTS[0]
    expand = bool(expand)

    if not ideas:
        return empty_block(
            "No ideas have been submitted yet.",
            "They appear here as soon as an employee presses "
            "<strong>Submit idea</strong> in the chat.")

    found = sort_ideas([i for i in ideas if matches(i, query, department)], how)
    if not found:
        return empty_block(
            "Nothing matches those filters.",
            f"Try a different word, or set the department back to "
            f"<strong>{html.escape(ALL)}</strong>.")

    if len(found) == len(ideas):
        count = f"Showing all {len(ideas)} ideas."
    else:
        narrowed = []
        if query.strip():
            narrowed.append(f'matching &ldquo;{html.escape(query.strip())}&rdquo;')
        if department != ALL:
            narrowed.append(f"in {html.escape(department)}")
        count = f"Showing {len(found)} of {len(ideas)} ideas {' '.join(narrowed)}."

    rows = "".join(row_html(idea, expand) for idea in found)
    return (f'<p class="it-count">{count}</p>'
            f'<div class="idea-table">{HEADER}{rows}</div>')


# --------------------------------------------------------------------------- #
# loading
# --------------------------------------------------------------------------- #
def show_ideas(request: gr.Request):
    """Load every idea for the dashboard user. Returns (ideas, stats, error)."""
    if not is_dashboard_user(request.username or ""):
        # Not an error the visitor needs explaining: they are simply not the
        # dashboard user, and their own page is the one that is visible.
        return [], empty_stats(), ""
    try:
        ideas = list_raw_ideas()
    except psycopg.Error:
        logging.exception("Could not load the ideas")
        return [], empty_stats(), (
            "The ideas could not be loaded. Please try again in a moment.")
    return ideas, stats_for(ideas), ""


def tile(number: str, caption: str) -> str:
    return f"<span class='num'>{number}</span><span class='cap'>{caption}</span>"


def empty_stats() -> list[str]:
    return [tile("0", "ideas"), tile("0", "contributors"),
            tile("0", "departments"), tile("—", "latest")]


def stats_for(ideas: list[RawIdea]) -> list[str]:
    if not ideas:
        return empty_stats()
    latest = max(i.updated_at or i.created_at for i in ideas)
    days = (datetime.now(latest.tzinfo) - latest).days
    when = "today" if days == 0 else ("yesterday" if days == 1 else f"{days}d ago")
    return [
        tile(str(len(ideas)), "ideas"),
        tile(str(len({i.author_id for i in ideas})), "contributors"),
        tile(str(len({i.department for i in ideas if i.department})), "departments"),
        tile(when, "latest submission"),
    ]


def department_choices(ideas: list[RawIdea]) -> gr.Dropdown:
    found = sorted({i.department for i in ideas if i.department})
    return gr.Dropdown(choices=[ALL, *found], value=ALL)


# --------------------------------------------------------------------------- #
# page
# --------------------------------------------------------------------------- #
def build(demo: gr.Blocks) -> None:
    """Add the dashboard to the page being built. It loads when the page opens."""
    ideas_state = gr.State([])

    with gr.Row(elem_classes="page-head"):
        gr.Markdown("## Innovation Dashboard\nEvery idea employees have "
                    "submitted. Search the text, filter by department or sort, "
                    "then open a row to read it in full.")

    with gr.Row(elem_id="stats", equal_height=True):
        tiles = [gr.Markdown(t, elem_classes=["stat", "flat"])
                 for t in empty_stats()]

    error = gr.Markdown()

    with gr.Row(elem_id="filters"):
        query = gr.Textbox(value="", label="Search",
                           placeholder="word, author, or idea ID",
                           scale=3, submit_btn=False)
        department = gr.Dropdown([ALL], value=ALL, label="Department", scale=2)
        order = gr.Dropdown(SORTS, value=SORTS[0], label="Sort by", scale=2)
        expand = gr.Checkbox(label="Open all rows", value=False, scale=1,
                             min_width=120)
        refresh = gr.Button("Refresh", scale=1, min_width=90)

    table = gr.HTML(elem_id="idea-table-wrap")

    controls = [ideas_state, query, department, order, expand]

    def redraw(ideas, text, dept, how, open_all):
        return table_html(ideas, text, dept, how, open_all)

    def refresh_all(text, dept, how, open_all, request: gr.Request):
        ideas, stats, message = show_ideas(request)
        return [ideas, department_choices(ideas), message,
                table_html(ideas, text, dept, how, open_all), *stats]

    gr.on(
        [demo.load, refresh.click], refresh_all,
        inputs=[query, department, order, expand],
        outputs=[ideas_state, department, error, table, *tiles],
    )
    gr.on(
        [query.change, department.change, order.change, expand.change],
        redraw, inputs=controls, outputs=table,
    )
