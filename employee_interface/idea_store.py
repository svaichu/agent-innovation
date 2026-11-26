"""Raw ideas, stored in the knowledge base but apart from the company content."""

import json
import re
from datetime import datetime
from itertools import count
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

KNOWLEDGE_BASE = Path(__file__).resolve().parent.parent / "knowledge-base"
RAW_IDEAS_DIR = KNOWLEDGE_BASE / "ideas" / "raw"
EMPLOYEES_CSV = KNOWLEDGE_BASE / "people" / "employees.csv"


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


def save_raw_idea(
    draft: IdeaDraft, author_id: str, directory: Path = RAW_IDEAS_DIR
) -> str:
    """Write the idea to a new file and return its ID. Never overwrites."""
    directory.mkdir(parents=True, exist_ok=True)
    created = datetime.now().astimezone()
    numbers = [
        int(match.group(1))
        for path in directory.iterdir()
        if (match := re.fullmatch(r"RI-(\d+)\.md", path.name))
    ]

    for number in count(max(numbers, default=0) + 1):
        idea_id = f"RI-{number:04d}"
        # JSON strings are valid YAML, so quotes in the title stay safe.
        front_matter = "\n".join(
            [
                "---",
                f"title: {json.dumps(' '.join(draft.title.split()), ensure_ascii=False)}",
                f"owner: {author_id}",
                "classification: internal",
                f"last_updated: {created.date().isoformat()}",
                "type: raw_idea",
                f"id: {idea_id}",
                f"author_id: {author_id}",
                f"created_at: {created.isoformat(timespec='seconds')}",
                "---",
            ]
        )
        try:
            with (directory / f"{idea_id}.md").open("x", encoding="utf-8") as file:
                file.write(f"{front_matter}\n\n{to_markdown(draft)}")
        except FileExistsError:
            continue  # another submission took this number
        return idea_id
