"""Render the nine department pages.

Team tables come from employees.csv so the IDs and names always match the
roster. The prose below is authored: mission, responsibilities, tools, key
figures and - most importantly - the pain points, which are what employees
submit ideas about.
"""

import csv
from pathlib import Path

from generate_people import (
    DEPARTMENT_TITLES,
    EMPLOYEES_CSV,
    LAST_UPDATED,
    ROOT,
)

DEPARTMENTS_DIR = ROOT / "knowledge-base" / "departments"

# Roles always shown in a department's table, however large the department.
LEADERSHIP_HINTS = ("Head of", "Lead", "Manager", "Chief", "CEO", "CTO",
                    "Officer", "Product Manager")

PROSE: dict[str, dict] = {
    "management": {
        "owner": "E01",
        "mission": "Set direction, allocate money and people, and remove blockers.",
        "responsibilities": [
            "Annual plan and quarterly review",
            "Approvals above department limits",
            "Investor and bank relations",
            "Security and risk oversight",
            "Internal investment portfolio, including AI use cases",
        ],
        "tools": "Google Workspace, Slack, finance reports from DATEV, BI dashboards",
        "figures": [
            ("Revenue, year to date", "EUR 12.60 million", "EUR 15.40 million by year end"),
            ("Cash runway", "16 months", "at least 12 months"),
            ("Internal tooling budget committed", "EUR 108,000 of 250,000", "spent on measured benefit"),
            ("AI use cases in production", "0", "2 by end of 2027"),
        ],
        "pains": [
            "Figures for the leadership sync are copied by hand from six systems, about 5 hours per week.",
            "No single list of internal improvement ideas. The same proposal reaches the leadership sync from two departments more than once a quarter.",
            "Ideas arrive in different formats, so they cannot be compared: some carry numbers, most do not.",
            "Nobody tracks whether a funded internal project delivered the benefit it promised.",
            "Department heads estimate effort informally, and the estimates are usually too low.",
        ],
    },
    "engineering": {
        "owner": "E03",
        "mission": "Build reliable sensors and software.",
        "composition": "6 hardware and mechanical, 4 firmware, 6 backend, 3 frontend, 1 QA, 3 DevOps and SRE, 4 product, design and documentation, 3 leads.",
        "responsibilities": [
            "Hardware, firmware and Canopy development",
            "Releases and certification",
            "Cloud operations",
        ],
        "tools": "Jira, GitHub, AWS, Grafana, Slack, Confluence",
        "figures": [
            ("Canopy availability", "99.93%", "99.9%"),
            ("Open bugs, priority high", "34", "under 20"),
            ("Releases per month", "4", "4"),
            ("Median pull request review time", "19 hours", "under 8 hours"),
            ("Share of developer time on support questions", "18%", "under 10%"),
        ],
        "pains": [
            "Bug reports from support often lack firmware version and logs, so about a third are sent back for more information.",
            "Calibration results are typed from the test rig into spreadsheets, roughly 400 devices per week.",
            "About 18% of developer time goes to answering support and sales questions that are already documented somewhere.",
            "Release notes are written by hand from Jira tickets before every release.",
            "Nobody can answer \"which customers run which firmware version\" without a manual export.",
            "Test coverage of the firmware reconnect path is thin, and reconnect bugs keep returning.",
        ],
    },
    "data-it": {
        "owner": "@HEAD",
        "mission": "Make company data usable and keep internal systems running.",
        "responsibilities": [
            "Data warehouse, BI and reporting",
            "System integrations between business systems",
            "Internal IT: devices, accounts, helpdesk",
            "Data quality and access governance",
        ],
        "tools": "Data warehouse, BI tool, dbt, Airflow, Google Workspace, Slack, device management",
        "figures": [
            ("Systems in the data warehouse", "4 of 16", "10 of 16"),
            ("Open report requests", "23", "under 10"),
            ("Median time to deliver a report", "11 working days", "3 working days"),
            ("Internal helpdesk tickets per month", "210", "under 160"),
            ("First response, internal helpdesk", "1.4 working days", "4 working hours"),
        ],
        "pains": [
            "Only HubSpot, Zendesk, Canopy and DATEV reach the warehouse. Inventory, RMA and Personio data are still manual exports.",
            "Several leadership figures exist in two places with two values, and reconciling them takes a day each month.",
            "Report requests arrive in Slack with no detail, so most need two clarification rounds.",
            "The same twelve questions make up about half the internal helpdesk volume: passwords, VPN, printer, access requests.",
            "There is no data catalogue, so analysts rediscover the same table definitions.",
        ],
    },
    "sales": {
        "owner": "E10",
        "mission": "Win and grow customer accounts.",
        "composition": "2 regional sales managers, 9 account executives, 3 sales development representatives, 1 partner manager, 1 sales operations analyst.",
        "responsibilities": [
            "Lead qualification and demos",
            "Quotes, tenders and contracts",
            "Reseller channel",
            "Forecast",
        ],
        "tools": "HubSpot, Google Workspace, tender portals",
        "figures": [
            ("Qualified pipeline", "EUR 6.80 million", "EUR 7.50 million"),
            ("Win rate", "27%", "30%"),
            ("Median days from lead to order", "64", "50"),
            ("Tenders answered per month", "14", "20"),
            ("CRM notes completed after a call", "61%", "90%"),
        ],
        "pains": [
            "Public tenders take 2 to 4 days each to answer, mostly reusing text from the roughly 420 tender documents already written.",
            "CRM notes are incomplete after calls, so forecasts rest on memory.",
            "Reps ask support and engineering the same technical questions repeatedly, about 40 Slack questions per week.",
            "Quote preparation needs a manual stock and lead-time check with Operations.",
            "No reliable view of which accounts are at risk until the renewal month.",
        ],
    },
    "marketing": {
        "owner": "E14",
        "mission": "Create demand and explain the product clearly.",
        "responsibilities": [
            "Website, newsletter and campaigns",
            "Trade fairs and webinars",
            "Case studies and sales material",
            "Product messaging and launches",
        ],
        "tools": "Website content system, HubSpot, web analytics, design tool",
        "figures": [
            ("Marketing-qualified leads per month", "210", "260"),
            ("Newsletter subscribers", "14,500", "18,000"),
            ("Case studies published per quarter", "2", "5"),
            ("Website pages out of date", "38 of 190", "under 10"),
        ],
        "pains": [
            "Case studies take about 6 weeks, mostly waiting for input from Sales and the customer.",
            "Product facts on the website drift from the current data sheets; 38 pages are known to be out of date.",
            "Content is translated between German, Dutch and English by hand.",
            "Campaign reporting is assembled by hand from three tools every month.",
            "The same product questions arrive through the website form and are answered individually.",
        ],
    },
    "support": {
        "owner": "E16",
        "mission": "Get customers running and keep them successful.",
        "composition": "1 team lead, 10 support specialists, 1 knowledge manager, 4 customer success managers, 5 field installation technicians, 1 head.",
        "responsibilities": [
            "Onboarding, installation and training",
            "Tickets, returns and escalations",
            "Renewals together with Sales",
        ],
        "tools": "Zendesk, HubSpot, Canopy admin view, Slack",
        "figures": [
            ("Tickets per month", "1,250", "under 900"),
            ("First response within SLA", "88%", "95%"),
            ("Customer satisfaction", "4.4 of 5", "4.5 of 5"),
            ("Annual revenue churn", "7%", "under 5%"),
            ("Tickets resolved without escalation", "74%", "85%"),
        ],
        "pains": [
            "About 40% of tickets are repeat questions on connectivity, readings and logins, roughly 500 per month.",
            "Tickets are categorised and routed by hand, which costs the team lead about an hour a day.",
            "Help centre articles are partly outdated: about 30 of 85 no longer match the product.",
            "Site survey notes are written on paper and typed up later, often days after the visit.",
            "Onboarding status per customer is tracked in a personal spreadsheet per success manager.",
            "Escalations to engineering are reopened because the first handover lacked logs.",
        ],
    },
    "operations": {
        "owner": "E20",
        "mission": "Deliver correct, tested devices on time.",
        "composition": "1 production lead, 5 assembly technicians, 3 quality and test technicians, 1 planner, 2 procurement, 1 supplier quality, 2 logistics, 1 warehouse lead, 1 inventory controller, 1 head.",
        "responsibilities": [
            "Purchasing and suppliers",
            "Assembly, end-of-line test and repairs",
            "Inventory and shipping",
        ],
        "tools": "Inventory spreadsheet, shipping carrier portals, DATEV exports, Slack",
        "figures": [
            ("Median order-to-ship", "8 working days", "4 working days"),
            ("End-of-line test pass rate", "97.1%", "98.5%"),
            ("Return rate within 12 months", "2.3%", "under 1.5%"),
            ("Stock record accuracy", "87%", "98%"),
            ("Purchase orders raised per month", "180", "same, with less effort"),
        ],
        "pains": [
            "Stock is tracked in a spreadsheet that is often out of date, and record accuracy sits at 87%.",
            "Reorder dates are estimated by experience; there were two stock-outs in 2026.",
            "Order data is retyped from HubSpot into the inventory sheet, about 180 orders per month.",
            "Supplier lead times are tracked in email threads, not in any system.",
            "Fault codes from returns are recorded in a separate spreadsheet and reviewed only monthly.",
        ],
    },
    "quality-compliance": {
        "owner": "@HEAD",
        "mission": "Keep the product compliant and the management system audit-ready.",
        "responsibilities": [
            "Quality management system and internal audits",
            "Product certification: CE marking, radio regulation",
            "Data protection, subject requests and DPIAs",
            "Information security and access reviews",
            "Register of AI systems and their risk classification",
        ],
        "tools": "Document management, Confluence, Google Workspace, risk register",
        "figures": [
            ("ISO 27001 readiness", "38% of controls evidenced", "100% by Q4 2027"),
            ("Open corrective actions", "17", "under 8"),
            ("Data subject requests per quarter", "9", "answered within one month"),
            ("Access reviews completed on time", "72%", "100%"),
            ("AI systems in the register", "3", "all of them"),
        ],
        "pains": [
            "Audit evidence is collected by hand from six systems before every audit, about 10 person-days each time.",
            "Policy documents are reviewed on paper and the review dates are tracked in a spreadsheet.",
            "No structured screening exists for new AI use cases, so EU AI Act obligations are assessed late or not at all.",
            "Data processing agreements are stored per contract, with no single register of processors.",
            "Access reviews depend on exports that each system owner produces differently.",
        ],
    },
    "finance-people": {
        "owner": "E23",
        "mission": "Keep the company funded, compliant and a good place to work.",
        "responsibilities": [
            "Bookkeeping, invoicing and payroll preparation",
            "Budget and monthly close",
            "Contracts and data protection coordination",
            "Hiring, onboarding and training",
        ],
        "tools": "DATEV, Personio, Google Workspace",
        "figures": [
            ("Monthly close", "9 working days", "5 working days"),
            ("Invoices overdue more than 30 days", "6%", "under 4%"),
            ("Open positions", "7", "under 4"),
            ("Supplier invoices processed per month", "1,100", "same, with less effort"),
            ("Time to fill a role", "68 days", "45 days"),
        ],
        "pains": [
            "Supplier invoices are keyed in manually, about 1,100 per month across two people.",
            "Expense receipts arrive late and incomplete, and chasing them takes about 6 hours a month.",
            "New staff ask the same policy questions; onboarding answers the same twenty questions each time.",
            "Candidate applications are screened by hand, about 140 per open role.",
            "Leave and working-time corrections are made by email and then entered twice.",
        ],
    },
}


