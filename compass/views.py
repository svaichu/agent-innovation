"""Data assembly for the dashboard, and the access rules.

Authorization lives here, not in the UI. Hiding a tab is a convenience; every
function below independently refuses a role that may not see the data, so an
employee cannot reach the portfolio by calling the endpoint directly.
"""

from __future__ import annotations

import csv
import sqlite3
from dataclasses import dataclass

from . import config, db
from .agents import risk as risk_agent
from .kg import query, retrieve

LOGINS = config.SEED_DIR / "demo_logins.csv"

RISK_LABEL = {
    "prohibited": "Art. 5 PROHIBITED",
    "high_risk": "HIGH-RISK",
    "high_risk_candidate": "Annex III candidate",
    "minimal": "minimal",
    "insufficient_information": "cannot tell yet",
}

AI_FIT_LABEL = {
    "ai": "AI",
    "conventional_automation": "conventional automation",
    "hybrid": "hybrid",
    "more_research": "more research",
}


class AccessDenied(Exception):
    """Raised when a role may not see what it asked for."""


@dataclass
class Viewer:
    employee_id: str
    name: str
    department: str
    role: str

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    @property
    def may_review(self) -> bool:
        return self.role in ("admin", "reviewer")


def load_logins() -> dict[str, dict]:
    if not LOGINS.exists():
        return {}
    with LOGINS.open(newline="", encoding="utf-8") as file:
        return {r["employee_id"]: r for r in csv.DictReader(file)}


def check_login(username: str, password: str) -> bool:
    """Demo authentication: plain comparison against a generated file.

    Not an authentication scheme. See the README.
    """
    import hmac

    row = load_logins().get((username or "").strip().upper())
    if row is None:
        return False
    return hmac.compare_digest(row["password"].encode(), (password or "").encode())


def viewer_for(employee_id: str) -> Viewer:
    row = load_logins().get((employee_id or "").strip().upper())
    if row is None:
        return Viewer(employee_id or "?", "unknown", "", "employee")
    return Viewer(row["employee_id"], row["name"], row["department"],
                  row["access_role"])


def require_admin(viewer: Viewer) -> None:
    if not viewer.is_admin:
        raise AccessDenied(
            f"{viewer.name} ({viewer.employee_id}) has access role "
            f"'{viewer.role}'. The assessed portfolio is restricted to the "
            f"decision board. Ask Ottilie Janssens (E26).")


def require_reviewer(viewer: Viewer) -> None:
    if not viewer.may_review:
        raise AccessDenied(
            f"The review queue is restricted to reviewers and the decision "
            f"board. Your access role is '{viewer.role}'.")


# --------------------------------------------------------------------------- #
# portfolio
# --------------------------------------------------------------------------- #
def portfolio(conn: sqlite3.Connection, viewer: Viewer) -> list[dict]:
    """Every assessed idea with the figures the board filters on."""
    require_admin(viewer)

    rows = []
    for case in conn.execute(
        "SELECT * FROM use_cases ORDER BY id").fetchall():
        score = db.latest_assessment(conn, case["id"], "score")
        feasibility = db.latest_assessment(conn, case["id"], "feasibility")
        risk = db.latest_assessment(conn, case["id"], "risk")
        ai_fit = db.latest_assessment(conn, case["id"], "ai_fit")
        if not (score and feasibility and risk and ai_fit):
            continue

        risk_payload = risk["payload"]
        selectable, gate_reason = risk_agent.gate(risk_payload)
        open_items = conn.execute(
            "SELECT COUNT(*) FROM review_items WHERE use_case_id = ? "
            "AND status = 'open'", (case["id"],)).fetchone()[0]
        links = conn.execute(
            "SELECT COUNT(*) FROM overlaps WHERE (a_id = ? OR b_id = ?) "
            "AND verdict != 'distinct'", (case["id"], case["id"])).fetchone()[0]
        decision = conn.execute(
            "SELECT decision FROM decisions WHERE use_case_id = ? "
            "ORDER BY id DESC LIMIT 1", (case["id"],)).fetchone()

        provided = conn.execute(
            "SELECT COUNT(*) FROM core_fields WHERE use_case_id = ? "
            "AND state = 'provided'", (case["id"],)).fetchone()[0]

        rows.append({
            "id": case["id"],
            "title": case["title"],
            "department": case["department"] or "-",
            "author_id": case["author_id"] or "-",
            "score": score["payload"].get("score"),
            "ai_fit": ai_fit["payload"].get("verdict"),
            "risk": risk_payload.get("overall"),
            "article_50": bool(risk_payload.get("article_50", {}).get("applies")),
            "feasibility": feasibility["payload"].get("verdict"),
            "est_cost_eur": feasibility["payload"].get("est_cost_eur") or 0,
            "people_required": feasibility["payload"].get("people_required") or 0,
            "est_person_days": feasibility["payload"].get("est_person_days") or 0,
            "completeness": f"{provided}/{len(config.core_field_keys())}",
            "fields_provided": provided,
            "overlaps": links,
            "open_review_items": open_items,
            "selectable": selectable,
            "gate_reason": gate_reason,
            "decision": decision["decision"] if decision else "",
            "scoring_config": score["payload"]["config"]["file"],
            "model": score["model"],
        })

    # Scored first, highest first; unscored last but still visible.
    rows.sort(key=lambda r: (r["score"] is None, -(r["score"] or 0), r["id"]))
    for position, row in enumerate(rows, 1):
        row["rank"] = position
    return rows


