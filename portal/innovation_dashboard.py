"""Innovation Dashboard: raw ideas, and the refined ideas merged from them, in
tables with one score column for each active metric.

Ideas and their scores are loaded once per page load into State, then filtered in
memory.
Searching and filtering therefore does not go back to Postgres - there are tens
of ideas, not millions, and a round trip per keystroke would be slower and
noisier than a list comprehension.

Access is checked in show_ideas() on every call, not by hiding the page.
"""

import logging

import gradio as gr
import psycopg

from auth import is_dashboard_user
from dashboard_table import Column, raw_row, refined_row, table_html, tiles_html
from idea_store import RawIdea, list_raw_ideas
from merge_ideas import merge_ideas
from refined_store import RefinedIdea, list_refined_ideas
from score_ideas import Setup, load_setups, score_ideas
from score_store import Score, current_scores

ALL = "All departments"
# A ranking by a metric has the value "score:<metric name>".
BY_SCORE = "score:"
OTHER_SORTS = ["Newest first", "Oldest first", "Department", "Author"]


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


def rank(
    ideas: list[RawIdea] | list[RefinedIdea], scores: dict[str, Score]
) -> list:
    """Highest score first, then ideas needing information, then pending ones.

    Ties keep the order given.

    Args:
        scores: By idea ID, the scores of one metric.
    """

    def key(idea: RawIdea | RefinedIdea) -> tuple[int, int]:
        if (score := scores.get(idea.id)) is None:
            return 2, 0
        if score.value is None:
            return 1, 0
        return 0, -score.value

    return sorted(ideas, key=key)


def metric_scores(
    scores: dict[str, dict[str, Score]], name: str
) -> dict[str, Score]:
    """By idea ID, the scores of one metric."""
    return {idea_id: own[name] for idea_id, own in scores.items() if name in own}


def overview(
    setups: list[Setup],
    ideas: list[RawIdea | RefinedIdea],
    scores: dict[str, dict[str, Score]],
) -> str:
    metrics = ", ".join(f"{s.metric.label} v{s.metric.version}" for s in setups)
    pending = sum(len(scores.get(idea.id, {})) < len(setups) for idea in ideas)
    return f"Scored with {metrics}. Ideas awaiting a score: {pending}."


def sort_ideas(
    ideas: list[RawIdea], how: str, scores: dict[str, dict[str, Score]]
) -> list[RawIdea]:
    if how.startswith(BY_SCORE):
        return rank(
            sort_ideas(ideas, "Newest first", scores),
            metric_scores(scores, how.removeprefix(BY_SCORE)),
        )
    if how == "Oldest first":
        return sorted(ideas, key=lambda i: i.created_at)
    if how == "Department":
        return sorted(ideas, key=lambda i: ((i.department or "~"), i.created_at))
    if how == "Author":
        return sorted(ideas, key=lambda i: ((i.author_name or "~"), i.created_at))
    return sorted(ideas, key=lambda i: i.created_at, reverse=True)


def sort_refined(
    refined: list[RefinedIdea],
    how: str,
    scores: dict[str, dict[str, Score]],
    ideas: dict[str, RawIdea],
) -> list[RefinedIdea]:
    """The same choices as for raw ideas.

    By department or author, the first of the sources in the alphabet counts.
    """
    oldest = sorted(refined, key=lambda r: (r.saved_at, r.id))
    if how.startswith(BY_SCORE):
        return rank(oldest[::-1], metric_scores(scores, how.removeprefix(BY_SCORE)))
    if how == "Oldest first":
        return oldest
    if how in ("Department", "Author"):
        field = "department" if how == "Department" else "author_name"
        return sorted(oldest, key=lambda r: min(
            (getattr(ideas[i], field) or "~" for i in r.sources if i in ideas),
            default="~",
        ))
    return oldest[::-1]


