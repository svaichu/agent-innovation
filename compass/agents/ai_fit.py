"""Is AI the right tool, or would conventional automation do?

The brief asks for this explicitly, and it is the finding clients least expect:
a good share of "AI ideas" are integration work. Saying so is more valuable
than scoring them.

Verdicts
    ai                      - needs to interpret language, images or messy input
    conventional_automation - deterministic: rules, a field mapping, an API call
    hybrid                  - deterministic plumbing with one judgement step
    more_research           - cannot tell yet, usually because the data is unfit
"""

from __future__ import annotations

import sqlite3

from .. import llm
from ..kg import query
from ..records import UseCaseRecord

VERDICTS = ["ai", "conventional_automation", "hybrid", "more_research"]

SYSTEM = """\
You decide whether a proposed internal use case genuinely needs AI.

Return JSON only:
{
  "verdict": "ai" | "conventional_automation" | "hybrid" | "more_research",
  "confidence": "high" | "medium" | "low",
  "reasoning": "two or three sentences",
  "why_not_simpler": "if verdict is ai or hybrid: what a rules-based version could not do",
  "simpler_alternative": "if verdict is conventional_automation or hybrid: the concrete non-AI approach",
  "signals": ["short phrases from the submission that drove the verdict"],
  "gaps": ["information that would change this verdict"]
}

How to decide:
- conventional_automation when the work is deterministic: moving data between
  two systems, a field mapping, a scheduled report, a validation rule, a
  reminder. If a competent developer could write the rules out in full, it is
  not an AI problem.
- ai when the input is unstructured and needs interpretation: free text,
  images, speech, messy categories, ranking by relevance, drafting language,
  answering questions over documents.
- hybrid when most of the work is plumbing and exactly one step needs
  judgement. Say which step.
- more_research when the required data does not exist, is of low quality, or
  the purpose is too vague to judge.

Rules:
- Judge the task, not the submitter's enthusiasm. People often label
  integration work as AI.
- Never invent facts about systems or data. Use only the record and the
  knowledge base facts given to you.
- If a system has no API, saying so is more important than the verdict: it
  blocks either approach until the data moves somewhere reachable.

Worked examples:

Record: "Order data is retyped from HubSpot into the inventory spreadsheet,
about 180 orders per month. It should be copied automatically."
-> {"verdict": "conventional_automation", "confidence": "high",
    "reasoning": "The fields are known and the mapping is fixed. Nothing has to
    be interpreted, so this is an integration, not a model.",
    "simpler_alternative": "A scheduled job reading the HubSpot deals API and
    writing rows to whatever replaces the inventory spreadsheet.",
    "signals": ["retyped", "180 orders per month", "fixed fields"],
    "gaps": ["The inventory spreadsheet has no API, so it must be migrated first."]}

Record: "About 40% of our 1,250 monthly tickets are repeat questions. Route
them and draft a first reply."
-> {"verdict": "ai", "confidence": "high",
    "reasoning": "Tickets arrive as free text in two languages and the
    categories are inconsistent, so routing needs interpretation rather than
    keyword rules. Drafting a reply is language generation.",
    "why_not_simpler": "Keyword rules were the previous approach and failed
    because customers describe the same fault in many ways.",
    "signals": ["free text", "categories inconsistent", "draft a reply"],
    "gaps": []}
"""

# --- offline rules ---------------------------------------------------------
# Signals that the input needs interpreting.
UNSTRUCTURED = {
    "ticket", "tickets", "email", "emails", "text", "document", "documents",
    "article", "articles", "note", "notes", "comment", "comments", "question",
    "questions", "answer", "answers", "tender", "tenders", "description",
    "summarise", "summarize", "summary", "translate", "translation",
    "classify", "classification", "categorise", "categorize", "category",
    "draft", "drafting", "write", "writing", "search", "knowledge",
    "language", "handwritten", "image", "images", "photo", "voice", "speech",
    "sentiment", "intent", "unstructured", "free-text", "relevance",
}

# Signals that the work is a deterministic transfer or rule.
DETERMINISTIC = {
    "retype", "retyped", "retyping", "copy", "copied", "copying", "paste",
    "transfer", "sync", "synchronise", "synchronize", "export", "import",
    "reconcile", "reconciliation", "mapping", "integration", "integrate",
    "duplicate", "twice", "manually enter", "manual entry", "spreadsheet",
    "scheduled", "reminder", "threshold", "validation", "checklist",
    "dashboard", "report", "reporting", "alert", "alerts",
}

# Signals that judgement is needed on top of plumbing.
JUDGEMENT = {
    "decide", "decision", "prioritise", "prioritize", "rank", "ranking",
    "recommend", "recommendation", "predict", "prediction", "forecast",
    "estimate", "detect", "anomaly", "similar", "match", "matching",
    "suggest", "triage", "route", "routing", "score", "scoring",
}


def _words(record: UseCaseRecord) -> set[str]:
    return query.tokens(record.searchable_text()) | {
        w for w in record.searchable_text().lower().split()
    }


