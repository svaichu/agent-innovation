"""Merge related ideas of different employees into refined ideas.

Runs from the "Merge related ideas" button of the dashboard. The agent proposes,
and the rules here decide what is stored. Raw ideas are only read.
"""

import asyncio
import logging
import re
from pathlib import Path

import yaml

from db import connect
from idea_store import RawIdea, list_raw_ideas, to_markdown
from knowledge import load_knowledge, remove_names
from merge_agent import MergeContext, MergeProposal, propose_merges
from refined_store import RefinedIdea, list_refined_ideas, save_refined_ideas

PORTAL_DIR = Path(__file__).resolve().parent
MAX_IDEA_CHARS = 20_000
# "From multiple users": one person's ideas alone are never merged.
MIN_AUTHORS = 2


def build_prompt(
    ideas: list[RawIdea], refined: list[RefinedIdea], employees: dict[str, str]
) -> str:
    """All ideas as tagged text, without names or anything else about the authors."""

    def inside(text: str) -> str:
        # No idea can open or close a tag.
        text = re.sub(r"</?(idea|refined)\b[^>]*>", "", text, flags=re.IGNORECASE)
        return remove_names(text, employees)[:MAX_IDEA_CHARS]

    versions = {idea.id: idea.version for idea in ideas}
    labels: dict[str, str] = {}
    parts = []
    for idea in sorted(ideas, key=lambda i: i.id):
        label = labels.setdefault(idea.author_id, f"A{len(labels) + 1}")
        parts.append(
            f'<idea id="{idea.id}" author="{label}">\n{inside(idea.text)}\n</idea>'
        )
    for item in sorted(refined, key=lambda r: r.id):
        changed = [i for i, v in sorted(item.sources.items()) if versions.get(i) != v]
        note = f' changed="{", ".join(changed)}"' if changed else ""
        parts.append(
            f'<refined id="{item.id}" sources="{", ".join(sorted(item.sources))}"'
            f"{note}>\n{inside(item.text)}\n</refined>"
        )
    return "\n\n".join(parts)


def accept(
    proposals: list[MergeProposal],
    ideas: list[RawIdea],
    refined: list[RefinedIdea],
) -> list[RefinedIdea]:
    """The refined ideas to store: new ones, and new versions of existing ones.

    A proposal is dropped if it names unknown ideas, has an empty field, has
    fewer than two authors, repeats an existing group or changes no source.
    """
    raw = {idea.id: idea for idea in ideas}
    existing = {item.id: item for item in refined}
    groups = {item.id: set(item.sources) for item in refined}
    accepted: list[RefinedIdea] = []
    revised: set[str] = set()

    for number, proposal in enumerate(proposals):

        def drop(reason: str) -> None:
            logging.warning("Merge proposal %d not stored: %s", number + 1, reason)

        revises = (proposal.revises or "").strip().upper() or None
        ids = {idea_id.strip().upper() for idea_id in proposal.source_ids}
        if unknown := ids - set(raw):
            drop(f"unknown ideas {sorted(unknown)}")
            continue
        old = None
        if revises:
            if revises not in existing or revises in revised:
                drop(f"cannot revise {revises}")
                continue
            old = existing[revises]
            # A source is never taken away, so every merge stays traceable.
            ids |= set(old.sources)
        if len({raw[idea_id].author_id for idea_id in ids}) < MIN_AUTHORS:
            drop("the ideas do not come from different authors")
            continue
        if missing := proposal.draft.missing_fields():
            drop(f"empty fields {missing}")
            continue
        sources = {idea_id: raw[idea_id].version for idea_id in sorted(ids)}
        if old and sources == old.sources:
            drop(f"no source of {revises} is new or changed")
            continue
        if (not old or ids != set(old.sources)) and any(
            ids <= group for key, group in groups.items() if key != revises
        ):
            drop("these ideas are already merged")
            continue

        if revises:
            revised.add(revises)
        groups[revises or f"new {number}"] = ids
        accepted.append(
            RefinedIdea(
                id=revises,
                version=old.version + 1 if old else 1,
                text=to_markdown(proposal.draft),
                sources=sources,
                rationale=proposal.rationale,
                differences=proposal.differences,
            )
        )
    return accepted


def merge_ideas() -> tuple[int, int]:
    """Run the merge agent once. How many refined ideas were created and updated."""
    ideas = list_raw_ideas()
    if len({idea.author_id for idea in ideas}) < MIN_AUTHORS:
        return 0, 0
    refined = list_refined_ideas()
    config = yaml.safe_load((PORTAL_DIR / "config.yaml").read_text(encoding="utf-8"))
    with connect() as connection:
        documents, employees = load_knowledge(connection)
    proposals = asyncio.run(
        propose_merges(
            build_prompt(ideas, refined, employees),
            MergeContext(documents),
            config["models"]["merge_agent"],
        )
    )
    changes = accept(proposals, ideas, refined)
    save_refined_ideas(changes)
    created = sum(change.id is None for change in changes)
    return created, len(changes) - created
