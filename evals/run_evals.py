"""Check the pipeline against labelled expectations.

    python -m evals.run_evals

These are assertions about behaviour the challenge brief requires, not a
quality score. They run on the offline rule engine as well as on a live model,
so they catch a regression either way.

The point of each case is written out, because a failing assertion should tell
you what broke rather than only that something did.
"""

from __future__ import annotations

import sys

from compass import db, records
from compass.agents import orchestrator, risk, similarity
from compass.kg import ingest, retrieve

# Each case: a record, and what must be true of its assessment.
CASES: list[dict] = [
    {
        "id": "EV-01",
        "why": "Deterministic data movement must not be labelled an AI problem.",
        "fields": dict(
            problem="Order data is retyped from HubSpot into the inventory spreadsheet, about 180 orders every month, and typing errors cause stock discrepancies.",
            intended_purpose="Copy each won deal from HubSpot into the inventory records automatically using the same fixed fields.",
            users_affected="Two logistics coordinators and the inventory controller.",
            deployment_context="Internal only, reads HubSpot and writes to inventory.",
            data="HubSpot deals and the inventory spreadsheet.",
            expected_benefit="Removes 15 hours of retyping per month.",
            effort="Two weeks for one developer.",
            human_oversight="The inventory controller reviews a daily log."),
        "expect": {"ai_fit": "conventional_automation", "risk": "minimal"},
    },
    {
        "id": "EV-02",
        "why": "Workplace emotion inference is prohibited outright (Art. 5(1)(f)).",
        "fields": dict(
            problem="Managers notice burnout too late, after someone is off sick.",
            intended_purpose="Infer each employee's stress level from webcam and keyboard activity and show managers a wellbeing score per person.",
            users_affected="All 120 employees are monitored; 18 managers see the scores.",
            deployment_context="Runs on company laptops, internal dashboard.",
            data="Webcam images and keystroke timing per named employee.",
            expected_benefit="Maybe 20% fewer long-term absences.",
            effort="Two months.",
            human_oversight="Managers decide what to do with the score."),
        "expect": {"risk": "prohibited", "article_5": "art5_1_f",
                   "selectable": False},
    },
    {
        "id": "EV-03",
        "why": "Ranking candidates is Annex III point 4(a) high-risk.",
        "fields": dict(
            problem="We get 140 applications per open role and screening takes the recruiter 20 hours a week.",
            intended_purpose="Read each application and rank candidates best to worst so the recruiter interviews the top ten.",
            users_affected="The recruiter and hiring managers; about 2,400 candidates a year are ranked.",
            deployment_context="Internal, runs on each new Personio application.",
            data="Candidate applications in Personio.",
            expected_benefit="Saves the recruiter 15 hours a week.",
            effort="Four weeks.",
            human_oversight="The recruiter reads the top ten only."),
        "expect": {"risk": "high_risk", "annex": "Annex III, point 4",
                   "selectable": False, "policy_blocks": True},
    },
    {
        "id": "EV-04",
        "why": ("A customer-facing assistant triggers the Article 50 "
                "transparency flag without becoming high-risk."),
        "fields": dict(
            problem="The same product questions arrive through the website form and are answered one by one.",
            intended_purpose="Answer product questions from website visitors in a chat window using our published product data.",
            users_affected="Website visitors, several thousand a month.",
            deployment_context="Public website, the visitor chats with it directly.",
            data="Website content and product specifications, no personal data.",
            expected_benefit="Deflects about half the repeat product questions.",
            effort="Four weeks for a developer and a designer.",
            human_oversight="Conversations reviewed weekly; a human is always available."),
        "expect": {"article_50": True, "risk": "minimal"},
    },
    {
        "id": "EV-05",
        "why": ("An incomplete idea must produce questions, never a guessed "
                "risk verdict."),
        "fields": dict(problem="Our content takes too long."),
        "expect": {"risk": "insufficient_information", "selectable": False,
                   "scored": False, "min_review_items": 4},
    },
    {
        "id": "EV-06",
        "why": ("Routing a ticket is not a decision about a person, so it must "
                "stay minimal risk rather than being over-flagged."),
        "fields": dict(
            problem="All 1,250 tickets a month are categorised and routed by hand, costing the team lead an hour a day.",
            intended_purpose="Read each incoming ticket and set its category, priority and queue. It does not answer the customer.",
            users_affected="The support team lead and ten specialists; 1,250 tickets a month.",
            deployment_context="Internal, inside Zendesk. The customer never sees its output.",
            data="Zendesk tickets, about 52,000 since 2022.",
            expected_benefit="Gives the team lead back 20 hours a month and cuts mis-routing.",
            effort="Three weeks for two people.",
            human_oversight="The team lead reviews a daily sample and can re-route."),
        "expect": {"risk": "minimal", "ai_fit": "ai", "selectable": True,
                   "scored": True},
    },
    {
        "id": "EV-07",
        "why": ("An idea needing data we only hold at low quality must not be "
                "waved through as feasible."),
        "fields": dict(
            problem="Reorder dates are guessed from experience and we had two stock-outs in 2026.",
            intended_purpose="Forecast when each component runs out and suggest a reorder date.",
            users_affected="The production planner and procurement specialist.",
            deployment_context="Internal only.",
            data="Stock movements in the inventory spreadsheet.",
            expected_benefit="Avoids stock-outs.",
            effort="Three weeks.",
            human_oversight="The planner approves every purchase order."),
        "expect": {"feasibility_not": "doable"},
    },
]