def filter_portfolio(rows: list[dict], *, max_cost: int | None = None,
                     max_people: int | None = None,
                     max_person_days: int | None = None,
                     departments: list[str] | None = None,
                     ai_fits: list[str] | None = None,
                     feasibilities: list[str] | None = None,
                     risk_clear_only: bool = False,
                     hide_unscored: bool = False,
                     needs_review_only: bool = False) -> list[dict]:
    out = rows
    if max_cost is not None:
        out = [r for r in out if r["est_cost_eur"] <= max_cost]
    if max_people is not None:
        out = [r for r in out if r["people_required"] <= max_people]
    if max_person_days is not None:
        out = [r for r in out if r["est_person_days"] <= max_person_days]
    if departments:
        out = [r for r in out if r["department"] in departments]
    if ai_fits:
        out = [r for r in out if r["ai_fit"] in ai_fits]
    if feasibilities:
        out = [r for r in out if r["feasibility"] in feasibilities]
    if risk_clear_only:
        out = [r for r in out if r["selectable"]]
    if hide_unscored:
        out = [r for r in out if r["score"] is not None]
    if needs_review_only:
        out = [r for r in out if r["open_review_items"] > 0]
    return out


TABLE_HEADERS = ["#", "ID", "Idea", "Dept", "Score", "AI fit", "EU AI Act",
                 "Art. 50", "Feasibility", "EUR", "People", "Days",
                 "Fields", "Links", "Review", "Selectable"]


def to_table(rows: list[dict]) -> list[list]:
    return [[
        row["rank"], row["id"], row["title"][:58], row["department"],
        "-" if row["score"] is None else row["score"],
        AI_FIT_LABEL.get(row["ai_fit"], row["ai_fit"]),
        RISK_LABEL.get(row["risk"], row["risk"]),
        "yes" if row["article_50"] else "",
        row["feasibility"].replace("_", " "),
        f"{row['est_cost_eur']:,}", row["people_required"],
        row["est_person_days"], row["completeness"], row["overlaps"] or "",
        row["open_review_items"] or "",
        "yes" if row["selectable"] else "BLOCKED",
    ] for row in rows]


# --------------------------------------------------------------------------- #
# one idea, in full
# --------------------------------------------------------------------------- #
def _bullets(items: list[str], empty: str = "none") -> str:
    return "\n".join(f"- {i}" for i in items) if items else f"- {empty}"


