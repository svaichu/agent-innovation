"""The facts the feasibility agent is allowed to use.

Every function returns a dataclass carrying both an answer and the knowledge
base path it came from. The agent must cite those paths, which is what makes a
feasibility verdict checkable rather than an opinion.

Nothing here calls a model. These are deterministic lookups.
"""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass, field
from typing import Any

from .. import db

# Working days per month used for every capacity calculation.
WORKING_DAYS_PER_MONTH = 20

STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "for", "in", "on", "with", "by",
    "from", "our", "we", "it", "is", "are", "be", "that", "this", "their",
    "would", "could", "should", "can", "all", "into", "about", "per", "at",
    "as", "if", "not", "no", "but", "them", "they", "then", "than", "so",
    "data", "system", "systems", "use", "using", "used", "new", "more",
}


def tokens(text: str) -> set[str]:
    """Content words, for topical matching.

    Pure numbers are dropped. They are never a topical signal here and they
    create false matches: "52,000 tickets" and "13,000 invoices" both yield
    the token "000", which once made a ticket-routing idea match the supplier
    invoice dataset. Figures are read by the dedicated parsers in
    agents/score.py and agents/feasibility.py, not by this tokeniser.
    """
    return {w for w in re.findall(r"[a-z0-9]+", (text or "").lower())
            if len(w) > 2 and w not in STOPWORDS and not w.isdigit()}


def _attrs(row: sqlite3.Row) -> dict[str, Any]:
    return json.loads(row["attrs"])


# --------------------------------------------------------------------------- #
# result types
# --------------------------------------------------------------------------- #
@dataclass
class SkillMatch:
    skill: str
    matched_name: str
    holders: list[dict]          # employee_id, name, role, department, free %
    holder_count: int
    cite: str = "knowledge-base/people/employees.csv"

    @property
    def is_bottleneck(self) -> bool:
        return 0 < self.holder_count <= 3


@dataclass
class SystemFact:
    name: str
    found: bool
    purpose: str = ""
    owner_id: str = ""
    api_or_automation: str = ""
    integrable: bool = False
    personal_data: str = ""
    in_data_warehouse: str = ""
    cite: str = "knowledge-base/it/systems.md"


@dataclass
class DatasetFact:
    name: str
    system: str
    owner_id: str
    volume: str
    quality: str
    quality_note: str
    personal_data: str
    usable_as_is: bool
    cite: str = "knowledge-base/it/data-inventory.md"


@dataclass
class CapacityFact:
    requested_person_days: int | None
    monthly_allocation: int
    committed_person_days: int
    months_to_deliver: float | None
    status: str                  # ok | tight | over
    note: str
    cites: list[str] = field(default_factory=list)


@dataclass
class BudgetFact:
    requested_eur: int | None
    budget_eur: int
    committed_eur: int
    remaining_eur: int
    approval_path: str
    status: str                  # ok | needs_board | over
    note: str = ""
    cites: list[str] = field(default_factory=list)


@dataclass
class PriorityMatch:
    number: str
    priority: str
    target: str
    owner: str
    overlap: int
    cite: str = "knowledge-base/company/strategy-2027.md"


@dataclass
class PolicyFact:
    rule: str
    policy: str
    cite: str
    severity: str                # blocks | requires_approval | note


@dataclass
class PainPointMatch:
    department: str
    text: str
    overlap: int
    cite: str


