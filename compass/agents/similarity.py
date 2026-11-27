"""Find ideas from other teams that solve substantially the same problem.

Retrieval is deterministic TF-IDF cosine, so it works with no API key and is
reproducible. A model is then asked only to judge the shortlist, which is the
part that needs reading comprehension: "deflect repeat tickets with a help
centre search" and "answer tender questions from past responses" are the same
machine behind two different front doors.

Pairs are stored once, with the lexically smaller id first, so a link is never
duplicated.
"""

from __future__ import annotations

import math
import sqlite3
from collections import Counter
from dataclasses import dataclass

from .. import db, llm
from ..kg import query
from ..records import UseCaseRecord

# Below this combined score, do not even ask: the ideas share nothing real.
# Tuned on the seeded portfolio. Raw cosine alone fails both ways here: ideas
# from one company share plenty of vocabulary ("ticket", "customer", "month")
# without sharing a problem, while the overlaps that matter most are phrased in
# completely different words - answering tender questions and deflecting
# support tickets are the same machine, and their cosine is only 0.15.
SHORTLIST_THRESHOLD = 0.28
# At or above this, call it a duplicate without a model.
STRONG_THRESHOLD = 0.55

# Capability signatures: what an idea would actually need BUILT, independent of
# the department's vocabulary. Two ideas sharing a signature are candidates to
# build once and scope twice, which is the finding the brief is really after.
CAPABILITIES: dict[str, set[str]] = {
    "document_search": {
        "search", "find", "retrieve", "lookup", "knowledge", "article",
        "articles", "document", "documents", "past", "previous", "reuse",
        "help centre", "confluence", "policy", "policies", "question",
        "questions", "answer", "answers", "hunting",
    },
    "text_drafting": {
        "draft", "drafts", "drafting", "write", "writing", "written", "reply",
        "replies", "generate", "summarise", "summarize", "summary",
        "commentary", "translate", "translation", "notes", "copy", "text",
        "wording",
    },
    "classification": {
        "classify", "categorise", "categorize", "category", "categories",
        "route", "routing", "tag", "tagging", "label", "labels", "triage",
        "priority", "queue", "group", "grouping", "sort",
    },
    "data_transfer": {
        "retype", "retyped", "retyping", "transfer", "sync", "synchronise",
        "integration", "integrate", "export", "import", "copied", "copying",
        "entry", "enter", "keyed", "load", "loads", "pipeline", "reconcile",
    },
    "extraction": {
        "extract", "parse", "structure", "structured", "photo", "photos",
        "form", "forms", "invoice", "invoices", "scan", "transcribe",
        "transcription", "dictate", "handwritten", "pdf", "read",
    },
    "forecasting": {
        "predict", "prediction", "forecast", "likelihood", "likely",
        "at-risk", "anomaly", "trend", "early", "precedes", "churn",
        "estimate", "reorder",
    },
    "people_assessment": {
        "candidate", "candidates", "cv", "cvs", "application", "applications",
        "applicant", "recruit", "recruiting", "performance", "appraisal",
        "employee", "employees", "colleague", "colleagues", "staff",
    },
    "monitoring": {
        "monitor", "monitoring", "alert", "alerts", "threshold", "thresholds",
        "health", "outage", "failure", "warning", "detect", "flag", "flags",
    },
    "reporting": {
        "dashboard", "report", "reporting", "figures", "metrics", "kpi",
        "view", "overview", "briefing", "visibility",
    },
}


def capabilities(record: UseCaseRecord) -> set[str]:
    """Which capabilities this idea would need built."""
    words = query.tokens(record.searchable_text())
    text = record.searchable_text().lower()
    found = set()
    for name, cues in CAPABILITIES.items():
        if words & cues or any(" " in c and c in text for c in cues):
            found.add(name)
    # people_assessment only counts when the idea actually assesses people.
    if "people_assessment" in found and not (
            words & {"rank", "ranking", "score", "scoring", "screen",
                     "screening", "evaluate", "assess", "shortlist"}):
        found.discard("people_assessment")
    return found


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)

VERDICTS = ["duplicate", "related", "distinct"]

SYSTEM = """\
You judge whether two internal improvement ideas overlap.

Return JSON only:
{
  "verdict": "duplicate" | "related" | "distinct",
  "similarity_reason": "one or two sentences",
  "shared_capability": "the thing both would need built, or null",
  "recommendation": "merge" | "link" | "keep separate",
  "who_should_talk": ["department names"]
}

Definitions:
- duplicate: the same problem and the same solution. One piece of work would
  serve both. Usually two departments that never spoke.
- related: different problems that would be solved by the same underlying
  capability - for example two teams each wanting search over their own
  documents. Worth building once, scoped twice.
- distinct: superficial word overlap only.

Judge the underlying capability, not the vocabulary. Two ideas phrased very
differently can be duplicates, and two using identical words can be distinct.
"""


@dataclass
class Overlap:
    a_id: str
    b_id: str
    similarity: float
    verdict: str
    rationale: str
    shared_capability: str = ""
    recommendation: str = ""


def _vector(text: str) -> Counter:
    return Counter(query.tokens(text))


def _cosine(a: Counter, b: Counter, idf: dict[str, float]) -> float:
    shared = set(a) & set(b)
    if not shared:
        return 0.0
    numerator = sum(a[t] * b[t] * idf.get(t, 1.0) ** 2 for t in shared)
    norm_a = math.sqrt(sum((c * idf.get(t, 1.0)) ** 2 for t, c in a.items()))
    norm_b = math.sqrt(sum((c * idf.get(t, 1.0)) ** 2 for t, c in b.items()))
    if not norm_a or not norm_b:
        return 0.0
    return numerator / (norm_a * norm_b)