def detail(conn: sqlite3.Connection, viewer: Viewer, use_case_id: str) -> str:
    """The full assessment as markdown: evidence, reasoning and citations."""
    require_admin(viewer)

    case = conn.execute("SELECT * FROM use_cases WHERE id = ?",
                        (use_case_id,)).fetchone()
    if case is None:
        return f"No idea with id {use_case_id!r}."

    fields = {r["field_key"]: r for r in conn.execute(
        "SELECT * FROM core_fields WHERE use_case_id = ?", (use_case_id,))}
    score = db.latest_assessment(conn, use_case_id, "score")
    feasibility = db.latest_assessment(conn, use_case_id, "feasibility")
    risk = db.latest_assessment(conn, use_case_id, "risk")
    ai_fit = db.latest_assessment(conn, use_case_id, "ai_fit")
    similarity = db.latest_assessment(conn, use_case_id, "similarity")

    out = [f"## {case['id']}: {case['title']}",
           f"*Submitted by {case['author_id']} ({case['department'] or 'unknown'}), "
           f"status {case['status']}, source {case['source']}*", ""]

    if risk:
        selectable, reason = risk_agent.gate(risk["payload"])
        if not selectable:
            out += [f"> **Selection blocked.** {reason}", ""]

    # --- the submitted record, with states visible -----------------------
    out += ["### The submitted record", ""]
    for key in config.core_field_keys():
        row = fields.get(key)
        state = row["state"] if row else "missing"
        value = (row["value"] or "").strip() if row else ""
        if state == "provided":
            out.append(f"**{key}**  \n{value}")
        elif state == "unclear":
            out.append(f"**{key}** — *too vague to evaluate*  \n{value}")
        elif state == "assumed":
            out.append(f"**{key}** — *assumed by the agent, not evidence*  \n{value}")
        else:
            out.append(f"**{key}** — *not provided. The agent asked rather "
                       f"than assuming a value.*")
        out.append("")

    # --- business score ---------------------------------------------------
    if score:
        payload = score["payload"]
        out += ["### Business score (RICE)",
                f"Config: **{payload['config']['label']}** "
                f"(`{payload['config']['file']}`, "
                f"formula `{payload['config']['formula']}`, "
                f"period {payload['config']['time_period']})", ""]
        if payload.get("scored"):
            out.append(f"**Score {payload['score']}** — {payload['explanation']}")
        else:
            out.append(f"**Not scored.** "
                       f"{', '.join(payload.get('unscored_factors', []))} "
                       f"could not be determined from the submission.")
        out.append("")
        out += ["| Factor | Value | Basis |", "|---|---|---|"]
        for name, factor in payload.get("factors", {}).items():
            basis = (factor.get("band") or factor.get("label") or "")
            extra = factor.get("evidence") or factor.get("rationale") or ""
            if factor.get("caps_applied"):
                extra += " " + "; ".join(factor["caps_applied"])
            if factor.get("raw") is not None:
                basis = f"{basis} (raw {factor['raw']})"
            out.append(f"| {name} | {factor.get('value')} | {basis} "
                       f"{str(extra)[:120]} |")
        out.append("")
        if payload.get("assumptions"):
            out += ["**Assumptions**", _bullets(payload["assumptions"]), ""]
        if payload.get("what_would_raise_confidence"):
            out += ["**What would raise confidence**",
                    _bullets(payload["what_would_raise_confidence"]), ""]

    # --- AI suitability ---------------------------------------------------
    if ai_fit:
        payload = ai_fit["payload"]
        out += ["### Is AI the right tool?",
                f"**{AI_FIT_LABEL.get(payload['verdict'], payload['verdict'])}** "
                f"(confidence {payload.get('confidence', '?')})", "",
                payload.get("reasoning", ""), ""]
        if payload.get("simpler_alternative"):
            out += [f"**Simpler alternative:** {payload['simpler_alternative']}", ""]
        if payload.get("why_not_simpler"):
            out += [f"**Why rules would not do:** {payload['why_not_simpler']}", ""]
        if payload.get("gaps"):
            out += ["**Blocking facts and gaps**", _bullets(payload["gaps"]), ""]

    # --- regulatory screening --------------------------------------------
    if risk:
        payload = risk["payload"]
        out += ["### EU AI Act screening (preliminary, not legal advice)",
                f"**Overall: {RISK_LABEL.get(payload['overall'], payload['overall'])}**",
                ""]
        article_5 = payload.get("article_5", {})
        out += [f"**Article 5 (prohibited):** {article_5.get('verdict', '?')}"
                + (f" — `{article_5['citation']}`" if article_5.get("citation") else ""),
                "", article_5.get("rationale") or "No prohibited practice matched.",
                ""]
        high = payload.get("high_risk", {})
        out += [f"**Article 6 (high-risk):** {high.get('verdict', '?')}"
                + (f" — `{high['citation']}`" if high.get("citation") else ""), ""]
        if high.get("matched_point"):
            out.append(f"Matched: {high['matched_point']}  ")
        if high.get("derogation_applied"):
            out.append(f"Article 6(3) derogation applied: "
                       f"*{high.get('derogation_condition')}*  ")
        out += [high.get("rationale", ""), ""]

        article_50 = payload.get("article_50", {})
        if article_50.get("applies"):
            out += [f"**Article 50 (transparency): APPLIES** — "
                    f"`{article_50.get('citation')}`", "",
                    article_50.get("obligation", ""),
                    "", "*A separate obligation. It sits on top of the risk "
                    "class and does not change it.*", ""]
        else:
            out += ["**Article 50 (transparency):** does not apply on the "
                    "information given.", ""]

        if payload.get("evidence"):
            out += ["**Evidence quoted from the submission**",
                    _bullets(payload["evidence"]), ""]
        if payload.get("local_policy"):
            out += ["**Company policy (independent of the Act)**",
                    _bullets(payload["local_policy"]), ""]
        if payload.get("gaps"):
            out += ["**Gaps that limited this screening**",
                    _bullets(payload["gaps"]), ""]
        review = payload.get("human_review", {})
        if review.get("required"):
            out += [f"**Human review required:** "
                    f"{', '.join(review.get('who', []))} — "
                    f"{review.get('why', '')}", ""]

    # --- feasibility ------------------------------------------------------
    if feasibility:
        payload = feasibility["payload"]
        out += ["### Can we deliver it?",
                f"**{payload['verdict'].replace('_', ' ')}** — "
                f"{payload['est_person_days']} person-days, "
                f"{payload['people_required']} people, "
                f"about EUR {payload['est_cost_eur']:,} "
                f"at EUR {payload.get('day_rate_eur', 0)}/day "
                f"(effort figure from: {payload.get('effort_source')})", "",
                "| Dimension | Status | Finding | Sources |", "|---|---|---|---|"]
        for name, dimension in payload.get("dimensions", {}).items():
            cites = ", ".join(f"`{c}`" for c in dimension.get("cites", [])[:2])
            out.append(f"| {name} | **{dimension.get('status')}** | "
                       f"{str(dimension.get('note', ''))[:220]} | {cites} |")
        out.append("")
        if payload.get("blockers"):
            out += ["**Blockers**", _bullets(payload["blockers"]), ""]
        if payload.get("assumptions"):
            out += ["**Assumptions**", _bullets(payload["assumptions"]), ""]
        if payload.get("open_questions"):
            out += ["**Open questions**", _bullets(payload["open_questions"]), ""]

    # --- overlaps ---------------------------------------------------------
    links = conn.execute(
        "SELECT *, CASE WHEN a_id = ? THEN b_id ELSE a_id END AS other "
        "FROM overlaps WHERE (a_id = ? OR b_id = ?) AND verdict != 'distinct' "
        "ORDER BY similarity DESC", (use_case_id, use_case_id, use_case_id)
    ).fetchall()
    out += ["### Related ideas from elsewhere in the company", ""]
    if links:
        for link in links:
            other = conn.execute(
                "SELECT title, department FROM use_cases WHERE id = ?",
                (link["other"],)).fetchone()
            out += [f"**{link['verdict']}** ({link['similarity']:.2f}) → "
                    f"**{link['other']}** {other['title']} "
                    f"*({other['department']})*  ",
                    f"{link['rationale']}", ""]
    else:
        out += ["- No related idea found in the portfolio.", ""]
    if similarity and similarity["payload"].get("active_project_overlap"):
        out += ["**Overlaps work already running**", ""]
        for project in similarity["payload"]["active_project_overlap"]:
            out.append(f"- {project['id']} {project['project']} "
                       f"({project['status']}, due {project['due']}) — "
                       f"`{project['cite']}`")
        out.append("")

    # --- open questions for a human --------------------------------------
    items = conn.execute(
        "SELECT * FROM review_items WHERE use_case_id = ? AND status = 'open' "
        "ORDER BY CASE severity WHEN 'high' THEN 0 WHEN 'medium' THEN 1 "
        "ELSE 2 END", (use_case_id,)).fetchall()
    out += ["### Open questions and review items", ""]
    if items:
        for item in items:
            out.append(f"- **[{item['severity']}]** {item['reason']}"
                       + (f" (`{item['field_key']}`)" if item["field_key"] else "")
                       + f" — {item['detail'] or ''}"
                       + (f" → {item['assignee_id']}" if item["assignee_id"] else ""))
    else:
        out.append("- none")
    out.append("")

    models = {kind: (db.latest_assessment(conn, use_case_id, kind) or {}).get("model")
              for kind in ("similarity", "ai_fit", "risk", "feasibility", "score")}
    out += ["---",
            "*Produced by: " + ", ".join(f"{k}={v}" for k, v in models.items()
                                         if v) + "*"]
    return "\n".join(out)