# --------------------------------------------------------------------------- #
# queries
# --------------------------------------------------------------------------- #
def skills_available(conn: sqlite3.Connection,
                     required: list[str]) -> list[SkillMatch]:
    """Who in the company holds each required skill.

    Matching is token overlap against the skill vocabulary, so "Python" finds
    "Python; FastAPI; AWS" and "machine learning" finds nothing - which is
    itself the useful answer.
    """
    skills = conn.execute(
        "SELECT id, name FROM kg_node WHERE type = 'Skill'").fetchall()
    results: list[SkillMatch] = []

    for want in required:
        wanted = tokens(want)
        if not wanted:
            continue
        best: tuple[int, str, str] | None = None
        for row in skills:
            overlap = len(wanted & tokens(row["name"]))
            if overlap and (best is None or overlap > best[0]):
                best = (overlap, row["id"], row["name"])

        if best is None:
            results.append(SkillMatch(skill=want, matched_name="",
                                      holders=[], holder_count=0))
            continue

        holders = []
        for holder in conn.execute(
            "SELECT n.* FROM kg_node n JOIN kg_edge e ON e.src = n.id "
            "WHERE e.rel = 'has_skill' AND e.dst = ?", (best[1],)
        ).fetchall():
            attrs = _attrs(holder)
            holders.append({
                "employee_id": attrs["employee_id"],
                "name": holder["name"],
                "role": attrs["role"],
                "department": attrs["department"],
                "capacity_pct_available": attrs["capacity_pct_available"],
                "cost_per_day_eur": attrs["cost_per_day_eur"],
            })
        holders.sort(key=lambda h: -h["capacity_pct_available"])
        results.append(SkillMatch(skill=want, matched_name=best[2],
                                  holders=holders, holder_count=len(holders)))
    return results


def system_integrability(conn: sqlite3.Connection,
                         names: list[str]) -> list[SystemFact]:
    """Whether each named system can actually be reached by automation."""
    rows = conn.execute(
        "SELECT * FROM kg_node WHERE type = 'System'").fetchall()
    facts: list[SystemFact] = []

    for name in names:
        wanted = tokens(name)
        match = None
        for row in rows:
            if row["name"].lower() in name.lower() or name.lower() in row["name"].lower():
                match = row
                break
            if wanted & tokens(row["name"]):
                match = row
                break
        if match is None:
            facts.append(SystemFact(name=name, found=False))
            continue
        attrs = _attrs(match)
        facts.append(SystemFact(
            name=match["name"], found=True, purpose=attrs["purpose"],
            owner_id=attrs["owner_id"],
            api_or_automation=attrs["api_or_automation"],
            integrable=bool(attrs["integrable"]),
            personal_data=attrs["personal_data"],
            in_data_warehouse=attrs.get("in_data_warehouse", "no"),
        ))
    return facts


def dataset_fitness(conn: sqlite3.Connection, topics: list[str],
                    limit: int = 5) -> list[DatasetFact]:
    """Datasets relevant to the topics, with quality and personal-data status."""
    rows = conn.execute(
        "SELECT * FROM kg_node WHERE type = 'Dataset'").fetchall()
    wanted = tokens(" ".join(topics))
    scored = []
    for row in rows:
        attrs = _attrs(row)
        haystack = tokens(f"{row['name']} {attrs['system']} {attrs['volume']}")
        overlap = len(wanted & haystack)
        if overlap:
            scored.append((overlap, row, attrs))
    # Equal topical overlap is broken by data quality: a board should be shown
    # the best usable source first, not an arbitrary one.
    grades = {"high": 3, "medium": 2, "low": 1}
    scored.sort(key=lambda item: (-item[0],
                                  -grades.get(item[2]["quality"].split()[0], 1)))

    return [
        DatasetFact(
            name=row["name"], system=attrs["system"], owner_id=attrs["owner_id"],
            volume=attrs["volume"], quality=attrs["quality"],
            quality_note=attrs["quality_note"],
            personal_data=attrs["personal_data"],
            usable_as_is=bool(attrs["usable_as_is"]),
        )
        for _, row, attrs in scored[:limit]
    ]


