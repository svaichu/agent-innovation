"""Configurable RICE scoring.

The formula, the bands, the scales and the Confidence caps all come from
config/scoring/*.yaml. Swapping the active config re-ranks the portfolio and
the dashboard explains each move - that is a required demonstration in the
brief, and it is why nothing here is hard-coded.

Business value only. Regulatory risk never enters this number.
"""

from __future__ import annotations

import re
import sqlite3
from typing import Any

from .. import config, llm
from ..kg import query
from ..records import UseCaseRecord

SYSTEM = """\
You estimate the RICE inputs for an internal use case from what the submitter
actually wrote.

Return JSON only:
{
  "reach_value": number or null,
  "reach_units": "what is counted, e.g. tickets per month",
  "reach_evidence": "the submitter's words the number came from",
  "impact_label": "minimal" | "low" | "medium" | "high" | "massive",
  "impact_rationale": "one or two sentences",
  "impact_basis": "measured" | "estimated" | "guessed",
  "confidence_evidence": "strong" | "moderate" | "weak" | "none",
  "assumptions": ["..."],
  "what_would_raise_confidence": ["the single most useful thing to measure"]
}

Rules:
- reach_value must come from the submission. If no number was given, return
  null. Do not infer a number from the company's size.
- impact_basis is `measured` only if the figure plainly comes from a system
  ("Zendesk shows 1,250 tickets"), `estimated` if from experience with a stated
  basis, `guessed` otherwise.
- Be strict with impact. `massive` means the task essentially disappears.
- Normalise reach to a monthly figure where the submitter gave a different
  period, and say so in an assumption.
"""

IMPACT_HINTS = [
    ({"eliminate", "eliminates", "remove", "removes", "no longer", "entirely",
      "completely", "automatically", "without any"}, "high"),
    ({"halve", "half", "50%", "60%", "70%", "80%", "90%", "double"}, "high"),
    ({"faster", "quicker", "fewer", "reduce", "reduces", "save", "saves",
      "saving", "less", "cut", "cuts", "shorten", "shortens", "improve",
      "improves", "lift", "lifts", "avoid", "avoids", "speed", "deflect"},
     "medium"),
    ({"easier", "nicer", "clearer", "convenient", "helpful", "tidier"}, "low"),
]


def _bands(spec: list[dict], value: float | None) -> tuple[float | None, str]:
    """Map a raw value onto its configured band."""
    if value is None:
        return None, "not provided"
    for band in spec:
        ceiling = band.get("max")
        if ceiling is None or value <= ceiling:
            return float(band["value"]), band.get("label", str(band["value"]))
    return float(spec[-1]["value"]), spec[-1].get("label", "")


def _scale_value(spec: list[dict], label: str | None) -> tuple[float | None, str]:
    for entry in spec:
        if entry.get("label") == label:
            return float(entry["value"]), entry.get("guidance", "")
    return None, ""


def parse_reach(record: UseCaseRecord) -> tuple[float | None, str, str]:
    """A per-month count from the submitter's own words."""
    text = f"{record.value('problem')} {record.value('users_affected')} " \
           f"{record.value('expected_benefit')}"
    patterns = [
        (r"(\d[\d,.]*)\s*(?:\w+\s+){0,3}?per\s+month", 1.0),
        (r"(\d[\d,.]*)\s*(?:\w+\s+){0,3}?a\s+month", 1.0),
        (r"(\d[\d,.]*)\s*(?:\w+\s+){0,3}?per\s+week", 4.3),
        (r"(\d[\d,.]*)\s*(?:\w+\s+){0,3}?a\s+week", 4.3),
        (r"(\d[\d,.]*)\s*(?:\w+\s+){0,3}?per\s+day", 20.0),
        (r"(\d[\d,.]*)\s*(?:\w+\s+){0,3}?per\s+year", 1 / 12),
        (r"(\d[\d,.]*)\s*(?:\w+\s+){0,3}?per\s+quarter", 1 / 3),
    ]
    for pattern, multiplier in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            digits = match.group(1).replace(",", "").rstrip(".")
            if not digits:
                continue
            raw = float(digits)
            unit = re.search(r"per\s+(\w+)|a\s+(\w+)", match.group(0),
                             re.IGNORECASE)
            period = (unit.group(1) or unit.group(2)) if unit else "month"
            note = (f"'{match.group(0).strip()}'"
                    + ("" if period == "month"
                       else f", normalised from per {period} to per month"))
            return round(raw * multiplier), note, period
    # A bare count with no period is not a reach figure.
    return None, "", ""