# --------------------------------------------------------------------------- #
# review queue
# --------------------------------------------------------------------------- #
REVIEW_HEADERS = ["Severity", "Idea", "Title", "Reason", "Field", "Detail",
                  "Assigned"]


def review_queue(conn: sqlite3.Connection, viewer: Viewer,
                 mine_only: bool = False) -> list[list]:
    require_reviewer(viewer)
    sql = ("SELECT r.*, u.title, u.department FROM review_items r "
           "JOIN use_cases u ON u.id = r.use_case_id "
           "WHERE r.status = 'open' ")
    params: list = []
    if mine_only:
        sql += "AND r.assignee_id = ? "
        params.append(viewer.employee_id)
    sql += ("ORDER BY CASE r.severity WHEN 'high' THEN 0 WHEN 'medium' THEN 1 "
            "ELSE 2 END, r.use_case_id")
    return [[
        row["severity"], row["use_case_id"], row["title"][:44],
        row["reason"].replace("_", " "), row["field_key"] or "",
        (row["detail"] or "")[:110], row["assignee_id"] or "",
    ] for row in conn.execute(sql, params).fetchall()]


# --------------------------------------------------------------------------- #
# employee's own submissions
# --------------------------------------------------------------------------- #
MINE_HEADERS = ["ID", "Idea", "Submitted", "Status", "Fields complete",
                "What happens next"]

