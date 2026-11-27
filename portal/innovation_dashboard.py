"""Innovation Dashboard: every raw idea, who proposed it, and a way to find one.

The list is loaded once per page load into a State and then filtered in memory.
Searching and filtering therefore does not go back to Postgres - there are tens
of ideas, not millions, and a round trip per keystroke would be slower and
noisier than a list comprehension.

Access is checked in show_ideas() on every call, not by hiding the page.
"""

import logging
import re
from datetime import datetime

import gradio as gr
import psycopg

from auth import is_dashboard_user
from idea_store import RawIdea, list_raw_ideas

ALL = "All departments"
SORTS = ["Newest first", "Oldest first", "Department", "Author"]

# The headings the intake agent writes into every idea.
SECTION = re.compile(r"^#+\s*", re.MULTILINE)


def idea_title(idea: RawIdea) -> str:
    """The first line of the idea, without its leading '# '."""
    first_line, _, _ = idea.text.partition("\n")
    return first_line.removeprefix("# ").strip() or idea.id


def idea_body(idea: RawIdea) -> str:
    """The idea's own sections, pushed below the card's own heading level."""
    _, _, body = idea.text.partition("\n")
    return re.sub(r"^#+", "####", body.strip(), flags=re.MULTILINE)


def author_line(idea: RawIdea) -> str:
    if not idea.author_name:
        return f"{idea.author_id} · not in the employee list"
    return f"{idea.author_name} · {idea.author_id} · {idea.department}"


def matches(idea: RawIdea, query: str, department: str) -> bool:
    if department != ALL and (idea.department or "") != department:
        return False
    if not query.strip():
        return True
    needle = query.casefold()
    haystack = " ".join([
        idea.id, idea.text, idea.author_name or "", idea.department or "",
    ]).casefold()
    return needle in haystack


def sort_ideas(ideas: list[RawIdea], how: str) -> list[RawIdea]:
    if how == "Oldest first":
        return sorted(ideas, key=lambda i: i.created_at)
    if how == "Department":
        return sorted(ideas, key=lambda i: ((i.department or "~"), i.created_at))
    if how == "Author":
        return sorted(ideas, key=lambda i: ((i.author_name or "~"), i.created_at))
    return sorted(ideas, key=lambda i: i.created_at, reverse=True)


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


def empty_stats() -> list[str]:
    return [tile("0", "ideas"), tile("0", "contributors"),
            tile("0", "departments"), tile("—", "latest")]


def tile(number: str, caption: str) -> str:
    return f"<span class='num'>{number}</span><span class='cap'>{caption}</span>"


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


def count_label(shown: int, total: int, query: str, department: str) -> str:
    if total == 0:
        return ""
    if shown == total:
        return f"Showing all {total} ideas."
    narrowed = []
    if query.strip():
        narrowed.append(f'matching "{query.strip()}"')
    if department != ALL:
        narrowed.append(f"in {department}")
    return f"Showing {shown} of {total} ideas {' '.join(narrowed)}."


# --------------------------------------------------------------------------- #
# page
# --------------------------------------------------------------------------- #
def build(demo: gr.Blocks) -> None:
    """Add the dashboard to the page being built. It loads when the page opens."""
    ideas_state = gr.State([])

    with gr.Row(elem_classes="page-head"):
        gr.Markdown("## Innovation Dashboard\nEvery idea employees have "
                    "submitted, newest first. Search the text, filter by "
                    "department, or sort.")

    with gr.Row(elem_id="stats", equal_height=True):
        tiles = [gr.Markdown(t, elem_classes=["stat", "flat"])
                 for t in empty_stats()]

    error = gr.Markdown()

    with gr.Row(elem_id="filters"):
        query = gr.Textbox(label="Search", placeholder="word, author, or idea ID",
                           scale=3, submit_btn=False)
        department = gr.Dropdown([ALL], value=ALL, label="Department", scale=2)
        order = gr.Dropdown(SORTS, value=SORTS[0], label="Sort by", scale=2)
        refresh = gr.Button("Refresh", scale=1, min_width=90)

    count = gr.Markdown(elem_id="result-count")

    @gr.render(inputs=[ideas_state, query, department, order])
    def render_ideas(ideas, text, dept, how):
        if not ideas:
            with gr.Column(elem_classes=["empty", "flat"]):
                gr.Markdown("No ideas have been submitted yet.\n\n"
                            "They appear here as soon as an employee presses "
                            "**Submit idea** in the chat.")
            return

        found = sort_ideas([i for i in ideas if matches(i, text, dept)], how)
        if not found:
            with gr.Column(elem_classes=["empty", "flat"]):
                gr.Markdown("Nothing matches those filters.\n\n"
                            "Try a different word, or set the department back "
                            f"to **{ALL}**.")
            return

        for idea in found:
            with gr.Group(elem_classes=["idea-card", "flat"]):
                revision = ""
                if idea.version > 1 and idea.updated_at:
                    revision = (f"<span class='badge badge-rev'>v{idea.version}"
                                f"</span>")
                gr.Markdown(
                    f"<span class='badge badge-id'>{idea.id}</span>{revision}\n\n"
                    f"### {idea_title(idea)}")
                stamp = f"{idea.created_at.astimezone():%d %b %Y, %H:%M}"
                if idea.updated_at and idea.version > 1:
                    stamp += (f" · updated "
                              f"{idea.updated_at.astimezone():%d %b %Y, %H:%M}")
                gr.Markdown(f"{author_line(idea)}  \n{stamp}",
                            elem_classes="idea-meta")
                with gr.Accordion("Read the idea", open=len(found) == 1):
                    gr.Markdown(idea_body(idea))

    def refresh_all(request: gr.Request):
        ideas, stats, message = show_ideas(request)
        return [ideas, department_choices(ideas), message, *stats]

    outputs = [ideas_state, department, error, *tiles]
    gr.on([demo.load, refresh.click], refresh_all, outputs=outputs)

    # The count line is cheap to recompute, so it follows every filter change.
    def update_count(ideas, text, dept):
        shown = sum(1 for i in ideas if matches(i, text, dept))
        return count_label(shown, len(ideas), text, dept)

    gr.on([ideas_state.change, query.change, department.change],
          update_count, inputs=[ideas_state, query, department], outputs=count)
