"""Demo logins for all 120 employees.

employee_interface/users.csv holds five logins and belongs to that app, so it
is left untouched. The five passwords in it are reused verbatim here, so the
same credentials work in both apps during a demo.

Passwords are readable word triples, written to a file that is NOT committed
(see .gitignore). This is demo scaffolding for a prototype on localhost, not an
authentication scheme: there is no hashing and no rate limiting, and the README
says so.
"""

import csv
import random
from pathlib import Path

from generate_people import EMPLOYEES_CSV, PEOPLE, ROOT

OUT = ROOT / "seed" / "data" / "demo_logins.csv"
# A short, readable sheet to keep open during a demo. Gitignored like the CSV.
SHEET = ROOT / "TEST_LOGINS.md"
EXISTING = ROOT / "employee_interface" / "users.csv"
CAPACITY_CSV = PEOPLE / "capacity.csv"

SEED = 20261127

ADJECTIVES = ["maple", "copper", "quiet", "amber", "silver", "golden", "rapid",
              "calm", "bright", "hidden", "narrow", "gentle", "lucky", "brave",
              "clever", "distant", "early", "frozen", "green", "humble",
              "ivory", "jolly", "keen", "little", "misty", "noble", "open",
              "proud", "royal", "steady", "tidy", "upper", "vivid", "warm"]
NOUNS = ["river", "field", "harbor", "forest", "meadow", "valley", "ridge",
         "hollow", "spring", "garden", "island", "canyon", "bridge", "summit",
         "thicket", "orchard", "lantern", "compass", "anchor", "beacon",
         "cedar", "dune", "ember", "fjord", "glade", "heather", "inlet",
         "juniper", "kettle", "lagoon", "marsh", "nettle", "oasis", "pebble"]


def load_existing() -> dict[str, str]:
    if not EXISTING.exists():
        return {}
    with EXISTING.open(newline="", encoding="utf-8") as file:
        return {r["employee_id"]: r["password"] for r in csv.DictReader(file)}


def generate() -> None:
    rng = random.Random(SEED)
    reused = load_existing()
    employees = list(csv.DictReader(EMPLOYEES_CSV.open(encoding="utf-8")))
    access = {r["employee_id"]: r["access_role"] for r in
              csv.DictReader(CAPACITY_CSV.open(encoding="utf-8"))}

    taken = set(reused.values())
    rows = []
    for employee in employees:
        employee_id = employee["id"]
        password = reused.get(employee_id)
        while password is None:
            candidate = (f"{rng.choice(ADJECTIVES)}-{rng.choice(NOUNS)}-"
                         f"{rng.randint(10, 99)}")
            if candidate not in taken:
                taken.add(candidate)
                password = candidate
        rows.append({
            "employee_id": employee_id,
            "password": password,
            "name": employee["name"],
            "department": employee["department"],
            "access_role": access.get(employee_id, "employee"),
        })

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    write_sheet(rows)

    counts: dict[str, int] = {}
    for row in rows:
        counts[row["access_role"]] = counts.get(row["access_role"], 0) + 1
    print(f"{OUT.relative_to(ROOT)}: {len(rows)} logins "
          f"({len(reused)} reused from employee_interface/users.csv)")
    print(f"  by access role: {counts}")
    print(f"{SHEET.relative_to(ROOT)}: demo sheet written (both gitignored)")
    print("\n  Credentials to test with:")
    for row in pick_demo_logins(rows):
        print(f"    {row['employee_id']}  {row['password']:<18} "
              f"{row['access_role']:<9} {row['name']}")


def pick_demo_logins(rows: list[dict]) -> list[dict]:
    """A small, useful set: every admin, two reviewers, three employees.

    The employees are chosen from departments that actually submitted seeded
    ideas, so "My ideas" is not empty when you log in as one.
    """
    chosen = [r for r in rows if r["access_role"] == "admin"]
    chosen += [r for r in rows if r["access_role"] == "reviewer"][:2]
    for department in ("support", "sales", "operations"):
        match = next((r for r in rows if r["access_role"] == "employee"
                      and r["department"] == department), None)
        if match:
            chosen.append(match)
    return chosen


def write_sheet(rows: list[dict]) -> None:
    by_id = {r["employee_id"]: r for r in rows}
    lines = [
        "# Test logins",
        "",
        "**Generated and gitignored.** Recreate any time with "
        "`python seed/generate_logins.py`.",
        "",
        "Plain-text passwords for a prototype on localhost. This is not an "
        "authentication scheme: no hashing, no rate limiting, no lockout. "
        "Anything real would use SSO. Authorization, unlike authentication, "
        "*is* enforced properly - server-side in `compass/views.py`, on every "
        "call rather than by hiding a tab.",
        "",
        "## Recommended: one port, one login",
        "",
        "`python -m compass.serve` serves **both** apps on "
        "http://127.0.0.1:7860 — the board at `/` and the idea-intake chat at "
        "`/intake/`. Signing in once covers both, and the Log out button "
        "clears both. The board header gets a **Submit an idea** button.",
        "",
        "## Board app - also runs alone: `python -m compass.app` "
        "(http://127.0.0.1:7861)",
        "",
        "| Employee ID | Password | Access role | Name | What you can see |",
        "|---|---|---|---|---|",
    ]
    explanation = {
        "admin": "Everything: ranked portfolio, scoring method, review queue",
        "reviewer": "Review queue and own department; **no** ranked portfolio",
        "employee": "Ask the company, and own submissions without scores",
    }
    for row in pick_demo_logins(rows):
        lines.append(
            f"| `{row['employee_id']}` | `{row['password']}` | "
            f"{row['access_role']} | {row['name']} ({row['department']}) | "
            f"{explanation[row['access_role']]} |")

    lines += [
        "",
        "Start with the first admin: they are the Head of Strategy & AI "
        "Portfolio, the role that owns this tool.",
        "",
        "### Worth trying",
        "",
        "- Log in as an **employee** and note the Portfolio tab is absent, not "
        "merely disabled.",
        "- Ask the knowledge chat *\"What is our ARR target for 2027?\"* as an "
        "employee and then as an admin. Strategy is classified "
        "`confidential`, so only the admin gets it; the employee is told how "
        "many sections are hidden and who to ask.",
        "- As an admin, select **UC-006** (webcam stress monitoring) and press "
        "**Select**. It refuses, citing Article 5(1)(f), and says the business "
        "score does not override it.",
        "- **Log out** (top right) clears your session and returns you to the "
        "login screen, so you can sign in as a different role. It ends only "
        "the current browser session, so a second tab signed in as someone "
        "else stays open - which is the quickest way to show an admin view "
        "and an employee view side by side.",
        "",
        "## Intake app - also runs alone: "
        "`python employee_interface/app.py` (http://127.0.0.1:7860)",
        "",
        "That app has its own credentials in "
        "`employee_interface/users.csv` (committed, owned by a teammate). "
        "These five IDs share the same password in both apps, so you can "
        "submit an idea and then see it on the board:",
        "",
        "| Employee ID | Password | Name |",
        "|---|---|---|",
    ]
    for employee_id in ("E01", "E03", "E06", "E07", "E08"):
        row = by_id.get(employee_id)
        if row:
            lines.append(f"| `{employee_id}` | `{row['password']}` | "
                         f"{row['name']} |")
    lines += [
        "",
        "After submitting, run `python -m seed.load` to re-assess, then look "
        "for the new `RI-` row on the board.",
        "",
        "## All 120",
        "",
        "`seed/data/demo_logins.csv` has every employee, with their access "
        "role. Also gitignored.",
        "",
    ]
    SHEET.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    generate()
