"""Innovation Dashboard: every raw idea, ranked by the active metric."""

import logging
import re

import gradio as gr
import psycopg

from auth import is_dashboard_user
from idea_store import RawIdea, list_raw_ideas
from score_ideas import Setup, load_setup, score_ideas
from score_store import Score, current_scores


def one_line(text: object) -> str:
    """Model and employee text kept on one line, so it cannot add headings."""
    return " ".join(str(text).split())


def format_score(score: Score | None) -> str:
    """The score with its reasons and flags, as Markdown."""
    if score is None:
        return "**Score:** pending"
    details = score.details
    value = "needs information" if score.value is None else f"{score.value}/100"
    act = details["ai_act"]
    review = " · **Review required**" if details["review_required"] else ""
    lines = [
        f"**Score:** {value} · **AI fit:** {details['ai_fit']['label']} · "
        f"**EU AI Act (preliminary):** {act['tier']}{review}",
        "",
        "<details><summary>Why</summary>",
        "",
        f"- {one_line(score.rationale)}",
    ]
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
    lines += ["- Preliminary screening, not legal advice.", "", "</details>"]
    return "\n".join(lines)


def format_idea(idea: RawIdea, score: Score | None) -> str:
    """One idea as Markdown: title, score, proposer, then the idea's own sections."""
    first_line, _, body = idea.text.partition("\n")
    if idea.author_name:
        author = f"{idea.author_name} ({idea.author_id}), {idea.department}"
    else:
        author = f"{idea.author_id} (not in the employee list)"
    # Move the idea's headings below the one used for its title.
    body = re.sub(r"^#", "###", body.strip(), flags=re.MULTILINE)
    updated = ""
    if idea.updated_at:
        updated = (
            f"  \n**Updated:** {idea.updated_at.astimezone():%Y-%m-%d %H:%M} "
            f"(version {idea.version})"
        )
    return (
        f"## {idea.id}: {first_line.removeprefix('# ')}\n"
        f"{format_score(score)}\n\n"
        f"**Proposed by:** {author}  \n"
        f"**Submitted:** {idea.created_at.astimezone():%Y-%m-%d %H:%M}"
        f"{updated}\n\n"
        f"{body}"
    )


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
        f"**Raw ideas: {len(ideas)}** · ranked by {setup.metric.name} version "
        f"{setup.metric.version} · pending: {pending}"
    )


def show_ideas(request: gr.Request) -> str:
    """All raw ideas, ranked. Empty for anyone but the dashboard user."""
    if not is_dashboard_user(request.username or ""):
        return ""
    try:
        setup = load_setup()
        ideas = list_raw_ideas()
        scores = current_scores(setup.metric.name, setup.metric.version, setup.sha)
    except (psycopg.Error, ValueError, OSError):
        logging.exception("Could not load the ideas")
        return "The ideas could not be loaded. Please try again in a moment."
    if not ideas:
        return "No ideas have been submitted yet."
    return "\n\n---\n\n".join(
        [
            overview(setup, ideas, scores),
            *(format_idea(idea, scores.get(idea.id)) for idea in rank(ideas, scores)),
        ]
    )


def score_pending(request: gr.Request) -> str:
    """Score every pending idea, then show the new ranking."""
    if not is_dashboard_user(request.username or ""):
        return ""
    try:
        _, failed = score_ideas()
    except (psycopg.Error, ValueError, OSError):
        logging.exception("Could not score the ideas")
        gr.Warning("The ideas could not be scored. Please try again in a moment.")
    else:
        if failed:
            gr.Warning(f"{failed} ideas could not be scored. The log says why.")
    return show_ideas(request)


def build(demo: gr.Blocks) -> None:
    """Add the dashboard to the page being built. It loads when the page opens."""
    gr.Markdown("# Innovation Dashboard")
    with gr.Row():
        refresh = gr.Button("Refresh", size="sm")
        score_button = gr.Button("Score pending ideas", size="sm")
    ideas = gr.Markdown()
    gr.on([demo.load, refresh.click], show_ideas, outputs=ideas)
    score_button.click(score_pending, outputs=ideas)
