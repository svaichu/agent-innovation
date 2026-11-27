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


def update_raw_idea(idea_id: str, draft: IdeaDraft, author_id: str) -> bool:
    """Replace the author's idea, keeping the earlier text in raw_idea_history.

    False if the author has no idea with this ID.
    """
    text = to_markdown(draft)
    with connect() as connection:
        # Locked until commit, so two updates cannot save the same version.
        row = connection.execute(
            "SELECT text FROM app_generated.raw_idea "
            "WHERE id = %s AND author_id = %s FOR UPDATE",
            (idea_id, author_id),
        ).fetchone()
        if row is None:
            return False
        if row[0] != text:
            connection.execute(
                "INSERT INTO app_generated.raw_idea_history "
                "(idea_id, version, text, saved_at) "
                "SELECT id, version, text, COALESCE(updated_at, created_at) "
                "FROM app_generated.raw_idea WHERE id = %s",
                (idea_id,),
            )
            connection.execute(
                "UPDATE app_generated.raw_idea "
                "SET text = %s, version = version + 1, updated_at = now() "
                "WHERE id = %s",
                (text, idea_id),
            )
    return True


def raw_idea_texts(versions: dict[str, int]) -> dict[str, str]:
    """By ID, the text each idea had at the given version."""
    texts = {}
    with connect() as connection:
        for idea_id, version in sorted(versions.items()):
            row = connection.execute(
                "SELECT text FROM app_generated.raw_idea "
                "WHERE id = %(id)s AND version = %(version)s "
                "UNION ALL SELECT text FROM app_generated.raw_idea_history "
                "WHERE idea_id = %(id)s AND version = %(version)s",
                {"id": idea_id, "version": version},
            ).fetchone()
            if row is None:
                raise ValueError(f"{idea_id} has no version {version}")
            texts[idea_id] = row[0]
    return texts


class RawIdea(BaseModel):
    """A stored idea. The name and department are None if the author is unknown."""

    id: str
    text: str
    created_at: datetime
    version: int
    updated_at: datetime | None
    author_id: str
    author_name: str | None
    department: str | None


def list_raw_ideas(author_id: str | None = None) -> list[RawIdea]:
    """Raw ideas with their authors, newest first. All of them, or one author's."""
    with connect() as connection:
        return (
            connection.cursor(row_factory=class_row(RawIdea))
            .execute(
                "SELECT idea.id, idea.text, idea.created_at, idea.version, "
                "idea.updated_at, idea.author_id, "
                "employee.name AS author_name, employee.department "
                "FROM app_generated.raw_idea AS idea "
                "LEFT JOIN knowledge_base.employees AS employee "
                "ON employee.id = idea.author_id "
                "WHERE %(author)s::text IS NULL OR idea.author_id = %(author)s "
                "ORDER BY idea.created_at DESC, idea.id DESC",
                {"author": author_id},
            )
            .fetchall()
        )
