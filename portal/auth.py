"""Simple login for a few users. Passwords are stored in plain text.

users.csv (not in the repository) has the columns username and password.
Usernames are lowercase. An employee's username is their last name, as in the
knowledge base. The one user "innovation" is not an employee and opens the
Innovation Dashboard.
"""

import csv
import hmac
from pathlib import Path

from db import connect

USERS_CSV = Path(__file__).resolve().parent / "users.csv"
DASHBOARD_USER = "innovation"


def is_dashboard_user(username: str) -> bool:
    return username.strip().casefold() == DASHBOARD_USER


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
    wanted = username.strip().casefold()
    if not (is_dashboard_user(wanted) or find_employee(wanted)):
        return False
    with USERS_CSV.open(newline="", encoding="utf-8") as file:
        for row in csv.DictReader(file):
            if row["username"].casefold() == wanted:
                return hmac.compare_digest(
                    row["password"].encode(), password.encode()
                )
    return False