def capacity_outlook(conn: sqlite3.Connection,
                     person_days: int | None) -> CapacityFact:
    """Requested effort against the allocation and what is already committed."""
    allocation_row = conn.execute(
        "SELECT attrs FROM kg_node WHERE type = 'Constraint' "
        "AND id LIKE '%engineering-capacity%'").fetchone()
    allocation = 60
    if allocation_row:
        value = json.loads(allocation_row["attrs"]).get("value", "")
        found = re.search(r"(\d+)", value)
        if found:
            allocation = int(found.group(1))

    committed = conn.execute(
        "SELECT COALESCE(SUM(json_extract(attrs, '$.remaining_person_days')), 0) "
        "FROM kg_node WHERE type = 'Project'").fetchone()[0] or 0

    cites = ["knowledge-base/company/strategy-2027.md",
             "knowledge-base/projects/active-projects.md"]

    if person_days is None:
        return CapacityFact(
            None, allocation, int(committed), None, "unknown",
            "No effort estimate was given, so capacity cannot be checked.", cites)

    months = round(person_days / allocation, 1) if allocation else None
    backlog_months = round(committed / allocation, 1) if allocation else 0
    if person_days <= allocation:
        # Fitting inside one month's allocation is not the same as starting
        # soon: the committed backlog decides when it could actually begin.
        status = "ok" if backlog_months <= 6 else "tight"
        note = (
            f"{person_days} person-days fits inside one month of the "
            f"{allocation} person-day internal allocation, but "
            f"{int(committed)} person-days are already committed "
            f"(about {backlog_months} months of backlog), so it queues "
            f"behind the active portfolio unless it is prioritised.")
    elif person_days <= allocation * 3:
        status, note = "tight", (
            f"{person_days} person-days is about {months} months of the whole "
            f"internal allocation, and {int(committed)} person-days are already "
            f"committed (about {backlog_months} months of backlog).")
    else:
        status, note = "over", (
            f"{person_days} person-days exceeds three months of the entire "
            f"{allocation} person-day allocation. Needs phasing or external help.")
    return CapacityFact(person_days, allocation, int(committed), months,
                        status, note, cites)


def budget_outlook(conn: sqlite3.Connection,
                   cost_eur: int | None) -> BudgetFact:
    """Requested spend against the internal tooling budget and approval rules."""
    budget = 250_000
    row = conn.execute(
        "SELECT attrs FROM kg_node WHERE type = 'Constraint' "
        "AND id LIKE '%internal-tooling%'").fetchone()
    if row:
        budget = json.loads(row["attrs"]).get("amount_eur") or budget

    # Committed spend is stated on the management department page.
    committed = 108_000
    management = conn.execute(
        "SELECT attrs FROM kg_node WHERE id = 'department:management'").fetchone()
    if management:
        figures = json.loads(management["attrs"]).get("figures", {})
        for measure, values in figures.items():
            if "budget committed" in measure.lower():
                found = re.search(r"([\d,]+)", values.get("current", ""))
                if found:
                    committed = int(found.group(1).replace(",", ""))

    remaining = budget - committed
    cites = ["knowledge-base/company/strategy-2027.md",
             "knowledge-base/policies/procurement.md"]

    if cost_eur is None:
        return BudgetFact(None, budget, committed, remaining, "unknown",
                          "unknown",
                          "No cost estimate, so budget fit is unchecked.", cites)

    if cost_eur <= 20_000:
        path = "Department head decides, reported to the leadership sync."
        status = "ok"
    elif cost_eur <= 50_000:
        path = ("Leadership sync decides on the ranked portfolio; "
                "two quotes required.")
        status = "needs_board"
    else:
        path = ("Katharina Vogel (E01) and Miriam Scholz (E23); "
                "three quotes required.")
        status = "needs_board"
    if cost_eur > remaining:
        status = "over"
        path += (f" Exceeds the EUR {remaining:,} still unspent in the "
                 f"2027 internal tooling budget.")
    note = (f"EUR {cost_eur:,} against EUR {remaining:,} still unspent of the "
            f"EUR {budget:,} internal tooling budget. {path}")
    return BudgetFact(cost_eur, budget, committed, remaining, path, status,
                      note, cites)


def strategy_alignment(conn: sqlite3.Connection, text: str,
                       limit: int = 3) -> list[PriorityMatch]:
    wanted = tokens(text)
    matches = []
    for row in conn.execute(
        "SELECT * FROM kg_node WHERE type = 'StrategyPriority'"
    ).fetchall():
        attrs = _attrs(row)
        overlap = len(wanted & tokens(f"{row['name']} {attrs['target']}"))
        if overlap:
            matches.append(PriorityMatch(
                number=row["id"].split(":")[1], priority=row["name"],
                target=attrs["target"], owner=attrs["owner"], overlap=overlap))
    matches.sort(key=lambda m: -m.overlap)
    return matches[:limit]