def load_by_department() -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {}
    with EMPLOYEES_CSV.open(encoding="utf-8") as file:
        for row in csv.DictReader(file):
            grouped.setdefault(row["department"], []).append(row)
    return grouped


def table_rows(members: list[dict]) -> list[dict]:
    """Leadership and named owners. Small departments show everybody."""
    if len(members) <= 9:
        return members
    original = [m for m in members if int(m["id"][1:]) <= 25]
    leads = [m for m in members
             if any(h in m["role"] for h in LEADERSHIP_HINTS)
             and int(m["id"][1:]) > 25]
    chosen = {m["id"]: m for m in original + leads}
    return sorted(chosen.values(), key=lambda m: int(m["id"][1:]))


def render(department: str, members: list[dict], prose: dict) -> str:
    shown = table_rows(members)
    owner = prose["owner"]
    if owner == "@HEAD":
        owner = next(m["id"] for m in members if m["role"].startswith("Head of"))

    out = [
        "---",
        f'title: "{DEPARTMENT_TITLES[department]}"',
        f"owner: {owner}",
        "classification: internal",
        f"last_updated: {LAST_UPDATED}",
        "---",
        "",
        f"# {DEPARTMENT_TITLES[department]}",
        "",
        "## Mission",
        prose["mission"],
        "",
        f"## Team ({len(members)})",
    ]
    if len(shown) < len(members):
        out += ["Leadership and named owners. The full list is in the "
                "[directory](../people/directory.md)."]
    out += ["", "| ID | Name | Role | Skills |", "|---|---|---|---|"]
    for member in shown:
        out.append(f"| {member['id']} | {member['name']} | {member['role']} "
                   f"| {member['skills']} |")
    if "composition" in prose:
        out += ["", f"Composition: {prose['composition']}"]

    out += ["", "## Responsibilities"]
    out += [f"- {item}" for item in prose["responsibilities"]]
    out += ["", "## Tools", prose["tools"], "",
            "## Key figures, October 2026", "",
            "| Measure | Current | Target |", "|---|---|---|"]
    for measure, current, target in prose["figures"]:
        out.append(f"| {measure} | {current} | {target} |")
    out += ["", "## Known pain points"]
    out += [f"- {item}" for item in prose["pains"]]
    out.append("")
    return "\n".join(out)


if __name__ == "__main__":
    grouped = load_by_department()
    for department, prose in PROSE.items():
        members = grouped[department]
        path = DEPARTMENTS_DIR / f"{department}.md"
        path.write_text(render(department, members, prose), encoding="utf-8")
        print(f"{path.name}: {len(members)} people, "
              f"{len(table_rows(members))} shown, {len(prose['pains'])} pain points")
