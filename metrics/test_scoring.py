import json
from scoring import HERE, evaluate, rice_score, check_evidence

ideas = json.loads((HERE / "examples" / "ideas.json").read_text(encoding="utf-8"))
for idea in ideas:
    r, exp = evaluate(idea), idea["expected"]
    assert r["ai_fit"]["label"] == exp["ai_fit"], (idea["id"], r["ai_fit"])
    assert r["ai_act"]["tier"] == exp["tier"], (idea["id"], r["ai_act"])
    assert r["score"]["status"] == exp["status"], (idea["id"], r["score"])
    if exp.get("transparency"):
        assert r["ai_act"]["transparency"] and r["review_required"], idea["id"]

r = evaluate(next(i for i in ideas if i["id"] == "rank-job-applicants"))
assert r["review_required"] and r["score"]["value"] is not None

base = ideas[0]["rice_inputs"]
assert rice_score({"impact": 2})["status"] == "needs_info"

assert "impact" in rice_score({**base, "impact": {"value": 7}})["missing"]

inputs = {"reach": {"value": 999, "evidence": "1,000 users daily"}}
assert check_evidence(inputs, "we have a few users")[0] == ["reach"] and inputs["reach"]["value"] is None

print(f"ok: {len(ideas)} example ideas + 5 rule checks passed")

from scoring import ai_act
assert ai_act({"art5_practices": "social_scoring", "art50": [], "annex_iii_area": "none",
               "annex_i_safety_component": False, "profiles_people": False, "narrow_or_preparatory": True})["tier"] == "needs_review"
assert ai_act({"art5_practices": ["emotion_recognition"], "art50": [], "annex_iii_area": "none",
               "annex_i_safety_component": False, "profiles_people": False, "narrow_or_preparatory": True})["tier"] == "needs_review"
assert ai_act({"art5_practices": [], "art50": [], "annex_iii_area": "none",
               "annex_i_safety_component": "true", "profiles_people": False, "narrow_or_preparatory": True})["tier"] == "needs_review"
assert ai_act({"annex_iii_area": ["employment"]})["tier"] == "needs_review"
for bad in (float("nan"), float("inf"), -5, "312", True, 10**400):
    assert rice_score({**base, "reach": {"value": bad}})["status"] == "needs_info", bad
for ev in (None, "", "a", "knowledge-base/made-up.csv: 999 users", "knowledge-base/../../etc/passwd: root"):
    inputs = {"reach": {"value": 99999, "evidence": ev}}
    assert check_evidence(inputs, "we have a few users")[0] == ["reach"], ev
inputs = {"effort": {"value": 1, "evidence": "knowledge-base/it/systems.csv: Support tickets and help centre"}}
assert check_evidence(inputs, "x") == ([], [])
no_transcript = {**ideas[0], "transcript": ""}
assert evaluate(no_transcript)["score"]["status"] == "needs_info"
print("ok: hostile-input checks passed")

neg = {"art5_practices": [], "art50": [], "annex_i_safety_component": False, "profiles_people": False}
assert ai_act({**neg, "annex_i_safety_component": True, "annex_iii_area": "none", "narrow_or_preparatory": False})["tier"] == "high-risk"
assert ai_act({**neg, "annex_iii_area": "employment", "narrow_or_preparatory": True})["tier"].startswith("not high-risk")
assert ai_act({**neg, "annex_iii_area": "employment", "narrow_or_preparatory": True, "profiles_people": True})["tier"] == "high-risk"
print("ok: Annex I and Art. 6(3) paths checked")

est = {"reach": {"value": 312, "source": "knowledge_base", "evidence": "knowledge-base/departments/support.md: | Tickets per month | 312 |"},
       "impact": {"value": 2, "source": "employee", "evidence": "routing by hand takes ages"},
       "confidence": {"value": 1.0, "source": "employee", "evidence": "routing by hand takes ages"},
       "effort": {"value": 1, "source": "estimate", "evidence": "API exists, one developer month",
                  "basis": ["knowledge-base/it/systems.csv: Zendesk,Support tickets and help centre,E16,yes,yes",
                            "knowledge-base/company/strategy-2027.md: about 15 person-days per month"]}}
r = evaluate({"id": "e", "transcript": "Ticket routing by hand takes ages.", "rice_inputs": est})
assert r["score"]["status"] == "scored" and r["score"]["estimated"] == ["effort"] and r["score"]["breakdown"]["confidence"] == 0.5
bad = json.loads(json.dumps(est)); bad["effort"]["basis"] = ["knowledge-base/it/systems.csv: made up fact here"]
assert evaluate({"id": "e", "transcript": "Ticket routing by hand takes ages.", "rice_inputs": bad})["score"]["status"] == "needs_info"
print("ok: estimates from the knowledge base checked")
