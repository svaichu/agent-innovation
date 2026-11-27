"""Checks of everything around the score agent. No database or API key needed.

    .venv/bin/python -m unittest discover tests
"""

import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "portal"))

from checks import ai_act, screen  # noqa: E402
from idea_store import RawIdea  # noqa: E402
from innovation_dashboard import score_badges, score_reasons, sort_ideas  # noqa: E402
from knowledge import readable_documents  # noqa: E402
from score_agent import ScoreInputs  # noqa: E402
from score_ideas import assess, load_setup  # noqa: E402
from scoring import calculate, load_metric, score  # noqa: E402
from sync_knowledge_base import read_documents, read_employees  # noqa: E402

SETUP = load_setup()
RICE = load_metric(ROOT / "metrics" / "rice.md")
EXAMPLES = json.loads((ROOT / "tests" / "example_ideas.json").read_text(encoding="utf-8"))
FILES = read_documents(ROOT / "knowledge-base")
EMPLOYEES = {row[0]: row[1] for row in read_employees(FILES["people/employees.csv"])}
DOCUMENTS = readable_documents(FILES, EMPLOYEES)
IDEA = "We handle about 312 tickets per month by hand. It takes one developer a month."


def field(name, value, source="employee", evidence="about 312 tickets per month", basis=()):
    return {
        "name": name,
        "value": value,
        "source": source,
        "evidence": evidence,
        "basis": list(basis),
    }


def fields(**changes):
    """Four well supported inputs, with some replaced."""
    quote = "It takes one developer a month"
    filled = {
        "reach": field("reach", 312),
        "impact": field("impact", 2, evidence=quote),
        "confidence": field("confidence", 1.0, evidence=quote),
        "effort": field("effort", 1, evidence=quote),
    }
    return list((filled | changes).values())


def raw_idea(idea_id, text="# Title\n\n## Problem\nSlow.\n"):
    return RawIdea(
        id=idea_id,
        text=text,
        created_at=datetime.now(timezone.utc),
        version=1,
        updated_at=None,
        author_id="E17",
        author_name="Luis Ortega",
        department="support",
    )


def assess_example(example):
    filled = ScoreInputs.model_validate(
        {k: example[k] for k in ("inputs", "open_questions", "fit_answers", "act_answers")}
    )
    return assess(raw_idea(example["id"]), example["idea"], filled, DOCUMENTS, SETUP)


class Examples(unittest.TestCase):
    def test_flags_and_status(self):
        for example in EXAMPLES:
            with self.subTest(example["id"]):
                details = assess_example(example).details
                expected = example["expected"]
                self.assertEqual(details["ai_fit"]["label"], expected["ai_fit"])
                self.assertEqual(details["ai_act"]["tier"], expected["tier"])
                self.assertEqual(details["status"], expected["status"])
                if expected.get("transparency"):
                    self.assertTrue(details["ai_act"]["transparency"])
                    self.assertTrue(details["review_required"])

    def test_dashboard_ranks_and_shows_them(self):
        scores = {e["id"]: assess_example(e) for e in EXAMPLES}
        ideas = [raw_idea("new"), *(raw_idea(e["id"]) for e in EXAMPLES)]
        ranked = sort_ideas(ideas, "Highest score", scores)
        values = [scores[i.id].value for i in ranked[:-2]]
        self.assertEqual(values, sorted(values, reverse=True))
        self.assertEqual([i.id for i in ranked[-2:]], ["ai-for-sales", "new"])
        self.assertIn("Score pending", score_badges(None))
        for idea in ranked[:-1]:
            self.assertIn("EU AI Act", score_badges(scores[idea.id]))
            self.assertIn("not legal advice", score_reasons(scores[idea.id]))


class Evidence(unittest.TestCase):
    def result(self, **changes):
        return score(RICE, fields(**changes), IDEA, DOCUMENTS)

    def test_supported_inputs(self):
        self.assertEqual(self.result()["value"], 70)

    def test_number_must_be_in_the_quote(self):
        result = self.result(reach=field("reach", 100000))
        self.assertEqual(result["status"], "needs_info")
        self.assertIn("does not contain the number", result["open_questions"][0])

    def test_invented_quotes_and_unusable_values_are_dropped(self):
        bad = [
            field("reach", 312, evidence="312 tickets every single day"),
            field("reach", 312, evidence=None),
            field("reach", 312, source=None),
            field("reach", -5),
            field("reach", float("nan")),
            field("reach", float("inf")),
            field("reach", 1e9),
            field("reach", 312, "estimate", "guess", ["departments/support.md: made up fact"]),
            field("reach", 312, "estimate", "guess", []),
        ]
        for item in bad:
            with self.subTest(item):
                self.assertEqual(self.result(reach=item)["status"], "needs_info")

    def test_knowledge_base_quote(self):
        item = field(
            "reach",
            312,
            "knowledge_base",
            "knowledge-base/departments/support.md: | Tickets per month | 312 |",
        )
        self.assertEqual(self.result(reach=item)["value"], 70)

    def test_hidden_documents_are_not_evidence(self):
        for quote in (
            "company/strategy-2027.md: about 15 person-days per month",
            "people/employees.csv: E01,Katharina Vogel",
            "departments/../company/strategy-2027.md: Grow recurring revenue",
        ):
            with self.subTest(quote):
                item = field("effort", 1, "estimate", "derived", [quote])
                self.assertEqual(self.result(effort=item)["status"], "needs_info")

    def test_only_an_estimated_reach_lowers_confidence(self):
        basis = ["It takes one developer a month"]
        judged = {
            name: field(name, value, "estimate", "judged", basis)
            for name, value in (("impact", 2), ("confidence", 1.0), ("effort", 1))
        }
        self.assertEqual(self.result(**judged)["value"], 70)
        reach = self.result(reach=field("reach", 312, "estimate", "guess", basis))
        self.assertIn("confidence 0.5", reach["rationale"])
        self.assertLess(reach["value"], 70)

    def test_unknown_impact_uses_the_lowest_anchor(self):
        result = self.result(impact=field("impact", 7))
        self.assertEqual(result["missing"], ["impact"])
        self.assertIn("impact 0.25, confidence 0.5", result["rationale"])