def matches_refined(
    item: RefinedIdea, ideas: dict[str, RawIdea], query: str, department: str
) -> bool:
    """The filters apply to the refined text and to every source idea."""
    sources = [ideas[i] for i in item.sources if i in ideas]
    if department != ALL and all(s.department != department for s in sources):
        return False
    if not query.strip():
        return True
    needle = query.casefold()
    return needle in f"{item.id} {item.text}".casefold() or any(
        matches(source, query, ALL) for source in sources
    )


def merge_summary(created: int, updated: int) -> str:
    if not created and not updated:
        return "Nothing new to merge."
    return f"Refined ideas created: {created}, updated: {updated}."


# --------------------------------------------------------------------------- #
# loading
# --------------------------------------------------------------------------- #
def show_ideas(request: gr.Request):
    """Load every idea and its scores, for the dashboard user only.

    Returns (ideas, refined ideas, scores by idea ID and metric name, columns,
    ranking note, error).
    """
    nothing = [], [], {}, [], ""
    if not is_dashboard_user(request.username or ""):
        # Not an error the visitor needs explaining: they are simply not the
        # dashboard user, and their own page is the one that is visible.
        return *nothing, ""
    try:
        setups = load_setups()
        ideas = list_raw_ideas()
        refined = list_refined_ideas()
        scores: dict[str, dict[str, Score]] = {}
        for setup in setups:
            metric = setup.metric
            current = current_scores(metric.name, metric.version, setup.sha)
            for idea_id, score in current.items():
                scores.setdefault(idea_id, {})[metric.name] = score
    except (psycopg.Error, ValueError, OSError):
        logging.exception("Could not load the ideas")
        return *nothing, "The ideas could not be loaded. Please try again in a moment."
    columns = [Column(s.metric.name, s.metric.label) for s in setups]
    note = overview(setups, [*ideas, *refined], scores)
    return ideas, refined, scores, columns, note, ""


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


def merge_related(request: gr.Request) -> None:
    """Run the merge agent once."""
    if not is_dashboard_user(request.username or ""):
        return
    try:
        created, updated = merge_ideas()
    except Exception:
        # Also covers the model call. The page has to stay usable.
        logging.exception("Could not merge the ideas")
        gr.Warning("The ideas could not be merged. Please try again in a moment.")
    else:
        gr.Info(merge_summary(created, updated))


def score_and_report(refined_only: bool = False) -> None:
    """Score pending ideas, and warn about those that failed."""
    try:
        ids = [item.id for item in list_refined_ideas()] if refined_only else None
        _, failed = score_ideas(ids)
    except (psycopg.Error, ValueError, OSError):
        logging.exception("Could not score the ideas")
        gr.Warning("The ideas could not be scored. Please try again in a moment.")
    else:
        if failed:
            gr.Warning(f"{failed} ideas could not be scored. The log says why.")


def score_pending(request: gr.Request) -> None:
    """Score every pending idea, raw and refined."""
    if is_dashboard_user(request.username or ""):
        score_and_report()


def score_refined(request: gr.Request) -> None:
    """Score the refined ideas that have no current score."""
    if is_dashboard_user(request.username or ""):
        score_and_report(refined_only=True)


# --------------------------------------------------------------------------- #
# page
# --------------------------------------------------------------------------- #
def empty_note(message: str) -> None:
    with gr.Column(elem_classes=["empty", "flat"]):
        gr.Markdown(message)


NO_MATCH = ("Nothing matches those filters.\n\nTry a different word, or set the "
            f"department back to **{ALL}**.")