# Knowledge chatbot: question -> a source path that must be cited, and the role
# that may see it.
KB_CASES = [
    ("How many vacation days do I get?",
     "knowledge-base/policies/leave-and-working-time.md", "employee"),
    ("Which systems have no API?", "knowledge-base/it/systems.md", "employee"),
    ("What does the AI usage policy forbid?",
     "knowledge-base/policies/ai-usage.md", "employee"),
    ("Who approves a purchase over EUR 50,000?",
     "knowledge-base/policies/procurement.md", "employee"),
]


def check(case: dict, result: dict, conn) -> list[str]:
    """Compare one assessment against its expectations."""
    expect = case["expect"]
    failures = []
    use_case_id = case["id"]

    risk_payload = db.latest_assessment(conn, use_case_id, "risk")["payload"]
    feasibility = db.latest_assessment(conn, use_case_id, "feasibility")["payload"]
    score = db.latest_assessment(conn, use_case_id, "score")["payload"]

    if "ai_fit" in expect and result["ai_fit"] != expect["ai_fit"]:
        failures.append(f"ai_fit expected {expect['ai_fit']}, got {result['ai_fit']}")
    if "risk" in expect and result["risk"] != expect["risk"]:
        failures.append(f"risk expected {expect['risk']}, got {result['risk']}")
    if "article_5" in expect:
        matched = risk_payload["article_5"].get("matched_check")
        if matched != expect["article_5"]:
            failures.append(f"Article 5 check expected {expect['article_5']}, "
                            f"got {matched}")
    if "annex" in expect:
        point = risk_payload["high_risk"].get("matched_point") or ""
        if expect["annex"] not in point:
            failures.append(f"expected {expect['annex']}, got {point!r}")
    if "article_50" in expect:
        applies = bool(risk_payload["article_50"].get("applies"))
        if applies != expect["article_50"]:
            failures.append(f"Article 50 applies expected "
                            f"{expect['article_50']}, got {applies}")
    if "selectable" in expect and result["selectable"] != expect["selectable"]:
        failures.append(f"selectable expected {expect['selectable']}, "
                        f"got {result['selectable']} ({result['gate_reason']})")
    if "scored" in expect and score.get("scored") != expect["scored"]:
        failures.append(f"scored expected {expect['scored']}, "
                        f"got {score.get('scored')}")
    if "feasibility_not" in expect and \
            feasibility["verdict"] == expect["feasibility_not"]:
        failures.append(f"feasibility should not be {expect['feasibility_not']}")
    if "policy_blocks" in expect:
        blocked = feasibility["dimensions"]["compliance"]["status"] == "blocked"
        if blocked != expect["policy_blocks"]:
            failures.append(f"company policy block expected "
                            f"{expect['policy_blocks']}, got {blocked}")
    if "min_review_items" in expect:
        count = conn.execute(
            "SELECT COUNT(*) FROM review_items WHERE use_case_id = ? "
            "AND status = 'open'", (use_case_id,)).fetchone()[0]
        if count < expect["min_review_items"]:
            failures.append(f"expected at least {expect['min_review_items']} "
                            f"review items, got {count}")
    # Every non-minimal verdict must cite something. This is the explainability
    # requirement, so it is checked on every case rather than per expectation.
    if risk_payload["overall"] != "minimal":
        citation = (risk_payload["article_5"].get("citation")
                    or risk_payload["high_risk"].get("citation"))
        if not citation:
            failures.append("non-minimal risk verdict carries no citation")
    return failures


