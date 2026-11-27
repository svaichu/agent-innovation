"""Innovation Dashboard: every raw idea and who proposed it."""

import logging
import re

import gradio as gr
import psycopg

from auth import is_dashboard_user
from idea_store import RawIdea, list_raw_ideas


def format_idea(idea: RawIdea) -> str:
    """One idea as Markdown: title, proposer, then the idea's own sections."""
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
        f"**Proposed by:** {author}  \n"
        f"**Submitted:** {idea.created_at.astimezone():%Y-%m-%d %H:%M}"
        f"{updated}\n\n"
        f"{body}"
    )


def show_ideas(request: gr.Request) -> str:
    """All raw ideas, newest first. Empty for anyone but the dashboard user."""
    if not is_dashboard_user(request.username or ""):
        return ""
    try:
        ideas = list_raw_ideas()
    except psycopg.Error:
        logging.exception("Could not load the ideas")
        return "The ideas could not be loaded. Please try again in a moment."
    if not ideas:
        return "No ideas have been submitted yet."
    return "\n\n---\n\n".join(
        [f"**Raw ideas: {len(ideas)}**", *(format_idea(idea) for idea in ideas)]
    )


def build(demo: gr.Blocks) -> None:
    """Add the dashboard to the page being built. It loads when the page opens."""
    gr.Markdown("# Innovation Dashboard")
    refresh = gr.Button("Refresh", size="sm")
    ideas = gr.Markdown()
    gr.on([demo.load, refresh.click], show_ideas, outputs=ideas)