def offline_inputs(record: UseCaseRecord) -> dict:
    reach, evidence, period = parse_reach(record)
    benefit = record.value("expected_benefit").lower()
    found = query.tokens(benefit)

    impact = "low"
    for cues, label in IMPACT_HINTS:
        if found & cues:
            impact = label
            break
    if not record.get("expected_benefit").is_usable:
        impact = "minimal"

    has_number = bool(re.search(r"\d", benefit))
    if has_number and reach is not None:
        basis, confidence = "estimated", "moderate"
    elif has_number:
        basis, confidence = "estimated", "weak"
    else:
        basis, confidence = "guessed", "weak"
    if not record.get("expected_benefit").is_usable:
        basis, confidence = "guessed", "none"

    assumptions = []
    if reach is None:
        assumptions.append(
            "No countable reach figure was given, so Reach is unscored and "
            "flagged for review rather than guessed.")
    if period and period != "month":
        assumptions.append(f"Reach normalised from per {period} to per month.")

    return {
        "reach_value": reach,
        "reach_units": "cases per month" if reach else "",
        "reach_evidence": evidence,
        "impact_label": impact,
        "impact_rationale": ("Derived from the wording of the expected benefit "
                             "by rule, not by model."),
        "impact_basis": basis,
        "confidence_evidence": confidence,
        "assumptions": assumptions,
        "what_would_raise_confidence": [
            "A measured figure for how often the problem occurs."
        ] if reach is None else [],
    }


def _confidence_with_caps(spec: dict, label: str, record: UseCaseRecord,
                          impact_basis: str) -> tuple[float, list[str]]:
    value, _ = _scale_value(spec["scale"], label)
    if value is None:
        value = float(spec.get("missing", {}).get("value", 0.3))
    applied: list[str] = []
    for cap in spec.get("caps", []):
        condition = str(cap.get("when", ""))
        ceiling = float(cap["max"])
        hit = False
        if "impact_basis == guessed" in condition and impact_basis == "guessed":
            hit = True
        else:
            field = re.match(r"core\.(\w+) is missing", condition)
            if field and not record.get(field.group(1)).is_usable:
                hit = True
        if hit and value > ceiling:
            value = ceiling
            applied.append(f"capped at {ceiling} because {condition}")
    return value, applied


def _scarcity_multiplier(spec: dict, feasibility: dict) -> tuple[float, list[str]]:
    """v2 only: queueing behind a bottleneck is a real cost."""
    skills = feasibility.get("dimensions", {}).get("skills", {})
    holders = [entry.get("holders", 0) for entry in skills.get("available", [])]
    fewest = min(holders) if holders else None

    multiplier, reasons = 1.0, []
    for rule in spec.get("rules", []):
        condition = str(rule.get("when", ""))
        factor = float(rule["multiply_effort_by"])
        match = re.match(r"unique_skill_holders <= (\d+)", condition)
        if match and fewest is not None and fewest <= int(match.group(1)):
            multiplier *= factor
            reasons.append(f"a required skill is held by only {fewest} "
                           f"{'person' if fewest == 1 else 'people'}")
            break
    return multiplier, reasons


