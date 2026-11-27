"""Refined ideas, stored as app-generated data. Each version is its own row."""

from datetime import datetime

from psycopg.rows import class_row
from psycopg.types.json import Jsonb
from pydantic import BaseModel

from db import connect


class RefinedIdea(BaseModel):
    """One idea combined from two or more raw ideas."""

    # None until a new refined idea is stored.
    id: str | None
    version: int
    text: str
    # By raw idea ID, the version of it that the text was written from.
    sources: dict[str, int]
    # Why these ideas belong together.
    rationale: str
    # Contradictions and open points between the sources.
    differences: list[str]
    saved_at: datetime | None = None


def save_refined_ideas(ideas: list[RefinedIdea]) -> None:
    """Store new refined ideas and new versions, all of them or none."""
    with connect() as connection:
        for idea in ideas:
            idea_id = idea.id
            if idea_id is None:
                number = connection.execute(
                    "SELECT nextval('app_generated.refined_idea_number')"
                ).fetchone()[0]
                idea_id = f"RF-{number:04d}"
            # The primary key rejects a version that was saved in the meantime.
            connection.execute(
                "INSERT INTO app_generated.refined_idea "
                "(id, version, text, sources, rationale, differences) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                (
                    idea_id,
                    idea.version,
                    idea.text,
                    Jsonb(idea.sources),
                    idea.rationale,
                    Jsonb(idea.differences),
                ),
            )


def list_refined_ideas() -> list[RefinedIdea]:
    """The latest version of every refined idea, most recently saved first."""
    with connect() as connection:
        ideas = (
            connection.cursor(row_factory=class_row(RefinedIdea))
            .execute(
                "SELECT DISTINCT ON (id) id, version, text, sources, rationale, "
                "differences, saved_at FROM app_generated.refined_idea "
                "ORDER BY id, version DESC"
            )
            .fetchall()
        )
    return sorted(ideas, key=lambda i: (i.saved_at, i.id), reverse=True)
