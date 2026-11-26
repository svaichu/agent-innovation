"""Simple login for a few employees. Passwords are stored in plain text."""

import csv
import hmac
from pathlib import Path

USERS_CSV = Path(__file__).resolve().parent / "users.csv"


def normalize_id(employee_id: str) -> str:
    return employee_id.strip().upper()


def check_login(username: str, password: str) -> bool:
    """Read users.csv on every attempt, so changes apply without a restart."""
    with USERS_CSV.open(newline="", encoding="utf-8") as file:
        for row in csv.DictReader(file):
            if row["employee_id"] == normalize_id(username):
                return hmac.compare_digest(
                    row["password"].encode(), password.encode()
                )
    return False