def shortlist(record: UseCaseRecord, others: list[UseCaseRecord],
              limit: int = 4) -> list[tuple[UseCaseRecord, float]]:
    """Nearest other ideas by TF-IDF cosine."""
    corpus = [record] + others
    vectors = {r.id: _vector(r.searchable_text()) for r in corpus}

    frequencies = Counter()
    for vector in vectors.values():
        frequencies.update(set(vector))
    total = len(corpus)
    idf = {term: math.log(1 + total / (1 + count))
           for term, count in frequencies.items()}

    mine = capabilities(record)
    scored = []
    for other in others:
        if other.id == record.id:
            continue
        lexical = _cosine(vectors[record.id], vectors[other.id], idf)
        shared = _jaccard(mine, capabilities(other))
        # Weighted so that a shared capability can surface a pair the wording
        # hides, without letting common vocabulary alone create a link.
        scored.append((other, 0.6 * lexical + 0.4 * shared))

    scored.sort(key=lambda item: -item[1])
    return [(other, round(score, 3)) for other, score in scored[:limit]
            if score >= SHORTLIST_THRESHOLD]


def offline_verdict(similarity: float, a: UseCaseRecord,
                    b: UseCaseRecord) -> dict:
    shared_caps = sorted(capabilities(a) & capabilities(b))
    shared_words = sorted(query.tokens(a.searchable_text()) &
                          query.tokens(b.searchable_text()))[:6]
    capability_text = ", ".join(c.replace("_", " ") for c in shared_caps)
    cross_team = a.department != b.department and a.department and b.department

    if similarity >= STRONG_THRESHOLD and len(shared_caps) >= 2:
        verdict, recommendation = "duplicate", "merge"
        reason = (f"Both need the same capabilities built ({capability_text}) "
                  f"and describe the same work. One piece of work would serve "
                  f"both.")
    elif len(shared_caps) >= 2:
        verdict, recommendation = "related", "link"
        reason = (f"Different problems, same underlying capability: "
                  f"{capability_text}. Worth building once and scoping twice"
                  + (f", and the two sit in different departments "
                     f"({a.department} and {b.department}), so neither team "
                     f"is likely to know about the other." if cross_team
                     else ".") )
    else:
        verdict, recommendation = "distinct", "keep separate"
        reason = (f"Only shared vocabulary ({', '.join(shared_words)})"
                  + (f" and one shared capability ({capability_text})"
                     if shared_caps else " and no shared capability")
                  + ". Not enough to link.")
    return {
        "verdict": verdict,
        "similarity_reason": reason,
        "shared_capability": capability_text or None,
        "recommendation": recommendation,
        "who_should_talk": sorted({a.department, b.department} - {""}),
    }


def judge(a: UseCaseRecord, b: UseCaseRecord,
          similarity: float) -> tuple[dict, str]:
    user = (f"Idea A\n{a.as_prompt_block()}\n\n"
            f"Idea B\n{b.as_prompt_block()}\n\n"
            f"Lexical similarity: {similarity:.2f}")
    payload, model = llm.generate_json(
        SYSTEM, user,
        offline=lambda: offline_verdict(similarity, a, b),
        required_keys=("verdict", "similarity_reason"),
    )
    if payload.get("verdict") not in VERDICTS:
        payload = offline_verdict(similarity, a, b)
        model = llm.OFFLINE_MODEL + " (invalid verdict from model)"
    return payload, model


def assess(record: UseCaseRecord, others: list[UseCaseRecord],
           conn: sqlite3.Connection) -> tuple[dict, str]:
    candidates = shortlist(record, others)
    overlaps: list[dict] = []
    model_used = llm.OFFLINE_MODEL

    for other, similarity in candidates:
        verdict, model_used = judge(record, other, similarity)
        if verdict["verdict"] == "distinct":
            continue
        overlaps.append({
            "other_id": other.id,
            "other_title": other.title,
            "other_department": other.department,
            "similarity": similarity,
            **verdict,
        })
        store(conn, record.id, other.id, similarity, verdict)

    projects = query.related_projects(conn, record.searchable_text())

    return {
        "overlaps": overlaps,
        "checked_against": len(others),
        "shortlisted": len(candidates),
        "active_project_overlap": projects,
        "note": (f"Compared against {len(others)} existing ideas; "
                 f"{len(overlaps)} link(s) suggested."
                 + (f" Also overlaps active work: "
                    f"{', '.join(p['id'] for p in projects)}." if projects else "")),
    }, model_used


def store(conn: sqlite3.Connection, a_id: str, b_id: str, similarity: float,
          verdict: dict) -> None:
    first, second = sorted([a_id, b_id])
    conn.execute(
        "INSERT INTO overlaps (a_id, b_id, similarity, verdict, rationale, "
        "status, created_at) VALUES (?, ?, ?, ?, ?, 'suggested', ?) "
        "ON CONFLICT(a_id, b_id) DO UPDATE SET "
        "similarity = excluded.similarity, verdict = excluded.verdict, "
        "rationale = excluded.rationale",
        (first, second, similarity, verdict["verdict"],
         verdict.get("similarity_reason", ""), db.now()),
    )


def links_for(conn: sqlite3.Connection, use_case_id: str) -> list[dict]:
    rows = conn.execute(
        "SELECT o.*, "
        "  CASE WHEN o.a_id = ? THEN o.b_id ELSE o.a_id END AS other_id "
        "FROM overlaps o WHERE o.a_id = ? OR o.b_id = ? "
        "ORDER BY o.similarity DESC",
        (use_case_id, use_case_id, use_case_id),
    ).fetchall()
    return [dict(row) for row in rows]
