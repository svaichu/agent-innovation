"""Simple login for a few employees. Passwords are stored in plain text.

The username is the employee's last name, from the knowledge base.
users.csv (not in the repository) maps employee IDs to passwords.
"""

import csv
import hmac
from pathlib import Path

from db import connect

USERS_CSV = Path(__file__).resolve().parent / "users.csv"


def find_employee(username: str) -> dict[str, str] | None:
    """The employee with this last name, or None if nobody or several have it."""
    wanted = username.strip().casefold()
    with connect() as connection:
        rows = connection.execute(
            "SELECT id, name FROM knowledge_base.employees"
        ).fetchall()
    matches = [
        {"id": employee_id, "name": name}
        for employee_id, name in rows
        if name.split()[-1].casefold() == wanted
    ]
    return matches[0] if len(matches) == 1 else None


def check_login(username: str, password: str) -> bool:
    """Read users.csv on every attempt, so changes apply without a restart."""
    if not (employee := find_employee(username)):
        return False
    with USERS_CSV.open(newline="", encoding="utf-8") as file:
        for row in csv.DictReader(file):
            if row["employee_id"] == employee["id"]:
                return hmac.compare_digest(
                    row["password"].encode(), password.encode()
                )
    return False
