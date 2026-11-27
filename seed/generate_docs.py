"""Regenerate the pages that restate the roster: directory and org chart.

Both are derived from employees.csv and capacity.csv, so they cannot drift away
from the data the agents actually query.
"""

import csv
from pathlib import Path

from generate_people import (
    CAPACITY_CSV,
    DEPARTMENT_ORDER,
    DEPARTMENT_TITLES,
    EMPLOYEES_CSV,
    LAST_UPDATED,
    PEOPLE,
)

ROOT = Path(__file__).resolve().parent.parent
DIRECTORY_MD = PEOPLE / "directory.md"
ORG_CHART_MD = ROOT / "knowledge-base" / "company" / "org-chart.md"


def load() -> tuple[list[dict], dict[str, dict]]:
    employees = list(csv.DictReader(EMPLOYEES_CSV.open(encoding="utf-8")))
    capacity = {r["employee_id"]: r
                for r in csv.DictReader(CAPACITY_CSV.open(encoding="utf-8"))}
    return employees, capacity


def front_matter(title: str, owner: str, classification: str) -> str:
    return (f"---\ntitle: {title!r}\nowner: {owner}\n"
            f"classification: {classification}\nlast_updated: {LAST_UPDATED}\n---\n")


def write_directory(employees: list[dict], capacity: dict[str, dict]) -> None:
    lines = [
        front_matter("Employee directory", "E25", "internal").replace("'", '"'),
        "\n# Employee directory\n",
        "\nAll 120 people are fictional. The same data is in "
        "[employees.csv](employees.csv); availability, day rates and access "
        "rights are in [capacity.csv](capacity.csv).\n",
        "\n`access` controls who may see the AI evaluation of submitted ideas: "
        "`admin` sees the ranked portfolio, `reviewer` sees the review queue "
        "and their own department, `employee` sees only their own submissions.\n",
    ]

    by_department: dict[str, list[dict]] = {}
    for row in employees:
        by_department.setdefault(row["department"], []).append(row)

    for department in DEPARTMENT_ORDER:
        rows = by_department.get(department, [])
        if not rows:
            continue
        lines.append(f"\n## {DEPARTMENT_TITLES[department]} ({len(rows)})\n")
        lines.append(
            "\n| ID | Name | Role | Manager | Site | Work mode | Start | "
            "Free % | EUR/day | Access | Deputy |\n"
            "|---|---|---|---|---|---|---|---|---|---|---|\n"
        )
        for row in rows:
            cap = capacity[row["id"]]
            lines.append(
                f"| {row['id']} | {row['name']} | {row['role']} | "
                f"{row['manager_id'] or 'none'} | {cap['site']} | "
                f"{row['work_mode']} | {row['start_date']} | "
                f"{cap['capacity_pct_available']}% | "
                f"{cap['cost_per_day_eur']} | {cap['access_role']} | "
                f"{row['deputy_id'] or '-'} |\n"
            )

    DIRECTORY_MD.write_text("".join(lines), encoding="utf-8")
    print(f"directory.md: {len(employees)} people")


def write_org_chart(employees: list[dict], capacity: dict[str, dict]) -> None:
    by_id = {row["id"]: row for row in employees}
    children: dict[str, list[str]] = {}
    for row in employees:
        children.setdefault(row["manager_id"], []).append(row["id"])

    def render(employee_id: str, depth: int, out: list[str]) -> None:
        row = by_id[employee_id]
        reports = children.get(employee_id, [])
        suffix = f"  [{len(reports)} reports]" if len(reports) > 2 else ""
        out.append(f"{'  ' * depth}{row['name']} ({employee_id}), "
                   f"{row['role']}{suffix}")
        for child in sorted(reports, key=lambda i: int(i[1:])):
            render(child, depth + 1, out)

    tree: list[str] = []
    for root_id in sorted(children.get("", []), key=lambda i: int(i[1:])):
        render(root_id, 0, tree)

    span = sorted(
        ((len(kids), mid) for mid, kids in children.items() if mid),
        reverse=True,
    )[:5]

    lines = [
        front_matter("Org chart", "E25", "internal").replace("'", '"'),
        "\n# Org chart\n",
        "\nIndentation shows the reporting line. 120 people in "
        f"{len(DEPARTMENT_ORDER)} departments across Aachen (HQ), Eindhoven "
        "and Vienna.\n",
        "\n```text\n", "\n".join(tree), "\n```\n",
        "\n## Largest teams\n",
        "\n| Manager | Role | Direct reports |\n|---|---|---|\n",
    ]
    for count, manager_id in span:
        lines.append(f"| {by_id[manager_id]['name']} ({manager_id}) | "
                     f"{by_id[manager_id]['role']} | {count} |\n")

    ORG_CHART_MD.write_text("".join(lines), encoding="utf-8")
    print(f"org-chart.md: {len(tree)} lines, deepest span {span[0][0]} reports")


if __name__ == "__main__":
    people, caps = load()
    write_directory(people, caps)
    write_org_chart(people, caps)