STATUS_EXPLANATION = {
    "draft": "Not submitted yet.",
    "submitted": "Received, waiting to be assessed.",
    "assessed": "Assessed and in the ranked portfolio for the next review.",
    "in_review": "A person is checking something before it can be ranked.",
    "selected": "Selected for funding.",
    "parked": "Kept for later.",
    "rejected": "Not being taken forward.",
}


def my_ideas(conn: sqlite3.Connection, viewer: Viewer) -> list[list]:
    """An employee's own submissions.

    Deliberately without scores: the ranked assessment is the decision board's
    working material, and showing someone their own idea scored 1.2 out of
    context is not useful to them.
    """
    rows = conn.execute(
        "SELECT * FROM use_cases WHERE author_id = ? ORDER BY created_at DESC",
        (viewer.employee_id,)).fetchall()
    out = []
    for row in rows:
        provided = conn.execute(
            "SELECT COUNT(*) FROM core_fields WHERE use_case_id = ? "
            "AND state = 'provided'", (row["id"],)).fetchone()[0]
        asked = conn.execute(
            "SELECT field_key FROM review_items WHERE use_case_id = ? "
            "AND reason = 'missing_core_field' AND status = 'open'",
            (row["id"],)).fetchall()
        next_step = STATUS_EXPLANATION.get(row["status"], row["status"])
        if asked:
            next_step = ("Waiting on you: "
                         + ", ".join(a["field_key"] for a in asked))
        out.append([row["id"], row["title"][:58], row["created_at"][:10],
                    row["status"], f"{provided}/8", next_step])
    return out