def policy_constraints(conn: sqlite3.Connection, text: str) -> list[PolicyFact]:
    """Policy rules that bear on this idea.

    Hard-coded against the policy pages because these are the rules that
    actually stop work, and they must fire reliably rather than depending on
    keyword luck.
    """
    found = tokens(text)
    facts: list[PolicyFact] = []
    ai_usage = "knowledge-base/policies/ai-usage.md"

    people_words = {"hiring", "hire", "candidate", "candidates", "cv", "cvs",
                    "applicant", "applicants", "applications", "recruiting",
                    "recruitment", "performance", "promotion", "appraisal",
                    "dismissal", "employee", "employees", "staff", "worker",
                    "workers", "colleague", "colleagues"}
    decision_words = {"rank", "ranking", "score", "scoring", "screen",
                      "screening", "shortlist", "select", "selection",
                      "evaluate", "evaluating", "assess", "assessment",
                      "filter", "filtering", "monitor", "monitoring"}
    if found & people_words and found & decision_words:
        facts.append(PolicyFact(
            rule=("Decisions about people (hiring, performance, promotion, "
                  "dismissal) are never made or ranked by AI."),
            policy="Use of AI tools", cite=ai_usage, severity="blocks"))

    emotion_words = {"emotion", "emotions", "mood", "stress", "sentiment",
                     "engagement", "fatigue", "wellbeing", "webcam", "camera",
                     "microphone", "keystroke", "keystrokes"}
    if found & emotion_words and found & {"employee", "employees", "staff",
                                          "worker", "workers", "colleague",
                                          "colleagues", "team"}:
        facts.append(PolicyFact(
            rule=("Inferring emotion or stress of employees from camera, "
                  "microphone or keyboard data is not allowed."),
            policy="Use of AI tools", cite=ai_usage, severity="blocks"))

    if found & {"personal", "customer", "contract", "contracts", "candidate",
                "personnel", "gdpr"}:
        facts.append(PolicyFact(
            rule=("Personal data in an AI tool needs approval from the Data "
                  "Protection Officer (E113); a DPIA is required before new "
                  "large-scale processing of personal data."),
            policy="Data protection and classification",
            cite="knowledge-base/policies/data-protection.md",
            severity="requires_approval"))

    if found & {"customer", "customers", "reply", "replies", "email", "chatbot",
                "chat", "answer", "answers"}:
        facts.append(PolicyFact(
            rule="AI-generated text is never sent to a customer without a human reading it.",
            policy="Use of AI tools", cite=ai_usage, severity="requires_approval"))

    if found & {"cloud", "hosted", "hosting", "saas", "vendor", "supplier",
                "tool", "software", "platform"}:
        facts.append(PolicyFact(
            rule=("New software processing personal data needs approval from "
                  "E23, E113 and E09 whatever the price; customer data stays "
                  "in EU-hosted systems."),
            policy="Procurement and approvals",
            cite="knowledge-base/policies/procurement.md",
            severity="requires_approval"))
    return facts


def related_pain_points(conn: sqlite3.Connection, text: str,
                        limit: int = 4) -> list[PainPointMatch]:
    """Documented pain points this idea would address.

    A match is real evidence that the problem exists independently of the
    submitter, which raises scoring Confidence.
    """
    wanted = tokens(text)
    matches = []
    for row in conn.execute(
        "SELECT * FROM kg_node WHERE type = 'PainPoint'").fetchall():
        attrs = _attrs(row)
        overlap = len(wanted & tokens(row["name"]))
        if overlap >= 2:
            matches.append(PainPointMatch(
                department=attrs["department"], text=row["name"],
                overlap=overlap,
                cite=f"knowledge-base/departments/{attrs['department']}.md"))
    matches.sort(key=lambda m: -m.overlap)
    return matches[:limit]