def assess(record: UseCaseRecord, conn: sqlite3.Connection, feasibility: dict,
           config_name: str | None = None) -> tuple[dict, str]:
    name = config_name or config.DEFAULT_SCORING
    spec = config.scoring_config(name)

    inputs, model = llm.generate_json(
        SYSTEM, record.as_prompt_block(),
        offline=lambda: offline_inputs(record),
        required_keys=("impact_label", "impact_basis", "confidence_evidence"),
    )
    fallback = offline_inputs(record)
    for key, default in fallback.items():
        if key not in inputs or inputs[key] is None and key != "reach_value":
            inputs[key] = default

    reach_value = inputs.get("reach_value")
    if not isinstance(reach_value, (int, float)):
        reach_value = fallback["reach_value"]

    reach, reach_band = _bands(spec["reach"]["bands"], reach_value)
    impact, impact_guidance = _scale_value(spec["impact"]["scale"],
                                           inputs.get("impact_label"))
    confidence, caps = _confidence_with_caps(
        spec["confidence"], inputs.get("confidence_evidence", "weak"),
        record, inputs.get("impact_basis", "guessed"))

    person_days = feasibility.get("est_person_days")
    effort, effort_band = _bands(spec["effort"]["bands"], person_days)

    # v2 extras. Absent from v1, so the same code path serves both.
    cost_multiplier, cost_band = 1.0, ""
    if "cost_multiplier" in spec:
        cost_multiplier, cost_band = _bands(
            spec["cost_multiplier"]["bands"], feasibility.get("est_cost_eur"))
        cost_multiplier = cost_multiplier or 1.0
    scarcity, scarcity_reasons = 1.0, []
    if "scarcity_penalty" in spec:
        scarcity, scarcity_reasons = _scarcity_multiplier(
            spec["scarcity_penalty"], feasibility)

    unscored = [n for n, v in (("reach", reach), ("impact", impact),
                               ("effort", effort)) if v is None]
    if unscored:
        score = None
    else:
        denominator = effort * cost_multiplier * scarcity
        score = round((reach * impact * confidence) / denominator,
                      spec.get("rounding", {}).get("score", 1))

    factors = {
        "reach": {"value": reach, "raw": reach_value, "band": reach_band,
                  "units": inputs.get("reach_units", ""),
                  "evidence": inputs.get("reach_evidence", "")},
        "impact": {"value": impact, "label": inputs.get("impact_label"),
                   "guidance": impact_guidance,
                   "rationale": inputs.get("impact_rationale", ""),
                   "basis": inputs.get("impact_basis")},
        "confidence": {"value": confidence,
                       "label": inputs.get("confidence_evidence"),
                       "caps_applied": caps},
        "effort": {"value": effort, "raw": person_days, "band": effort_band,
                   "source": feasibility.get("effort_source", "unknown")},
    }
    if "cost_multiplier" in spec:
        factors["cost_multiplier"] = {
            "value": cost_multiplier, "band": cost_band,
            "raw": feasibility.get("est_cost_eur")}
    if scarcity != 1.0:
        factors["scarcity_penalty"] = {"value": scarcity,
                                       "reasons": scarcity_reasons}

    payload = {
        "score": score,
        "scored": score is not None,
        "unscored_factors": unscored,
        "config": {"name": spec.get("name", name), "file": name,
                   "version": spec.get("version"), "label": spec.get("label"),
                   "formula": spec.get("formula"),
                   "time_period": spec.get("time_period")},
        "factors": factors,
        "assumptions": inputs.get("assumptions") or [],
        "what_would_raise_confidence": inputs.get("what_would_raise_confidence") or [],
        "explanation": _explain(factors, score, spec),
        # Repeated here so the board table never has to join to read them, and
        # so it is obvious they sit outside the score.
        "reported_separately": {
            "est_cost_eur": feasibility.get("est_cost_eur"),
            "people_required": feasibility.get("people_required"),
            "feasibility_verdict": feasibility.get("verdict"),
        },
    }
    return payload, model


def _explain(factors: dict, score: float | None, spec: dict) -> str:
    if score is None:
        return ("Not scored: " + ", ".join(factors[f]["label"] if "label" in factors[f]
                                           else f
                                           for f in ("reach", "impact", "effort")
                                           if factors[f]["value"] is None)
                + " could not be determined from the submission.")
    parts = [
        f"Reach {factors['reach']['value']} ({factors['reach']['band']})",
        f"Impact {factors['impact']['value']} ({factors['impact']['label']})",
        f"Confidence {factors['confidence']['value']} "
        f"({factors['confidence']['label']})",
        f"Effort {factors['effort']['value']} ({factors['effort']['band']})",
    ]
    if "cost_multiplier" in factors:
        parts.append(f"Cost multiplier {factors['cost_multiplier']['value']} "
                     f"({factors['cost_multiplier']['band']})")
    if "scarcity_penalty" in factors:
        parts.append(f"Scarcity penalty {factors['scarcity_penalty']['value']}")
    return " x ".join(parts[:2]) + " x " + " / ".join(parts[2:]) + f" = {score}"


def rank(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Order a portfolio: scored ideas by score, unscored last."""
    return sorted(
        entries,
        key=lambda e: (e.get("score") is None, -(e.get("score") or 0),
                       e.get("use_case_id", "")),
    )
