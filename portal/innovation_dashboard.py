"""Innovation Dashboard: every raw idea, ranked by the active metric.

Ideas and their scores are loaded once per page load into State, then filtered in
memory.
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
from score_ideas import Setup, load_setup, score_ideas
from score_store import Score, current_scores

ALL = "All departments"
SORTS = ["Highest score", "Newest first", "Oldest first", "Department", "Author"]

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


def one_line(text: object) -> str:
    """Model and employee text kept on one line, so it cannot add headings."""
    return " ".join(str(text).split())


def badge(text: str, kind: str = "") -> str:
    return f"<span class='badge {kind}'>{text}</span>"


def score_badges(score: Score | None) -> str:
    """The score and flags at a glance."""
    if score is None:
        return badge("Score pending")
    details = score.details
    value = "Needs information" if score.value is None else f"Score {score.value}/100"
    badges = [
        badge(value, "" if score.value is None else "badge-score"),
        badge(f"AI fit: {details['ai_fit']['label']}"),
        badge(f"EU AI Act (preliminary): {details['ai_act']['tier']}"),
    ]
    if details["review_required"]:
        badges.append(badge("Review required", "badge-review"))
    return " ".join(badges)


def score_reasons(score: Score) -> str:
    """Why the idea got this score and these flags, as Markdown."""
    details = score.details
    act = details["ai_act"]
    lines = [f"- {one_line(score.rationale)}"]
    for name, item in details["inputs"].items():
        if item["value"] is not None:
            source = item["source"].replace("_", " ")
            lines.append(
                f"- **{name}** {item['value']:g} ({source}): {one_line(item['evidence'])}"
            )
            if item["source"] == "estimate":
                lines += [f"    - based on: {one_line(fact)}" for fact in item["basis"]]
    lines += [f"- Warning: {one_line(flag)}" for flag in details["flags"]]
    lines += [f"- Open: {one_line(question)}" for question in details["open_questions"]]
    lines.append(f"- AI fit, rule {details['ai_fit']['rule']}: {details['ai_fit']['reason']}")
    if act["citations"]:
        applies = f" ({act['applies']})" if act["applies"] else ""
        lines.append(f"- AI Act: {'; '.join(act['citations'])}{applies}")
    lines += [f"- Transparency duty: {duty}" for duty in act["transparency"]]
    lines += [f"- To check: {one_line(problem)}" for problem in act["problems"]]
    lines.append("- Preliminary screening, not legal advice.")
    return "\n".join(lines)


def rank(ideas: list[RawIdea], scores: dict[str, Score]) -> list[RawIdea]:
    """Highest score first, then ideas needing information, then pending ones.

    Ties keep the order given.
    """

    def key(idea: RawIdea) -> tuple[int, int]:
        if (score := scores.get(idea.id)) is None:
            return 2, 0
        if score.value is None:
            return 1, 0
        return 0, -score.value

    return sorted(ideas, key=key)


def overview(setup: Setup, ideas: list[RawIdea], scores: dict[str, Score]) -> str:
    pending = sum(idea.id not in scores for idea in ideas)
    return (
        f"Scored with {setup.metric.name} version {setup.metric.version}. "
        f"Pending: {pending}."
    )


def sort_ideas(
    ideas: list[RawIdea], how: str, scores: dict[str, Score]
) -> list[RawIdea]:
    if how == "Highest score":
        return rank(sort_ideas(ideas, "Newest first", scores), scores)
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
    """Load every idea and its score, for the dashboard user only.

    Returns (ideas, scores by idea ID, ranking note, stats, error).
    """
    if not is_dashboard_user(request.username or ""):
        # Not an error the visitor needs explaining: they are simply not the
        # dashboard user, and their own page is the one that is visible.
        return [], {}, "", empty_stats(), ""
    try:
        setup = load_setup()
        ideas = list_raw_ideas()
        scores = current_scores(setup.metric.name, setup.metric.version, setup.sha)
    except (psycopg.Error, ValueError, OSError):
        logging.exception("Could not load the ideas")
        return [], {}, "", empty_stats(), (
            "The ideas could not be loaded. Please try again in a moment.")
    return ideas, scores, overview(setup, ideas, scores), stats_for(ideas), ""


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


def score_pending(request: gr.Request) -> None:
    """Score every pending idea."""
    if not is_dashboard_user(request.username or ""):
        return
    try:
        _, failed = score_ideas()
    except (psycopg.Error, ValueError, OSError):
        logging.exception("Could not score the ideas")
        gr.Warning("The ideas could not be scored. Please try again in a moment.")
    else:
        if failed:
            gr.Warning(f"{failed} ideas could not be scored. The log says why.")


# --------------------------------------------------------------------------- #
# page
# --------------------------------------------------------------------------- #
def build(demo: gr.Blocks) -> None:
    """Add the dashboard to the page being built. It loads when the page opens."""
    ideas_state = gr.State([])
    scores_state = gr.State({})

    with gr.Row(elem_classes="page-head"):
        gr.Markdown("## Innovation Dashboard\nEvery idea employees have "
                    "submitted, highest score first. Search the text, filter "
                    "by department, or sort.")

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

    with gr.Row(equal_height=True):
        ranking = gr.Markdown(elem_id="ranking-note", scale=4)
        score_button = gr.Button("Score pending ideas", size="sm", scale=0,
                                 min_width=180)

    count = gr.Markdown(elem_id="result-count")

    @gr.render(inputs=[ideas_state, scores_state, query, department, order])
    def render_ideas(ideas, scores, text, dept, how):
        if not ideas:
            with gr.Column(elem_classes=["empty", "flat"]):
                gr.Markdown("No ideas have been submitted yet.\n\n"
                            "They appear here as soon as an employee presses "
                            "**Submit idea** in the chat.")
            return

        found = sort_ideas(
            [i for i in ideas if matches(i, text, dept)], how, scores
        )
        if not found:
            with gr.Column(elem_classes=["empty", "flat"]):
                gr.Markdown("Nothing matches those filters.\n\n"
                            "Try a different word, or set the department back "
                            f"to **{ALL}**.")
            return

        for idea in found:
            score = scores.get(idea.id)
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
                gr.Markdown(score_badges(score), elem_classes="idea-score")
                if score:
                    with gr.Accordion("Why this score", open=False):
                        gr.Markdown(score_reasons(score))
                with gr.Accordion("Read the idea", open=len(found) == 1):
                    gr.Markdown(idea_body(idea))

    def refresh_all(request: gr.Request):
        ideas, scores, note, stats, message = show_ideas(request)
        return [ideas, scores, note, department_choices(ideas), message, *stats]

    outputs = [ideas_state, scores_state, ranking, department, error, *tiles]
    gr.on([demo.load, refresh.click], refresh_all, outputs=outputs)
    score_button.click(score_pending).then(refresh_all, outputs=outputs)

    # The count line is cheap to recompute, so it follows every filter change.
    def update_count(ideas, text, dept):
        shown = sum(1 for i in ideas if matches(i, text, dept))
        return count_label(shown, len(ideas), text, dept)

    gr.on([ideas_state.change, query.change, department.change],
          update_count, inputs=[ideas_state, query, department], outputs=count)