class Metrics(unittest.TestCase):
    def write(self, text):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "metric.md"
        path.write_text(text, encoding="utf-8")
        return path

    def test_another_metric_needs_no_code(self):
        metric = load_metric(
            self.write(
                "---\nname: ease\nversion: 1\nscale: 0-100\n---\n"
                "```yaml\nformula: 10 * ease\ninputs:\n"
                "  ease:\n    anchors: [1, 5, 10]\n    default: 1\n```\n"
            )
        )
        quote = "It takes one developer a month"
        result = score(metric, [field("ease", 5, evidence=quote)], IDEA, DOCUMENTS)
        self.assertEqual((result["value"], metric.version), (50, 1))

    def test_broken_metric_files_are_rejected(self):
        good = (ROOT / "metrics" / "rice.md").read_text(encoding="utf-8")
        for old, new in (
            ("version: 3", "version: three"),
            ("scale: 0-100", "scale: flags"),
            ("reach * impact", "audience * impact"),
            ("    default: 0.25", "    deafult: 0.25"),
        ):
            with self.subTest(new), self.assertRaises(ValueError):
                load_metric(self.write(good.replace(old, new)))

    def test_formula_is_arithmetic_only(self):
        for formula in (
            "__import__('os').system('true')",
            "x.real",
            "open('f')",
            "x if x else 1",
            "10 ** 10 ** 10",
            "x / 0",
        ):
            with self.subTest(formula), self.assertRaises(ValueError):
                calculate(formula, {"x": 1.0})


class Knowledge(unittest.TestCase):
    def test_confidential_and_personal_documents_are_hidden(self):
        for path in (
            "company/strategy-2027.md",
            "customers/key-accounts.md",
            "customers/key-accounts.csv",
            "company/org-chart.md",
            "people/employees.csv",
        ):
            self.assertNotIn(path, DOCUMENTS)
        self.assertIn("it/systems.csv", DOCUMENTS)
        self.assertEqual(readable_documents({"a.md": "no front matter"}, {}), {})

    def test_no_employee_name_remains(self):
        text = "\n".join(DOCUMENTS.values())
        for name in EMPLOYEES.values():
            self.assertNotIn(name, text)
        self.assertIn("| E16 | E16 |", DOCUMENTS["departments/support.md"])


class Checks(unittest.TestCase):
    harmless = {
        "art5_practices": [],
        "art50": [],
        "annex_iii_area": "none",
        "annex_i_safety_component": False,
        "profiles_people": False,
        "narrow_or_preparatory": True,
    }

    def tier(self, **changes):
        return ai_act(self.harmless | changes, SETUP.checks)["tier"]

    def test_unanswered_or_unknown_is_never_minimal(self):
        for changes in (
            {"art5_practices": "social_scoring"},
            {"art5_practices": ["emotion_recognition"]},
            {"annex_i_safety_component": "true"},
            {"annex_iii_area": None},
        ):
            with self.subTest(changes):
                self.assertEqual(self.tier(**changes), "needs_review")

    def test_annex_paths(self):
        self.assertEqual(self.tier(annex_i_safety_component=True), "high-risk")
        employment = {"annex_iii_area": "employment"}
        self.assertTrue(self.tier(**employment).startswith("not high-risk"))
        self.assertEqual(self.tier(**employment, profiles_people=True), "high-risk")
        self.assertEqual(self.tier(**employment, art5_practices=None), "high-risk")

    def test_risk_terms(self):
        def tier(idea):
            return screen({}, self.harmless, idea, SETUP.checks)["ai_act"]["tier"]

        for idea in (
            "Rank the applicants.",
            "Screen CVs.",
            "Biometric door access.",
            "Bewerbungen automatisch sortieren.",
            "Gesichtserkennung am Eingang.",
        ):
            with self.subTest(idea):
                self.assertEqual(tier(idea), "needs_review")
        for idea in (
            "For example, we examine parts.",
            "Send the credit note automatically.",
            "Fewer face-to-face meetings.",
            "Update the policy page.",
        ):
            with self.subTest(idea):
                self.assertEqual(tier(idea), "minimal")


if __name__ == "__main__":
    unittest.main()
