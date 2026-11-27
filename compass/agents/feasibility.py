"""Can this company actually deliver this idea?

The split here is deliberate. A model is good at reading an idea and naming
what it would need - skills, systems, data. A model is bad at arithmetic
against a budget and should not be trusted to remember how many people hold a
skill. So:

    model (or offline rules)  ->  what the idea requires
    knowledge graph           ->  what we have, and the sums

Every dimension carries the knowledge base paths it was decided from, so a
board member can check any verdict rather than trusting it.
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import asdict

from .. import llm
from ..kg import query
from ..records import UseCaseRecord

VERDICTS = ["doable", "doable_with_constraints", "not_doable_now"]

SYSTEM = """\
You read a proposed internal use case and name what delivering it would
require. You do NOT judge whether the company can do it - another step does
that against real data.

Return JSON only:
{
  "required_skills": ["skill names, as an engineer would name them"],
  "required_systems": ["systems that must be read from or written to"],
  "data_topics": ["the data it needs, in the submitter's terms"],
  "est_person_days": number or null,
  "people_required": number or null,
  "external_spend_eur": number or null,
  "delivery_steps": ["3 to 6 steps to deliver it"],
  "assumptions": ["anything you had to assume"],
  "open_questions": ["what you would need to ask to firm this up"]
}

Rules:
- If the submitter gave an effort figure, use it and do not change it. If they
  gave none, you may estimate, but then add an assumption saying the estimate
  is yours, not theirs.
- Name skills the way they appear on a CV: "Python", "data modelling", "test
  automation", "technical writing". Do not invent exotic skills.
- Only list systems the submission actually implies.
- Keep estimates honest. Most internal tools are 10 to 40 person-days; a
  migration or anything touching hardware is more.
