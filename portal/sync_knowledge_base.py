"""Copy the local knowledge base to Postgres. One way: local files win.

    .venv/bin/python portal/sync_knowledge_base.py --dry-run
    .venv/bin/python portal/sync_knowledge_base.py

Documents removed locally are removed from the database, and the employee table
is replaced by people/employees.csv. Only the knowledge_base schema is written;
app-generated data is never read or changed.
"""

import argparse
import csv
from pathlib import Path

import psycopg

from db import connect, create_tables

KNOWLEDGE_BASE = Path(__file__).resolve().parent.parent / "knowledge-base"
EMPLOYEES_FILE = "people/employees.csv"
EMPLOYEE_COLUMNS = [
    "id",
    "name",
    "email",
    "role",
    "department",
    "manager_id",
    "work_mode",
    "start_date",
    "skills",
    "responsibilities",
    "deputy_id",
]


def read_documents(directory: Path) -> dict[str, str]:
    """Every Markdown and CSV file, keyed by its path inside the knowledge base."""
    return {
        path.relative_to(directory).as_posix(): path.read_text(encoding="utf-8")
        for path in sorted(directory.rglob("*"))
        if path.is_file() and path.suffix in {".md", ".csv"}
    }


def read_employees(content: str) -> list[list[str]]:
    reader = csv.DictReader(content.splitlines())
    if reader.fieldnames != EMPLOYEE_COLUMNS:
        raise SystemExit(f"{EMPLOYEES_FILE}: expected columns {EMPLOYEE_COLUMNS}")
    rows = list(reader)
    if not rows:
        raise SystemExit(f"{EMPLOYEES_FILE} is empty; nothing was changed.")
    if any(None in row or None in row.values() for row in rows):
        raise SystemExit(f"{EMPLOYEES_FILE}: a row has the wrong number of fields")
    return [[row[column] for column in EMPLOYEE_COLUMNS] for row in rows]


def sync(connection: psycopg.Connection, directory: Path, dry_run: bool) -> None:
    documents = read_documents(directory)
    if EMPLOYEES_FILE not in documents:
        raise SystemExit(f"{directory / EMPLOYEES_FILE} not found; nothing was changed.")
    employees = read_employees(documents[EMPLOYEES_FILE])

    create_tables(connection)
    stored = dict(connection.execute("SELECT path, content FROM knowledge_base.documents"))
    added = sorted(documents.keys() - stored.keys())
    removed = sorted(stored.keys() - documents.keys())
    changed = sorted(
        path for path in documents.keys() & stored.keys()
        if documents[path] != stored[path]
    )
    for label, paths in (("add", added), ("update", changed), ("remove", removed)):
        for path in paths:
            print(f"{label:7}{path}")
    print(
        f"{len(documents)} documents ({len(added)} new, {len(changed)} changed, "
        f"{len(removed)} removed), {len(employees)} employees"
    )
    if dry_run:
        connection.rollback()
        print("Dry run: nothing was changed.")
        return

    with connection.cursor() as cursor:
        cursor.executemany(
            "INSERT INTO knowledge_base.documents (path, content) VALUES (%s, %s) "
            "ON CONFLICT (path) DO UPDATE "
            "SET content = EXCLUDED.content, updated_at = now()",
            [(path, documents[path]) for path in added + changed],
        )
        cursor.execute("DELETE FROM knowledge_base.documents WHERE path = ANY(%s)", (removed,))
        cursor.execute("DELETE FROM knowledge_base.employees")
        placeholders = ", ".join(["%s"] * len(EMPLOYEE_COLUMNS))
        cursor.executemany(
            f"INSERT INTO knowledge_base.employees ({', '.join(EMPLOYEE_COLUMNS)}) "
            f"VALUES ({placeholders})",
            employees,
        )
    print("Synced.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true", help="only show changes")
    arguments = parser.parse_args()
    # One transaction: either everything is updated or nothing is.
    with connect() as connection:
        sync(connection, KNOWLEDGE_BASE, arguments.dry_run)


if __name__ == "__main__":
    main()