def related_projects(conn: sqlite3.Connection, text: str,
                     limit: int = 3) -> list[dict]:
    """Active projects that may already cover this idea."""
    wanted = tokens(text)
    matches = []
    for row in conn.execute(
        "SELECT * FROM kg_node WHERE type = 'Project'").fetchall():
        attrs = _attrs(row)
        overlap = len(wanted & tokens(row["name"]))
        if overlap:
            matches.append({
                "id": row["id"].split(":")[1], "project": row["name"],
                "status": attrs["status"], "lead": attrs["lead"],
                "due": attrs["due"], "overlap": overlap,
                "cite": "knowledge-base/projects/active-projects.md"})
    matches.sort(key=lambda m: -m["overlap"])
    return matches[:limit]


def related_decisions(conn: sqlite3.Connection, text: str,
                      limit: int = 3) -> list[dict]:
    """Decisions already taken that bear on this idea."""
    wanted = tokens(text)
    matches = []
    for row in conn.execute(
        "SELECT * FROM kg_node WHERE type = 'Decision'").fetchall():
        attrs = _attrs(row)
        overlap = len(wanted & tokens(row["name"] + " " + attrs.get("reason", "")))
        if overlap >= 2:
            matches.append({"decision": row["name"], "date": attrs["date"],
                            "reason": attrs.get("reason", ""),
                            "overlap": overlap,
                            "cite": "knowledge-base/projects/decision-log.md"})
    matches.sort(key=lambda m: -m["overlap"])
    return matches[:limit]


def employee(conn: sqlite3.Connection, employee_id: str) -> dict | None:
    row = conn.execute("SELECT * FROM kg_node WHERE id = ?",
                       (f"employee:{employee_id}",)).fetchone()
    if row is None:
        return None
    return {"id": employee_id, "name": row["name"], **_attrs(row)}


def access_role(conn: sqlite3.Connection, employee_id: str) -> str:
    person = employee(conn, employee_id)
    return (person or {}).get("access_role", "employee")


def department_cost_per_day(conn: sqlite3.Connection,
                            department: str) -> int:
    row = conn.execute(
        "SELECT AVG(json_extract(attrs, '$.cost_per_day_eur')) FROM kg_node "
        "WHERE type = 'Employee' AND json_extract(attrs, '$.department') = ?",
        (department,)).fetchone()
    return int(row[0] or 500)


def company_day_rate(conn: sqlite3.Connection) -> int:
    row = conn.execute(
        "SELECT AVG(json_extract(attrs, '$.cost_per_day_eur')) FROM kg_node "
        "WHERE type = 'Employee'").fetchone()
    return int(row[0] or 500)


def stats(conn: sqlite3.Connection) -> dict[str, int]:
    return {
        "nodes": conn.execute("SELECT COUNT(*) FROM kg_node").fetchone()[0],
        "edges": conn.execute("SELECT COUNT(*) FROM kg_edge").fetchone()[0],
        "chunks": conn.execute("SELECT COUNT(*) FROM kb_chunk").fetchone()[0],
    }


if __name__ == "__main__":
    with db.session() as connection:
        print("stats:", stats(connection))
        print()
        for match in skills_available(connection, ["Python", "machine learning",
                                                   "test automation"]):
            print(f"{match.skill!r} -> {match.matched_name!r}: "
                  f"{match.holder_count} holders"
                  f"{' (bottleneck)' if match.is_bottleneck else ''}")
            for holder in match.holders[:3]:
                print(f"    {holder['employee_id']} {holder['name']} "
                      f"({holder['role']}, {holder['capacity_pct_available']}% free)")
        print()
        for fact in system_integrability(connection, ["Zendesk", "inventory spreadsheet",
                                                      "Salesforce"]):
            print(f"{fact.name}: found={fact.found} integrable={fact.integrable} "
                  f"api={fact.api_or_automation!r}")
        print()
        for fact in dataset_fitness(connection, ["support tickets categories"]):
            print(f"{fact.name}: {fact.quality} / {fact.volume} / "
                  f"personal={fact.personal_data}")
        print()
        print(capacity_outlook(connection, 24))
        print()
        print(budget_outlook(connection, 18_400))
        print()
        for policy in policy_constraints(connection,
                                         "screen and rank candidate CVs for hiring"):
            print(f"[{policy.severity}] {policy.rule}")
