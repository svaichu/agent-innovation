"""Run the full assessment for one idea, and keep the portfolio consistent.

Order matters. AI-fit runs before risk, because "this is not an AI system at
all" changes the whole risk conversation. Feasibility runs before scoring,
because RICE Effort comes from the feasibility estimate rather than being
invented twice.

    similarity -> ai_fit -> risk -> feasibility -> score

Everything is written as its own assessment row with the model that produced
it, so a board member can see which verdicts came from a live model and which
from the offline rules.
"""

from __future__ import annotations

import sqlite3

from .. import config, db, llm, records
from ..records import UseCaseRecord
from . import ai_fit, feasibility, risk, score, similarity

KINDS = ["similarity", "ai_fit", "risk", "feasibility", "score"]


def load_portfolio(conn: sqlite3.Connection) -> list[UseCaseRecord]:
    """Every stored use case, rebuilt as records for similarity comparison."""
    out: list[UseCaseRecord] = []
    for row in conn.execute("SELECT * FROM use_cases").fetchall():
        record = UseCaseRecord(
            id=row["id"], title=row["title"], author_id=row["author_id"] or "",
            department=row["department"] or "", source=row["source"],
            source_path=row["source_path"] or "", created_at=row["created_at"],
            status=row["status"], version=row["version"],
        )
        for field_row in conn.execute(
            "SELECT * FROM core_fields WHERE use_case_id = ?", (row["id"],)
        ).fetchall():
            record.fields[field_row["field_key"]] = records.CoreField(
                key=field_row["field_key"], value=field_row["value"] or "",
                state=field_row["state"], evidence=field_row["evidence"] or "")
        out.append(record)
    return out


def upsert_record(conn: sqlite3.Connection, record: UseCaseRecord) -> None:
    existing = conn.execute("SELECT version FROM use_cases WHERE id = ?",
                            (record.id,)).fetchone()
    version = (existing["version"] if existing else record.version)
    conn.execute(
        "INSERT INTO use_cases (id, title, author_id, department, source, "
        "source_path, status, version, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(id) DO UPDATE SET title = excluded.title, "
        "department = excluded.department, status = excluded.status, "
        "updated_at = excluded.updated_at",
        (record.id, record.title, record.author_id, record.department,
         record.source, record.source_path, record.status, version,
         record.created_at or db.now(), db.now()),
    )
    for key in config.core_field_keys():
        field = record.get(key)
        conn.execute(
            "INSERT INTO core_fields (use_case_id, field_key, value, state, "
            "evidence) VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(use_case_id, field_key) DO UPDATE SET "
            "value = excluded.value, state = excluded.state, "
            "evidence = excluded.evidence",
            (record.id, key, field.value, field.state, field.evidence),
        )


def _department_of(conn: sqlite3.Connection, author_id: str) -> str:
    if not author_id:
        return ""
    row = conn.execute(
        "SELECT json_extract(attrs, '$.department') FROM kg_node WHERE id = ?",
        (f"employee:{author_id}",)).fetchone()
    return (row[0] if row else "") or ""


def raise_review_items(conn: sqlite3.Connection, record: UseCaseRecord,
                       risk_payload: dict, score_payload: dict,
                       feasibility_payload: dict) -> None:
    """Turn every gap into something a named person can act on."""
    for key in record.missing_fields():
        severity = "high" if key in config.required_field_keys() else "medium"
        db.add_review_item(
            conn, record.id, reason="missing_core_field", severity=severity,
            field_key=key,
            detail=(f"'{key}' was not provided. The agent asked rather than "
                    f"assuming a value."),
            assignee_id=record.author_id or None)

    if risk_payload.get("human_review", {}).get("required"):
        who = risk_payload["human_review"].get("who") or ["E113"]
        db.add_review_item(
            conn, record.id, reason="risk_review_required",
            severity="high" if risk_payload["overall"] in
                     ("prohibited", "high_risk") else "medium",
            detail=risk_payload["human_review"].get("why", ""),
            assignee_id=who[0])

    if not score_payload.get("scored"):
        db.add_review_item(
            conn, record.id, reason="not_scored", severity="medium",
            detail=("Cannot be ranked: "
                    + ", ".join(score_payload.get("unscored_factors", []))
                    + " could not be determined."),
            assignee_id=record.author_id or None)

    for blocker in feasibility_payload.get("blockers", []):
        db.add_review_item(
            conn, record.id, reason="feasibility_blocker", severity="medium",
            detail=blocker, assignee_id="E26")

    if feasibility_payload.get("effort_source") == "agent estimate":
        db.add_review_item(
            conn, record.id, reason="effort_estimated_by_agent",
            severity="low",
            detail=(f"The submitter gave no effort figure. "
                    f"{feasibility_payload.get('est_person_days')} person-days "
                    f"is the agent's estimate and should be confirmed."),
            assignee_id="E26")