def offline_rules(record: UseCaseRecord, conn: sqlite3.Connection) -> dict:
    text = record.searchable_text().lower()
    found = _words(record)

    unstructured = sorted(found & UNSTRUCTURED)
    deterministic = sorted(found & DETERMINISTIC)
    judgement = sorted(found & JUDGEMENT)

    # Blocking fact first: an unreachable system stops both approaches.
    gaps: list[str] = []
    for fact in query.system_integrability(conn, _mentioned_systems(conn, text)):
        if fact.found and not fact.integrable:
            gaps.append(
                f"{fact.name} has no API or automation route "
                f"(knowledge-base/it/systems.md), so the data must be moved "
                f"before either approach can work.")

    datasets = query.dataset_fitness(conn, [text], limit=3)
    weak_data = [d for d in datasets if d.quality.startswith("low")]
    # Retrieval returns topical neighbours, so a weak one often sits beside a
    # good one. Only the absence of any usable dataset is a real blocker.
    usable_data = [d for d in datasets if not d.quality.startswith("low")]

    if not record.get("intended_purpose").is_usable:
        return {
            "verdict": "more_research",
            "confidence": "low",
            "reasoning": ("The intended purpose was not provided, so there is "
                          "nothing to judge. Asked of the submitter rather "
                          "than guessed."),
            "simpler_alternative": "",
            "why_not_simpler": "",
            "signals": [],
            "gaps": ["intended_purpose is missing"] + gaps,
        }

    if deterministic and not unstructured:
        return {
            "verdict": "conventional_automation",
            "confidence": "high" if len(deterministic) >= 2 else "medium",
            "reasoning": ("The described work is a deterministic transfer or "
                          "rule: " + ", ".join(deterministic[:4]) + ". The "
                          "fields and the logic are known in advance, so no "
                          "model is needed."),
            "simpler_alternative": ("A scheduled integration or rule in the "
                                    "existing systems."),
            "why_not_simpler": "",
            "signals": deterministic[:6],
            # Poor quality in the data being moved is a caveat here, not a
            # blocker: moving it correctly is usually the point.
            "gaps": gaps + [f"{d.name}: {d.quality_note}" for d in weak_data],
        }

    # Only now does weak data veto: an idea that has to LEARN from the data
    # cannot proceed if that data is not fit, unlike one that merely moves it.
    if weak_data and not usable_data and (unstructured or judgement):
        return {
            "verdict": "more_research",
            "confidence": "medium",
            "reasoning": (f"This would have to learn from data that is not fit "
                          f"for it: {weak_data[0].name} is recorded as "
                          f"'{weak_data[0].quality_note}'. How the data is "
                          f"captured has to change first."),
            "simpler_alternative": "Fix the data capture before building anything.",
            "why_not_simpler": "",
            "signals": sorted(set(unstructured + judgement))[:6],
            "gaps": gaps + [f"{d.name}: {d.quality_note}" for d in weak_data],
        }

    if unstructured and deterministic:
        return {
            "verdict": "hybrid",
            "confidence": "medium",
            "reasoning": ("Most of this is plumbing between existing systems, "
                          "with one step that needs interpretation of "
                          "unstructured input: " + ", ".join(unstructured[:3]) + "."),
            "simpler_alternative": ("Build the integration first and add the "
                                    "judgement step only if the rules prove "
                                    "insufficient."),
            "why_not_simpler": ("The interpretation step cannot be written out "
                                "as fixed rules."),
            "signals": sorted(set(unstructured[:3] + deterministic[:3])),
            "gaps": gaps,
        }

    if unstructured or judgement:
        return {
            "verdict": "ai",
            "confidence": "high" if len(unstructured) >= 3 else "medium",
            "reasoning": ("The input is unstructured and has to be interpreted "
                          "rather than matched: " +
                          ", ".join(sorted(set(unstructured + judgement))[:5]) +
                          ". Fixed rules would miss the variation."),
            "simpler_alternative": "",
            "why_not_simpler": ("The same meaning arrives in many different "
                                "wordings, which keyword rules do not cover."),
            "signals": sorted(set(unstructured + judgement))[:6],
            "gaps": gaps,
        }

    return {
        "verdict": "more_research",
        "confidence": "low",
        "reasoning": ("The description does not say clearly enough what would "
                      "be automated or interpreted."),
        "simpler_alternative": "",
        "why_not_simpler": "",
        "signals": [],
        "gaps": gaps + ["The purpose is too vague to classify."],
    }


def _mentioned_systems(conn: sqlite3.Connection, text: str) -> list[str]:
    """System names that actually appear in the text."""
    rows = conn.execute(
        "SELECT name FROM kg_node WHERE type = 'System'").fetchall()
    return [r["name"] for r in rows if r["name"].lower() in text]


def assess(record: UseCaseRecord, conn: sqlite3.Connection) -> tuple[dict, str]:
    systems = _mentioned_systems(conn, record.searchable_text().lower())
    facts = query.system_integrability(conn, systems) if systems else []
    datasets = query.dataset_fitness(conn, [record.searchable_text()], limit=3)

    context = ["Knowledge base facts (the only external facts you may use):"]
    for fact in facts:
        context.append(f"- system {fact.name}: api_or_automation="
                       f"{fact.api_or_automation}, integrable={fact.integrable}")
    for dataset in datasets:
        context.append(f"- dataset {dataset.name}: quality={dataset.quality_note}, "
                       f"volume={dataset.volume}, personal_data={dataset.personal_data}")
    if len(context) == 1:
        context.append("- none matched")

    user = f"{record.as_prompt_block()}\n\n" + "\n".join(context)
    payload, model = llm.generate_json(
        SYSTEM, user,
        offline=lambda: offline_rules(record, conn),
        required_keys=("verdict", "reasoning"),
    )
    if payload.get("verdict") not in VERDICTS:
        payload = offline_rules(record, conn)
        model = llm.OFFLINE_MODEL + " (invalid verdict from model)"
    return payload, model
