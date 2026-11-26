"""Raw ideas, stored as app-generated data, apart from the company knowledge base."""

from datetime import datetime
from typing import Literal

from psycopg.rows import class_row
from pydantic import BaseModel

from db import connect


class IdeaDraft(BaseModel):
    """A process or workflow improvement idea, in the employee's own terms."""

    title: str
    scope: Literal["company process", "own workflow"]
    current_process: str
    problem: str
    proposed_improvement: str
    who_is_affected: str
    expected_benefit: str

    def missing_fields(self) -> list[str]:
        return [name for name, value in self if not value.strip()]


def to_markdown(draft: IdeaDraft) -> str:
    """The idea text. The employee sees exactly this before submitting."""
    title = " ".join(draft.title.split())
    sections = [
        ("Scope", draft.scope),
        ("Current process", draft.current_process),
        ("Problem", draft.problem),
        ("Proposed improvement", draft.proposed_improvement),
        ("Who is affected", draft.who_is_affected),
        ("Expected benefit", draft.expected_benefit),
    ]
    body = "\n\n".join(f"## {name}\n{text.strip()}" for name, text in sections)
    return f"# {title}\n\n{body}\n"


def save_raw_idea(draft: IdeaDraft, author_id: str) -> str:
    """Add the idea to app_generated.raw_idea and return its ID."""
    with connect() as connection:
        number = connection.execute(
            "SELECT nextval('app_generated.raw_idea_number')"
        ).fetchone()[0]
        idea_id = f"RI-{number:04d}"
        connection.execute(
            "INSERT INTO app_generated.raw_idea (id, author_id, text) VALUES (%s, %s, %s)",
            (idea_id, author_id, to_markdown(draft)),
        )
    return idea_id


class RawIdea(BaseModel):
    """A stored idea. The name and department are None if the author is unknown."""

    id: str
    text: str
    created_at: datetime
    author_id: str
    author_name: str | None
    department: str | None


def list_raw_ideas() -> list[RawIdea]:
    """Every raw idea with its author, newest first."""
    with connect() as connection:
        return (
            connection.cursor(row_factory=class_row(RawIdea))
            .execute(
                "SELECT idea.id, idea.text, idea.created_at, idea.author_id, "
                "employee.name AS author_name, employee.department "
                "FROM app_generated.raw_idea AS idea "
                "LEFT JOIN knowledge_base.employees AS employee "
                "ON employee.id = idea.author_id "
                "ORDER BY idea.created_at DESC, idea.id DESC"
            )
            .fetchall()
        )