def run(record: UseCaseRecord, conn: sqlite3.Connection,
        scoring_config: str | None = None,
        others: list[UseCaseRecord] | None = None) -> dict:
    """Assess one idea end to end. Returns a summary of what was written."""
    if not record.department:
        record.department = _department_of(conn, record.author_id)
    upsert_record(conn, record)

    active = scoring_config or db.get_active_scoring(conn)
    portfolio = others if others is not None else [
        r for r in load_portfolio(conn) if r.id != record.id]

    similarity_payload, similarity_model = similarity.assess(
        record, portfolio, conn)
    db.save_assessment(conn, record.id, record.version, "similarity",
                       similarity_payload, similarity_model)

    ai_fit_payload, ai_fit_model = ai_fit.assess(record, conn)
    db.save_assessment(conn, record.id, record.version, "ai_fit",
                       ai_fit_payload, ai_fit_model)

    risk_payload, risk_model = risk.assess(
        record, conn, ai_fit_verdict=ai_fit_payload.get("verdict"))
    db.save_assessment(conn, record.id, record.version, "risk",
                       risk_payload, risk_model, config_name="eu-ai-act",
                       config_version=str(config.risk_config().get("version")))

    feasibility_payload, feasibility_model = feasibility.assess(record, conn)
    db.save_assessment(conn, record.id, record.version, "feasibility",
                       feasibility_payload, feasibility_model)

    score_payload, score_model = score.assess(
        record, conn, feasibility_payload, config_name=active)
    db.save_assessment(conn, record.id, record.version, "score",
                       score_payload, score_model,
                       config_name=active,
                       config_version=str(score_payload["config"]["version"]))

    raise_review_items(conn, record, risk_payload, score_payload,
                       feasibility_payload)

    allowed, gate_reason = risk.gate(risk_payload)
    status = "assessed" if allowed else "in_review"
    conn.execute("UPDATE use_cases SET status = ?, updated_at = ? WHERE id = ?",
                 (status, db.now(), record.id))

    db.log(conn, "orchestrator", "assess", record.id, detail={
        "ai_fit": ai_fit_payload.get("verdict"),
        "risk": risk_payload.get("overall"),
        "feasibility": feasibility_payload.get("verdict"),
        "score": score_payload.get("score"),
        "selectable": allowed,
        "provider": llm.status()["provider"],
    })

    return {
        "id": record.id,
        "title": record.title,
        "ai_fit": ai_fit_payload.get("verdict"),
        "risk": risk_payload.get("overall"),
        "feasibility": feasibility_payload.get("verdict"),
        "score": score_payload.get("score"),
        "est_cost_eur": feasibility_payload.get("est_cost_eur"),
        "people_required": feasibility_payload.get("people_required"),
        "overlaps": len(similarity_payload.get("overlaps", [])),
        "selectable": allowed,
        "gate_reason": gate_reason,
        "completeness": "%d/%d" % record.completeness(),
        "models": {"similarity": similarity_model, "ai_fit": ai_fit_model,
                   "risk": risk_model, "feasibility": feasibility_model,
                   "score": score_model},
    }


