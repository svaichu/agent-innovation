import json
import os
import tempfile

from scoring import HERE
from score_agent import MetricInputs, list_files, load_raw_idea, read_file, team_sizes, to_score

idea = json.loads((HERE / "examples" / "ideas.json").read_text(encoding="utf-8"))[0]
for field in idea["rice_inputs"].values():
    if isinstance(field, dict):
        field.setdefault("source", "employee")
        field.setdefault("basis", [])
idea["rice_inputs"].setdefault("open_questions", [])
inputs = MetricInputs.model_validate({k: idea[k] for k in ("rice_inputs", "fit_answers", "act_answers")})

rec = to_score({"id": "R1", "text": idea["transcript"]}, inputs)
for k in ("idea_id", "idea_version", "metric_name", "metric_version", "value", "rationale", "scored_at"):
    assert k in rec, k
assert rec["value"] == 85 and rec["ai_fit"]["label"] == "AI" and rec["ai_act"]["tier"] == "minimal"

risky = to_score({"id": "R2", "text": "Biometric emotion tracking of staff via webcam."}, inputs)
assert risky["ai_act"]["tier"] == "needs_review" and risky["review_required"]

files = list_files()
assert "it/systems.csv" in files and "people/" not in files and "ideas/" not in files
assert read_file("people/employees.csv").startswith("Not available")
assert read_file("../../etc/passwd").startswith("Not available")
assert read_file("company/strategy-2027.md").startswith("Not available")
for sneaky in ("./people/employees.csv", "it/../people/employees.csv", "customers/key-accounts.csv", "company/org-chart.md"):
    assert read_file(sneaky).startswith("Not available"), sneaky
assert "key-accounts.csv" not in files
assert "missing" in rec
assert "Katharina Vogel" not in read_file("company/overview.md")
assert "support: 4 people" in team_sizes()

with tempfile.TemporaryDirectory() as d:
    f = os.path.join(d, "RI-0007.md")
    open(f, "w").write('---\ntitle: "Tag tickets"\nauthor_id: E17\nid: RI-0007\n---\n\n# Tag tickets\n\n## Problem\nManual routing.\n')
    raw = load_raw_idea(f)
assert raw["id"] == "RI-0007" and "E17" not in raw["text"] and "Manual routing." in raw["text"]
print("ok: score agent tools and Score record")
