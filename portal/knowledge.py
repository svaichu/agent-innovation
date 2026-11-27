"""What the score agent may read from the knowledge base, with people's names removed.

Only documents classified public or internal are readable. Anything else,
including a document without a classification, stays hidden.
"""

import re

import psycopg

OPEN_CLASSIFICATIONS = {"public", "internal"}
# About people as persons, so hidden whatever their classification.
HIDDEN = ("people/", "company/org-chart")


def classification(content: str) -> str | None:
    """The classification in a document's front matter."""
    parts = content.split("---", 2)
    if len(parts) != 3 or parts[0].strip():
        return None
    match = re.search(r"^classification:\s*(\S+)", parts[1], re.M)
    return match.group(1) if match else None


def remove_names(text: str, employees: dict[str, str]) -> str:
    """Replace employee names with IDs or "[name]", and email addresses.

    Args:
        employees: Full names by employee ID.
    """
    text = re.sub(r"[\w.+-]+@[\w-]+(\.[\w-]+)+", "[email]", text)
    # All full names first, so a shared first or last name does not split one.
    for employee_id, name in employees.items():
        text = text.replace(f"{name} ({employee_id})", employee_id)
        text = text.replace(name, employee_id)
    parts = {part for name in employees.values() for part in name.split() if len(part) > 2}
    for part in parts:
        text = re.sub(rf"\b{re.escape(part)}\b", "[name]", text)
    return text


def readable_documents(
    documents: dict[str, str], employees: dict[str, str]
) -> dict[str, str]:
    """The documents the agent may read, by path, without names.

    A CSV file has no front matter, so it takes the classification of the
    Markdown file with the same name.
    """
    readable = {}
    for path, content in documents.items():
        page = documents.get(re.sub(r"\.csv$", ".md", path), "")
        if not path.startswith(HIDDEN) and classification(page) in OPEN_CLASSIFICATIONS:
            readable[path] = remove_names(content, employees)
    return readable


def load_knowledge(connection: psycopg.Connection) -> tuple[dict[str, str], dict[str, str]]:
    """The readable documents, and the employee names by ID."""
    employees = dict(connection.execute("SELECT id, name FROM knowledge_base.employees"))
    documents = dict(connection.execute("SELECT path, content FROM knowledge_base.documents"))
    return readable_documents(documents, employees), employees