def rescore_all(conn: sqlite3.Connection, scoring_config: str) -> dict:
    """Re-score the whole portfolio under a different config.

    Only the score changes: AI-fit, risk and feasibility are properties of the
    idea, not of how the board weights value. A snapshot is taken before and
    after so the dashboard can explain every move.
    """
    before = current_ranking(conn)
    db.set_active_scoring(conn, scoring_config)

    for record in load_portfolio(conn):
        feasibility_payload = db.latest_assessment(conn, record.id, "feasibility")
        if feasibility_payload is None:
            continue
        payload, model = score.assess(
            record, conn, feasibility_payload["payload"],
            config_name=scoring_config)
        db.save_assessment(conn, record.id, record.version, "score", payload,
                           model, config_name=scoring_config,
                           config_version=str(payload["config"]["version"]))

    after = current_ranking(conn)
    snapshot(conn, scoring_config, after)
    db.log(conn, "orchestrator", "rescore_all", scoring_config,
           detail={"ideas": len(after)})
    return diff(before, after)


def current_ranking(conn: sqlite3.Connection) -> list[dict]:
    entries = []
    for row in conn.execute(
        "SELECT id, title, department FROM use_cases").fetchall():
        scored = db.latest_assessment(conn, row["id"], "score")
        if scored is None:
            continue
        payload = scored["payload"]
        entries.append({
            "use_case_id": row["id"], "title": row["title"],
            "department": row["department"],
            "score": payload.get("score"),
            "factors": {k: v.get("value") for k, v in
                        payload.get("factors", {}).items()},
            "config": payload["config"]["file"],
        })
    ranked = score.rank(entries)
    for position, entry in enumerate(ranked, 1):
        entry["rank"] = position
    return ranked


def snapshot(conn: sqlite3.Connection, config_name: str,
             ranking: list[dict]) -> None:
    import json
    spec = config.scoring_config(config_name)
    conn.execute(
        "INSERT INTO rank_snapshots (config_name, config_version, payload, "
        "created_at) VALUES (?, ?, ?, ?)",
        (config_name, str(spec.get("version")),
         json.dumps(ranking, ensure_ascii=False), db.now()),
    )


def diff(before: list[dict], after: list[dict]) -> dict:
    """What moved, by how much, and which factor caused it."""
    previous = {e["use_case_id"]: e for e in before}
    moves = []
    for entry in after:
        old = previous.get(entry["use_case_id"])
        if old is None:
            continue
        delta = old["rank"] - entry["rank"]
        if delta == 0 and old.get("score") == entry.get("score"):
            continue
        changed = []
        for name, value in entry["factors"].items():
            previous_value = old["factors"].get(name)
            if previous_value == value:
                continue
            if name not in old["factors"]:
                # A factor the previous config did not have at all.
                changed.append(f"{name} {value} (new in this config)")
            else:
                changed.append(f"{name} {previous_value} -> {value}")
        for name in old["factors"]:
            if name not in entry["factors"]:
                changed.append(f"{name} no longer applies")
        moves.append({
            "use_case_id": entry["use_case_id"],
            "title": entry["title"],
            "rank_before": old["rank"], "rank_after": entry["rank"],
            "places_moved": abs(delta),
            "direction": "up" if delta > 0 else ("down" if delta < 0 else "same"),
            "score_before": old.get("score"), "score_after": entry.get("score"),
            "factor_changes": changed,
            "explanation": (
                f"{entry['use_case_id']} moved "
                f"{'up' if delta > 0 else 'down'} {abs(delta)} place"
                f"{'s' if abs(delta) != 1 else ''}: "
                + ("; ".join(changed) if changed else "score recomputed")
                + f". Score {old.get('score')} -> {entry.get('score')}."
            ) if delta else (
                f"{entry['use_case_id']} kept rank {entry['rank']} but its "
                f"score changed from {old.get('score')} to {entry.get('score')}."
            ),
        })
    moves.sort(key=lambda m: -m["places_moved"])
    return {
        "moved": moves,
        "unchanged": len(after) - len(moves),
        "total": len(after),
        "config_after": after[0]["config"] if after else None,
    }
