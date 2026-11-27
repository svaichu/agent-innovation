"""AI fit and EU AI Act screening: flags next to the score, never part of it.

The rules and their sources are described in metrics/checks.md.
"""

import json
import re
from pathlib import Path


def load_checks(path: Path) -> tuple[dict, str]:
    """The lists in the checks file, and the whole text, which the agent reads."""
    text = Path(path).read_text(encoding="utf-8")
    block = re.search(r"^```json\n(.*?)^```", text, re.S | re.M)
    if not block:
        raise ValueError(f"{path}: missing the json block")
    return json.loads(block.group(1)), text


def _bool(answers: dict, key: str) -> bool | None:
    value = answers.get(key)
    return value if isinstance(value, bool) else None


def ai_fit(answers: dict) -> dict:
    """AI, conventional automation or more research. The first matching rule wins."""

    def yes(key: str) -> bool:
        return _bool(answers, key) is True

    def result(label: str, rule: int, reason: str) -> dict:
        return {"label": label, "rule": rule, "reason": reason}

    if yes("low_volume_low_value"):
        return result("more research", 1, "Rare and low value: probably not worth automating.")
    if (
        yes("structured_input")
        and yes("rule_expressible")
        and _bool(answers, "needs_judgement") is False
    ):
        return result(
            "conventional automation", 2, "Structured input and clear rules, no judgement."
        )
    if yes("prediction_task") and not yes("has_historical_data"):
        return result("more research", 3, "Prediction task, but usable data is missing or unknown.")
    if yes("deterministic_required"):
        return result("conventional automation", 4, "The same input must always give the same result.")
    if yes("unstructured_or_language") or yes("needs_judgement") or yes("prediction_task"):
        return result("AI", 5, "Language, judgement or prediction with data: AI adds value.")
    return result("more research", 6, "Not enough information to decide.")


def _ids(answers: dict, key: str, known: dict) -> tuple[list[str], str | None]:
    value = answers.get(key)
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        return [], f"{key}: not answered"
    unknown = [item for item in value if item not in known]
    problem = f"{key}: unknown ids {unknown[:5]}" if unknown else None
    return [item for item in value if item in known], problem


def ai_act(answers: dict, lists: dict) -> dict:
    """The preliminary risk tier, with the articles it rests on."""
    banned, banned_problem = _ids(answers, "art5_practices", lists["art5"])
    art50, art50_problem = _ids(answers, "art50", lists["art50"])
    area = answers.get("annex_iii_area")
    area = area if isinstance(area, str) else None
    problems = [problem for problem in (banned_problem, art50_problem) if problem]
    if area is None:
        problems.append("annex_iii_area: not answered")
    elif area != "none" and area not in lists["annex_iii"]:
        problems.append(f"annex_iii_area: unknown id {area[:40]!r}")
    for key in ("annex_i_safety_component", "profiles_people", "narrow_or_preparatory"):
        if _bool(answers, key) is None:
            problems.append(f"{key}: not answered")

    dates = lists["dates"]

    def result(tier: str, citations: list[str] = (), applies: str | None = None) -> dict:
        return {
            "tier": tier,
            "citations": list(citations),
            "applies": applies,
            "transparency": [f"{lists['art50'][key]} ({dates['art50']})" for key in art50],
            "problems": problems,
        }

    if banned:
        return result("prohibited", [lists["art5"][key] for key in banned], dates["prohibited"])
    if _bool(answers, "annex_i_safety_component") is True:
        return result("high-risk", ["Art. 6(1) and Annex I"], dates["high_risk_annex_i"])
    if area in lists["annex_iii"]:
        citation = lists["annex_iii"][area]
        # The exception needs every question answered.
        if (
            not problems
            and _bool(answers, "profiles_people") is False
            and _bool(answers, "narrow_or_preparatory") is True
        ):
            return result(
                "not high-risk (Art. 6(3) exception, document and register)",
                [citation, "Art. 6(3), 6(4), Art. 49(2)"],
            )
        return result("high-risk", [citation], dates["high_risk_annex_iii"])
    return result("needs_review" if problems else "minimal")


def screen(fit_answers: dict, act_answers: dict, idea: str, lists: dict) -> dict:
    """Both checks, and whether a person has to review the idea."""
    act = ai_act(act_answers, lists)
    # A second line of defence in case the agent answers a risky idea harmlessly.
    hits = sorted(
        {
            match.group(0).lower()
            for term in lists["risk_terms"]
            for match in re.finditer(rf"\b(?:{term})", idea, re.IGNORECASE)
        }
    )
    if act["tier"] == "minimal" and hits:
        act["tier"] = "needs_review"
        act["problems"] = [*act["problems"], f"risk terms in the idea: {', '.join(hits[:5])}"]
    return {
        "ai_fit": ai_fit(fit_answers),
        "ai_act": act,
        "review_required": act["tier"] != "minimal" or bool(act["transparency"]),
        # Unverified, so kept for a person to confirm.
        "answers": {"ai_fit": fit_answers, "ai_act": act_answers},
    }