"""

# Task shape -> skills usually needed. Used by the offline extractor.
SKILL_HINTS: list[tuple[set[str], list[str]]] = [
    ({"classify", "classification", "categorise", "categorize", "route",
      "routing", "triage", "predict", "detect", "anomaly"},
     ["Python", "data modelling"]),
    ({"search", "knowledge", "question", "questions", "answer", "answers",
      "document", "documents", "article", "articles", "retrieve"},
     ["Python", "data modelling", "technical writing"]),
    ({"draft", "write", "generate", "summarise", "summarize", "translate",
      "translation", "content", "copywriting"},
     ["technical writing", "Python"]),
    ({"dashboard", "report", "reporting", "kpi", "figures", "analytics",
      "analysis"},
     ["SQL", "data visualisation", "data modelling"]),
    ({"integration", "integrate", "sync", "api", "export", "import",
      "transfer", "copy", "retype", "retyped", "pipeline"},
     ["Python", "integrations", "data modelling"]),
    ({"dashboard", "interface", "screen", "form", "ui", "portal", "web"},
     ["TypeScript", "React"]),
    ({"firmware", "sensor", "device", "calibration", "rig", "hardware"},
     ["C", "sensor calibration", "test rigs"]),
    ({"warehouse", "dbt", "model", "etl"}, ["dbt", "data modelling", "SQL"]),
    ({"security", "access", "identity", "iso", "audit"},
     ["information security", "identity management"]),
    ({"gdpr", "personal", "dpia", "protection"}, ["GDPR"]),
]

EFFORT_PATTERNS = [
    (r"(\d+(?:[.,]\d+)?)\s*(?:person[- ])?day", 1.0),
    (r"(\d+(?:[.,]\d+)?)\s*week", 5.0),
    (r"(\d+(?:[.,]\d+)?)\s*month", 20.0),
    (r"(\d+(?:[.,]\d+)?)\s*sprint", 10.0),
]


def parse_effort(text: str) -> int | None:
    """A person-day figure from free text like 'about three weeks'."""
    lowered = (text or "").lower()
    words = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
             "half": 0.5, "a": 1, "an": 1, "couple": 2, "few": 3}
    for word, number in words.items():
        # "of" is optional so that "a couple of days" parses as well as
        # "a couple days" - people write both.
        lowered = re.sub(
            rf"\b{word}\b(?:\s+of)?(?=\s+(?:person[- ])?"
            rf"(?:day|week|month|sprint))",
            str(number), lowered)
    for pattern, multiplier in EFFORT_PATTERNS:
        match = re.search(pattern, lowered)
        if match:
            value = float(match.group(1).replace(",", "."))
            return max(1, round(value * multiplier))
    return None


def parse_people(text: str) -> int | None:
    match = re.search(r"(\d+)\s*(?:people|persons?|developers?|engineers?|"
                      r"colleagues?|staff)", (text or "").lower())
    if match:
        return int(match.group(1))
    words = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5}
    for word, number in words.items():
        if re.search(rf"\b{word}\s+(?:people|persons?|developers?|engineers?)",
                     (text or "").lower()):
            return number
    return None


def parse_spend(text: str) -> int | None:
    match = re.search(r"(?:eur|€)\s*([\d.,]+)\s*(k|thousand)?", (text or "").lower())
    if not match:
        return None
    value = float(match.group(1).replace(".", "").replace(",", "."))
    if match.group(2):
        value *= 1000
    return int(value)


def offline_extract(record: UseCaseRecord, conn: sqlite3.Connection) -> dict:
    text = record.searchable_text().lower()
    found = query.tokens(text)

    skills: list[str] = []
    for cues, suggested in SKILL_HINTS:
        if found & cues:
            skills.extend(suggested)
    seen: dict[str, None] = {}
    for skill in skills:
        seen.setdefault(skill, None)

    systems = [r["name"] for r in conn.execute(
        "SELECT name FROM kg_node WHERE type = 'System'").fetchall()
        if r["name"].lower() in text]

    datasets = [d.name for d in query.dataset_fitness(
        conn, [record.value("data") or text], limit=3)]

    effort_text = record.value("effort")
    person_days = parse_effort(effort_text)
    assumptions = []
    if person_days is None:
        # Deliberately coarse, and labelled as the agent's own guess.
        person_days = 20 if not systems else 15 + 10 * len(systems)
        assumptions.append(
            f"The submitter gave no effort figure. {person_days} person-days is "
            f"the agent's own rough estimate from the scope, not theirs.")

    people = parse_people(effort_text) or min(3, max(1, len(list(seen)) // 2 or 1))
    if not parse_people(effort_text):
        assumptions.append(
            f"People required ({people}) estimated by the agent from the skills "
            f"involved.")

    return {
        "required_skills": list(seen)[:6],
        "required_systems": systems,
        "data_topics": datasets,
        "est_person_days": person_days,
        "people_required": people,
        "external_spend_eur": parse_spend(effort_text),
        "delivery_steps": [],
        "assumptions": assumptions,
        "open_questions": [],
    }


# --------------------------------------------------------------------------- #
# deterministic scoring of the extracted requirements
# --------------------------------------------------------------------------- #
def _skills_dimension(conn: sqlite3.Connection, wanted: list[str]) -> dict:
    matches = query.skills_available(conn, wanted)
    gaps = [m.skill for m in matches if m.holder_count == 0]
    bottlenecks = [m.skill for m in matches if m.is_bottleneck]

    if not matches:
        status = "unknown"
    elif gaps and len(gaps) == len(matches):
        status = "weak"
    elif gaps:
        status = "partial"
    elif bottlenecks:
        status = "partial"
    else:
        status = "ok"

    note_parts = []
    if gaps:
        note_parts.append(f"No one holds: {', '.join(gaps)}.")
    if bottlenecks:
        note_parts.append(
            f"Held by three or fewer people: {', '.join(bottlenecks)}.")
    if not note_parts:
        note_parts.append("All required skills are available in-house.")

    return {
        "status": status,
        "required": wanted,
        "available": [
            {"skill": m.skill, "matched": m.matched_name,
             "holders": m.holder_count,
             "examples": [f"{h['employee_id']} {h['name']} "
                          f"({h['role']}, {h['capacity_pct_available']}% free)"
                          for h in m.holders[:3]]}
            for m in matches if m.holder_count
        ],
        "gap": gaps,
        "bottlenecks": bottlenecks,
        "note": " ".join(note_parts),
        "cites": ["knowledge-base/people/employees.csv",
                  "knowledge-base/people/capacity.csv"],
    }


def _systems_dimension(conn: sqlite3.Connection, wanted: list[str]) -> dict:
    facts = query.system_integrability(conn, wanted)
    unreachable = [f.name for f in facts if f.found and not f.integrable]
    unknown = [f.name for f in facts if not f.found]

    if not facts:
        status, note = "unknown", "No systems were named, so this is unchecked."
    elif unreachable:
        status = "weak"
        note = (f"{', '.join(unreachable)} has no API or automation route, so "
                f"the data must be migrated or exported manually first.")
    elif unknown:
        status = "partial"
        note = f"Not in our system list: {', '.join(unknown)}. Would be new tooling."
    else:
        status = "ok"
        note = "Every system needed is reachable by API or scheduled export."

    return {
        "status": status,
        "required": wanted,
        "integrable": [
            {"system": f.name, "api": f.api_or_automation, "owner": f.owner_id,
             "personal_data": f.personal_data,
             "in_data_warehouse": f.in_data_warehouse}
            for f in facts if f.found
        ],
        "gap": unreachable + unknown,
        "note": note,
        "cites": ["knowledge-base/it/systems.md"],
    }


def _data_dimension(conn: sqlite3.Connection, topics: list[str]) -> dict:
    facts = query.dataset_fitness(conn, topics or ["unspecified"], limit=4)
    if not facts:
        return {"status": "weak", "datasets": [], "gap": topics,
                "note": ("No dataset in the data inventory matches what this "
                         "needs. The data would have to be captured first."),
                "cites": ["knowledge-base/it/data-inventory.md"]}

    low = [f.name for f in facts if f.quality.startswith("low")]
    usable = [f for f in facts if f.usable_as_is]
    personal = [f.name for f in facts if f.personal_data.startswith("yes")]

    # Relevance decides, then quality. dataset_fitness returns the most
    # topically relevant first, and THAT is the dataset the idea would have to
    # be built on - so its quality sets the status. Picking the
    # highest-quality match instead would report a barely-related medium
    # dataset as "best available" and hide that the data the idea actually
    # needs is unusable, which is exactly the finding that matters.
    grades = {"high": 3, "medium": 2, "low": 1}
    primary = facts[0]
    status = {3: "ok", 2: "partial", 1: "weak"}[
        grades.get(primary.quality.split()[0], 1)]

    notes = [f"Would be built on {primary.name} "
             f"({primary.quality_note}, {primary.volume})."]
    better = [f for f in facts[1:]
              if grades.get(f.quality.split()[0], 1) >
              grades.get(primary.quality.split()[0], 1)]
    if better:
        notes.append(f"Higher-quality related data exists "
                     f"({', '.join(f.name for f in better)}), which may be "
                     f"worth checking.")
    if low and primary.name not in low:
        notes.append(f"Also matched, but low quality: {', '.join(low)}.")
    if personal:
        notes.append(f"Contains personal data: {', '.join(personal)}. "
                     f"Needs E113 approval.")

    return {
        "status": status,
        "datasets": [asdict(f) for f in facts],
        "gap": low,
        "note": " ".join(notes) or "Data of mixed quality is available.",
        "cites": ["knowledge-base/it/data-inventory.md"],
    }


def _compliance_dimension(conn: sqlite3.Connection, text: str) -> dict:
    policies = query.policy_constraints(conn, text)
    blocking = [p for p in policies if p.severity == "blocks"]
    approvals = [p for p in policies if p.severity == "requires_approval"]

    if blocking:
        status = "blocked"
        note = "Company policy forbids this: " + " ".join(p.rule for p in blocking)
    elif approvals:
        status = "attention"
        note = ("Allowed with approval: "
                + " ".join(p.rule for p in approvals))
    else:
        status = "ok"
        note = "No policy rule matched this idea."

    return {"status": status,
            "rules": [{"rule": p.rule, "policy": p.policy, "cite": p.cite,
                       "severity": p.severity} for p in policies],
            "note": note,
            "cites": sorted({p.cite for p in policies}) or
                     ["knowledge-base/policies/ai-usage.md"]}


def _strategy_dimension(conn: sqlite3.Connection, text: str) -> dict:
    priorities = query.strategy_alignment(conn, text)
    pains = query.related_pain_points(conn, text)
    projects = query.related_projects(conn, text)
    decisions = query.related_decisions(conn, text)

    if priorities:
        status = "aligned"
        note = ("Supports priority " +
                ", ".join(f"{p.number} ({p.priority})" for p in priorities))
    elif pains:
        status = "supported"
        note = ("No direct strategy priority, but it addresses a documented "
                "pain point in " + ", ".join(sorted({p.department for p in pains})))
    else:
        status = "unclear"
        note = ("No strategy priority or documented pain point matched. May "
                "still be worth doing, but the case rests on the submitter's "
                "account alone.")

    if projects:
        note += (". Overlaps active work: " +
                 ", ".join(f"{p['id']} {p['project']} ({p['status']})"
                           for p in projects))
    if decisions:
        note += (". Related decision already taken: " +
                 "; ".join(f"{d['date']} {d['decision']}" for d in decisions))

    return {
        "status": status,
        "priorities": [asdict(p) for p in priorities],
        "pain_points": [asdict(p) for p in pains],
        "active_projects": projects,
        "decisions": decisions,
        "note": note,
        "cites": sorted({p.cite for p in priorities} |
                        {p.cite for p in pains} |
                        {p["cite"] for p in projects}) or
                 ["knowledge-base/company/strategy-2027.md"],
    }


# Worst status wins. A single blocked or weak dimension is what a board needs
# to see, not an average that hides it.
RANK = {"blocked": 0, "weak": 1, "partial": 2, "unknown": 2, "attention": 2,
        "tight": 2, "supported": 3, "unclear": 3, "aligned": 4, "ok": 4,
        "needs_board": 2, "over": 1}


def assess(record: UseCaseRecord, conn: sqlite3.Connection) -> tuple[dict, str]:
    text = record.searchable_text()

    extracted, model = llm.generate_json(
        SYSTEM, record.as_prompt_block(),
        offline=lambda: offline_extract(record, conn),
        required_keys=("required_skills", "required_systems", "est_person_days"),
    )
    # The model may omit or mistype numbers; fall back to the parsed values.
    fallback = offline_extract(record, conn)
    for key in ("required_skills", "required_systems", "data_topics"):
        if not isinstance(extracted.get(key), list):
            extracted[key] = fallback[key]
    person_days = extracted.get("est_person_days")
    if not isinstance(person_days, (int, float)) or person_days <= 0:
        person_days = fallback["est_person_days"]
    person_days = int(person_days)
    people = extracted.get("people_required")
    if not isinstance(people, (int, float)) or people <= 0:
        people = fallback["people_required"]
    people = int(people)
    external = extracted.get("external_spend_eur") or 0
    if not isinstance(external, (int, float)) or external < 0:
        external = 0

    data_topics = ([record.value("data")] if record.get("data").is_usable
                   else list(extracted["data_topics"]) or [text])

    day_rate = (query.department_cost_per_day(conn, record.department)
                if record.department else query.company_day_rate(conn))
    est_cost = int(person_days * day_rate + external)

    dimensions = {
        "skills": _skills_dimension(conn, extracted["required_skills"]),
        "systems": _systems_dimension(conn, extracted["required_systems"]),
        # The submitter's own description of the data, alone, when they gave
        # one. Mixing in dataset names from the extraction pass drags their
        # tokens into the query and lets an irrelevant dataset win on a tie -
        # it once made "CRM deals and notes" outrank "Site survey notes" for
        # an idea about site survey notes. Extracted topics are the fallback
        # only when the field is empty.
        "data": _data_dimension(conn, data_topics),
        "capacity": {**asdict(query.capacity_outlook(conn, person_days))},
        "budget": {**asdict(query.budget_outlook(conn, est_cost))},
        "compliance": _compliance_dimension(conn, text),
        "strategy": _strategy_dimension(conn, text),
    }

    worst = min(RANK.get(d.get("status", "unknown"), 2)
                for d in dimensions.values())
    if not record.get("problem").is_usable and \
            not record.get("intended_purpose").is_usable:
        # Nothing to assess. Saying "unknown" is honest; saying "doable" is not.
        verdict = "unknown"
    elif dimensions["compliance"]["status"] == "blocked":
        verdict = "not_doable_now"
    elif worst <= 1:
        verdict = "not_doable_now"
    elif worst <= 2:
        verdict = "doable_with_constraints"
    else:
        verdict = "doable"

    blockers = [f"{name}: {d['note']}"
                for name, d in dimensions.items()
                if RANK.get(d.get("status", "unknown"), 2) <= 1]

    payload = {
        "verdict": verdict,
        "est_person_days": person_days,
        "people_required": people,
        "est_cost_eur": est_cost,
        "day_rate_eur": day_rate,
        "external_spend_eur": int(external),
        "dimensions": dimensions,
        "blockers": blockers,
        "delivery_steps": extracted.get("delivery_steps") or [],
        "assumptions": extracted.get("assumptions") or [],
        "open_questions": extracted.get("open_questions") or [],
        "effort_source": ("submitter" if parse_effort(record.value("effort"))
                          else "agent estimate"),
    }
    return payload, model