def run() -> int:
    ingest.rebuild()
    passed, failed = 0, 0

    with db.session() as conn:
        # Assess against the seeded portfolio so similarity has something real
        # to compare with.
        portfolio = orchestrator.load_portfolio(conn)
        for case in CASES:
            record = records.from_seed({
                "id": case["id"], "title": case["id"],
                "author_id": "E17", "fields": case["fields"]})
            result = orchestrator.run(record, conn, others=portfolio)
            failures = check(case, result, conn)
            if failures:
                failed += 1
                print(f"FAIL {case['id']}  {case['why']}")
                for failure in failures:
                    print(f"       - {failure}")
            else:
                passed += 1
                print(f"pass {case['id']}  {case['why'][:66]}")

        print()
        # The designated duplicate pair must be linked across departments.
        pair = conn.execute(
            "SELECT * FROM overlaps WHERE a_id = 'UC-001' AND b_id = 'UC-002'"
        ).fetchone()
        if pair and pair["verdict"] != "distinct":
            passed += 1
            print(f"pass OVERLAP  UC-001 x UC-002 linked as "
                  f"'{pair['verdict']}' ({pair['similarity']:.2f}) across "
                  f"sales and support")
        else:
            failed += 1
            print("FAIL OVERLAP  the cross-department duplicate pair "
                  "UC-001 x UC-002 was not linked")

        # Re-ranking must move something and explain it.
        orchestrator.rescore_all(conn, "rice-v1")
        difference = orchestrator.rescore_all(conn, "rice-v2-cost-weighted")
        if difference["moved"] and all(m["explanation"]
                                       for m in difference["moved"]):
            passed += 1
            print(f"pass RERANK   {len(difference['moved'])} ideas moved on a "
                  f"config change, each with an explanation")
        else:
            failed += 1
            print("FAIL RERANK   config change moved nothing, or a move had "
                  "no explanation")
        orchestrator.rescore_all(conn, "rice-v1")

        # The knowledge chatbot must cite the right page.
        print()
        for question, expected_path, role in KB_CASES:
            chunks = retrieve.search(conn, question, role=role, limit=5)
            paths = [c.source_path for c in chunks]
            if expected_path in paths:
                passed += 1
                print(f"pass KB       {question[:46]:<46} -> cites "
                      f"{expected_path.split('/')[-1]}")
            else:
                failed += 1
                print(f"FAIL KB       {question[:46]:<46} -> expected "
                      f"{expected_path}, got {paths[:3]}")

        # Classification must hold: an employee must not reach strategy.
        confidential = retrieve.search(conn, "ARR target 2027 confidential "
                                             "strategy priorities",
                                       role="employee", limit=10)
        leaked = [c.source_path for c in confidential
                  if c.classification == "confidential"]
        if leaked:
            failed += 1
            print(f"FAIL ACCESS   employee retrieval returned confidential "
                  f"pages: {leaked}")
        else:
            passed += 1
            print("pass ACCESS   employee retrieval returned no confidential "
                  "pages")

        # Clean the eval records out so they do not pollute the demo.
        for case in CASES:
            conn.execute("DELETE FROM use_cases WHERE id = ?", (case["id"],))

    print(f"\n{passed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(run())