# --------------------------------------------------------------------------- #
# knowledge chatbot
# --------------------------------------------------------------------------- #
def ask_knowledge_base(conn: sqlite3.Connection, viewer: Viewer,
                       question: str) -> str:
    """Answer from the knowledge base, within what this role may see."""
    from . import llm

    question = (question or "").strip()
    if not question:
        return "Ask me something about the company."

    chunks = retrieve.search(conn, question, role=viewer.role, limit=5)
    hidden = retrieve.restricted_hits(conn, question, viewer.role)

    if not chunks:
        answer = ("I could not find anything about that in the knowledge base.")
        if hidden:
            answer += (f" There are {hidden} sections on this topic that your "
                       f"access role ('{viewer.role}') cannot see — ask "
                       f"Ottilie Janssens (E26).")
        return answer

    context = retrieve.context_block(chunks)
    system = (
        "You answer employee questions about their own company, using only the "
        "knowledge base extracts provided.\n"
        "Rules:\n"
        "- Use only the extracts. If they do not contain the answer, say so.\n"
        "- Cite the source path of every fact you state, in brackets.\n"
        "- Never guess a number. Quote it or say it is not recorded.\n"
        "- Be brief: two or three sentences unless asked for detail.")
    user = f"Question: {question}\n\nKnowledge base extracts:\n{context}"

    def offline() -> str:
        """Extractive answer: the best-matching sections, quoted with sources.

        Without a model we do not try to compose prose. Quoting the right
        paragraph and naming its source is more useful than a fluent guess.
        """
        parts = [f"From the knowledge base (no model configured, so these are "
                 f"the relevant sections quoted directly):", ""]
        for chunk in chunks[:3]:
            body = chunk.text.strip()
            if len(body) > 700:
                body = body[:700].rsplit("\n", 1)[0] + " ..."
            parts += [f"**{chunk.heading}** — `{chunk.source_path}`", body, ""]
        return "\n".join(parts)

    answer, _ = llm.generate_text(system, user, offline=offline)
    sources = sorted({c.source_path for c in chunks})
    answer += "\n\n*Sources: " + ", ".join(f"`{s}`" for s in sources) + "*"
    if hidden:
        answer += (f"\n\n*{hidden} further section(s) on this topic are "
                   f"restricted to a higher access role.*")
    return answer


# --------------------------------------------------------------------------- #
# decisions
# --------------------------------------------------------------------------- #
def record_decision(conn: sqlite3.Connection, viewer: Viewer,
                    use_case_id: str, decision: str, note: str = "") -> str:
    """Select, park or reject an idea. The risk gate is enforced here."""
    require_admin(viewer)
    if decision not in ("selected", "parked", "rejected"):
        return f"Unknown decision {decision!r}."

    risk = db.latest_assessment(conn, use_case_id, "risk")
    if risk is None:
        return f"{use_case_id} has not been assessed yet."

    allowed, reason = risk_agent.gate(risk["payload"])
    if decision == "selected" and not allowed:
        # The business score is not consulted. That is the point.
        return (f"**Cannot select {use_case_id}.** {reason}\n\n"
                f"The business score does not override this. Park or reject "
                f"it, or have the named reviewer clear the gate first.")

    conn.execute(
        "INSERT INTO decisions (use_case_id, decision, actor_id, note, "
        "created_at) VALUES (?, ?, ?, ?, ?)",
        (use_case_id, decision, viewer.employee_id, note, db.now()))
    conn.execute("UPDATE use_cases SET status = ?, updated_at = ? WHERE id = ?",
                 (decision, db.now(), use_case_id))
    db.log(conn, viewer.employee_id, f"decision.{decision}", use_case_id,
           detail={"note": note})
    return (f"**{use_case_id} marked {decision}** by {viewer.name} "
            f"({viewer.employee_id}).")


# --------------------------------------------------------------------------- #
# summary line
# --------------------------------------------------------------------------- #
def portfolio_summary(conn: sqlite3.Connection, rows: list[dict]) -> str:
    total = len(rows)
    scored = [r for r in rows if r["score"] is not None]
    blocked = [r for r in rows if not r["selectable"]]
    cost = sum(r["est_cost_eur"] for r in rows if r["selectable"]
               and r["score"] is not None)
    days = sum(r["est_person_days"] for r in rows if r["selectable"]
               and r["score"] is not None)
    budget = query.budget_outlook(conn, None)
    return (
        f"**{total} ideas** · {len(scored)} scored · {len(blocked)} blocked by "
        f"a risk gate · selectable work totals **EUR {cost:,}** and "
        f"**{days} person-days** against EUR {budget.remaining_eur:,} "
        f"unspent and about 60 person-days per month allocated.")