def build(demo: gr.Blocks) -> None:
    """Add the dashboard to the page being built. It loads when the page opens."""
    ideas_state = gr.State([])
    scores_state = gr.State({})
    refined_state = gr.State([])
    columns_state = gr.State([])
    # The sort choices are fixed when the page is built; restart after a change.
    sorts = [(f"Highest {s.metric.label}", BY_SCORE + s.metric.name)
             for s in load_setups()]

    with gr.Row(elem_classes="page-head"):
        gr.Markdown("## Innovation Dashboard\nSubmitted and refined ideas, scored "
                    "by each active metric. Search the text, filter by "
                    "department, or sort by any score.")

    tiles = gr.HTML(tiles_html([], [], {}, []))

    error = gr.Markdown()

    with gr.Row(elem_id="filters"):
        query = gr.Textbox(label="Search", placeholder="word, author, or idea ID",
                           scale=3, submit_btn=False)
        department = gr.Dropdown([ALL], value=ALL, label="Department", scale=2)
        order = gr.Dropdown(sorts + OTHER_SORTS, value=sorts[0][1],
                            label="Sort by", scale=2)
        refresh = gr.Button("Refresh", scale=1, min_width=90)

    with gr.Row(equal_height=True):
        ranking = gr.Markdown(elem_id="ranking-note", scale=4)
        score_button = gr.Button("Score pending ideas", size="sm", scale=0,
                                 min_width=180)
        merge_button = gr.Button("Merge related ideas", size="sm", scale=0,
                                 min_width=180, variant="primary")

    with gr.Tabs():
        with gr.Tab("Submitted ideas"):
            count = gr.Markdown(elem_id="result-count")
            submitted_tab = gr.Column()
        with gr.Tab("Refined ideas"):
            refined_tab = gr.Column()

    with submitted_tab:
        @gr.render(inputs=[ideas_state, scores_state, columns_state, query,
                           department, order])
        def render_ideas(ideas, scores, columns, text, dept, how):
            if not ideas:
                empty_note("No ideas have been submitted yet.\n\n"
                           "They appear here as soon as an employee presses "
                           "**Submit idea** in the chat.")
                return
            found = sort_ideas(
                [i for i in ideas if matches(i, text, dept)], how, scores
            )
            if not found:
                empty_note(NO_MATCH)
                return
            gr.HTML(table_html([raw_row(i) for i in found], scores, columns,
                               how.removeprefix(BY_SCORE)))

    with refined_tab:
        @gr.render(inputs=[refined_state, ideas_state, scores_state, columns_state,
                           query, department, order])
        def render_refined(refined, ideas, scores, columns, text, dept, how):
            if not refined:
                empty_note("No refined ideas yet.\n\n"
                           "Press **Merge related ideas** to combine ideas of "
                           "different employees.")
                return
            by_id = {i.id: i for i in ideas}
            found = sort_refined(
                [r for r in refined if matches_refined(r, by_id, text, dept)],
                how, scores, by_id,
            )
            if not found:
                empty_note(NO_MATCH)
                return
            gr.HTML(table_html([refined_row(r, by_id) for r in found], scores,
                               columns, how.removeprefix(BY_SCORE)))

    def refresh_all(request: gr.Request):
        ideas, refined, scores, columns, note, message = show_ideas(request)
        return [ideas, refined, scores, columns, note, department_choices(ideas),
                message, tiles_html(ideas, refined, scores, columns)]

    outputs = [ideas_state, refined_state, scores_state, columns_state, ranking,
               department, error, tiles]
    gr.on([demo.load, refresh.click], refresh_all, outputs=outputs)
    score_button.click(score_pending).then(refresh_all, outputs=outputs)
    # Merging and scoring take a while, so the button says which is running and
    # cannot be pressed twice. The refined ideas show up before their scores.
    merge_button.click(
        lambda: gr.update(value="Merging…", interactive=False), outputs=merge_button
    ).then(merge_related).then(refresh_all, outputs=outputs).then(
        lambda: gr.update(value="Scoring…"), outputs=merge_button
    ).then(score_refined).then(refresh_all, outputs=outputs).then(
        lambda: gr.update(value="Merge related ideas", interactive=True),
        outputs=merge_button,
    )

    # The count line is cheap to recompute, so it follows every filter change.
    def update_count(ideas, text, dept):
        shown = sum(1 for i in ideas if matches(i, text, dept))
        return count_label(shown, len(ideas), text, dept)

    gr.on([ideas_state.change, query.change, department.change],
          update_count, inputs=[ideas_state, query, department], outputs=count)
