import hashlib
import json
import math
import re
from pathlib import Path

HERE = Path(__file__).parent
KB = (HERE.parent / "knowledge-base").resolve()
MAX_NUMBER = 1e7
MIN_QUOTE = 8
RICE_KEYS = ("reach", "impact", "confidence", "effort")
RISK_TERMS = re.compile(
    r"\b(emotion|biometric|face|facial|webcam|surveil|monitor\w* (staff|employee|agent)|hiring|recruit|"
    r"applicant|cv|candidate|performance review|promotion|dismiss|termination|credit|insurance|"
    r"school|student|exam|police|migration|deepfake|manipulat)",
    re.I,
)


def load_metric(path: Path) -> tuple[dict, dict, str]:
    text = Path(path).read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise ValueError(f"{path}: missing front matter")
    front = dict(re.findall(r"^(\w+):\s*(.+)$", text.split("---\n")[1], re.M))
    block = re.search(r"```json\n(.*?)```", text, re.S)
    cfg_text = block.group(1) if block else "{}"
    return front, json.loads(cfg_text), hashlib.sha256(cfg_text.encode()).hexdigest()[:12]


def _rice_config(cfg: dict) -> dict:
    need = ("impact_anchors", "confidence_anchors", "missing_input_confidence", "estimate_confidence",
            "min_effort", "effort_flag_above", "rice_cap")
    missing = [k for k in need if k not in cfg]
    if missing or cfg["rice_cap"] <= 0 or cfg["min_effort"] <= 0:
        raise ValueError(f"rice.md config invalid (missing {missing}, rice_cap and min_effort must be > 0)")
    return cfg


def _number(x) -> float | None:
    if isinstance(x, bool) or not isinstance(x, (int, float)):
        return None
    try:
        x = float(x)
    except OverflowError:
        return None
    return x if math.isfinite(x) and 0 <= x <= MAX_NUMBER else None


def _value(field):
    return field.get("value") if isinstance(field, dict) else None


def _strings(x, limit: int = 20) -> list[str]:
    return [s[:300] for s in x[:limit] if isinstance(s, str)] if isinstance(x, list) else []


def _norm(s: str) -> str:
    return " ".join(s.lower().split())


def _quote(x) -> str:
    return x.strip().strip('"') if isinstance(x, str) else ""


def kb_quote_ok(quote: str) -> bool:
    rel, _, text = _quote(quote).partition(":")
    if not rel.startswith("knowledge-base/"):
        return False
    path = (KB.parent / rel.strip()).resolve()
    if not path.is_relative_to(KB) or not path.is_file() or len(text.strip()) < MIN_QUOTE:
        return False
    return _norm(text) in _norm(path.read_text(encoding="utf-8", errors="ignore"))


def _source_ok(field: dict, transcript: str) -> bool:
    evidence = _quote(field.get("evidence"))
    source = field.get("source") or ("knowledge_base" if evidence.startswith("knowledge-base/") else "employee")
    if source == "knowledge_base":
        return kb_quote_ok(evidence)
    if source == "estimate":
        basis = field.get("basis")
        return isinstance(basis, list) and bool(basis) and all(kb_quote_ok(b) for b in basis)
    return source == "employee" and len(evidence) >= MIN_QUOTE and _norm(evidence) in _norm(transcript)


def check_evidence(inputs: dict, transcript: str) -> tuple[list[str], list[str]]:
    dropped, estimated = [], []
    for name in RICE_KEYS:
        field = inputs.get(name)
        if not isinstance(field, dict) or field.get("value") is None:
            continue
        if not _source_ok(field, transcript):
            field["value"] = None
            dropped.append(name)
        elif field.get("source") == "estimate":
            estimated.append(name)
    return dropped, estimated


def rice_score(inputs: dict, estimated: list[str] = (), metric: Path = HERE / "rice.md") -> dict:
    front, cfg, sha = load_metric(metric)
    cfg = _rice_config(cfg)
    inputs = inputs if isinstance(inputs, dict) else {}
    reach, effort = _number(_value(inputs.get("reach"))), _number(_value(inputs.get("effort")))
    impact, conf = _value(inputs.get("impact")), _value(inputs.get("confidence"))
    questions = _strings(inputs.get("open_questions"))
    if impact is not None and (isinstance(impact, bool) or impact not in cfg["impact_anchors"]):
        questions.append(f"Impact is not on the scale {cfg['impact_anchors']}.")
        impact = None
    if conf is not None and (isinstance(conf, bool) or conf not in cfg["confidence_anchors"]):
        questions.append(f"Confidence is not on the scale {cfg['confidence_anchors']}.")
        conf = None
    missing = [k for k, v in zip(RICE_KEYS, (reach, impact, conf, effort)) if v is None]
    estimated = [k for k in estimated if k not in missing]
    result = {"metric_name": front.get("name"), "metric_version": front.get("version"), "config_sha": sha,
              "missing": missing, "estimated": estimated, "open_questions": questions, "flags": []}
    if reach is None or effort is None:
        return {**result, "status": "needs_info", "value": None,
                "rationale": f"No score: {', '.join(missing)} unknown and not inferable from the knowledge base."}
    impact = impact if impact is not None else min(cfg["impact_anchors"])
    conf = conf if conf is not None else 1.0
    if missing:
        conf = min(conf, cfg["missing_input_confidence"])
    if estimated:
        conf = min(conf, cfg["estimate_confidence"])
    effort = max(effort, cfg["min_effort"])
    rice = reach * impact * conf / effort
    value = min(100, round(100 * math.log10(1 + rice) / math.log10(1 + cfg["rice_cap"])))
    if effort > cfg["effort_flag_above"]:
        result["flags"].append(f"Effort {effort:g} person-months is above {cfg['effort_flag_above']}: check capacity.")
    rationale = f"RICE = {reach:g} x {impact:g} x {conf:g} / {effort:g} = {rice:.1f} -> {value}/100."
    if estimated:
        rationale += f" Estimated from the knowledge base: {', '.join(estimated)}."
    if missing:
        rationale += f" Missing {', '.join(missing)}: used lowest impact / confidence {conf:g}."
    return {**result, "status": "scored", "value": value, "rice": round(rice, 1), "rationale": rationale,
            "breakdown": {"reach": reach, "impact": impact, "confidence": conf, "effort": effort}}


def _bool(a: dict, k: str) -> bool | None:
    v = a.get(k)
    return v if isinstance(v, bool) else None


def ai_fit(a) -> dict:
    a = a if isinstance(a, dict) else {}
    yes = lambda k: _bool(a, k) is True
    if yes("low_volume_low_value"):
        return {"label": "more research", "rule": 1, "reason": "Rare and low value: probably not worth automating."}
    if yes("structured_input") and yes("rule_expressible") and _bool(a, "needs_judgement") is False:
        return {"label": "conventional automation", "rule": 2, "reason": "Structured input and clear rules, no judgement."}
    if yes("prediction_task") and not yes("has_historical_data"):
        return {"label": "more research", "rule": 3, "reason": "Prediction task, but usable data is missing or unknown."}
    if yes("deterministic_required"):
        return {"label": "conventional automation", "rule": 4, "reason": "The same input must always give the same result."}
    if yes("unstructured_or_language") or yes("needs_judgement") or yes("prediction_task"):
        return {"label": "AI", "rule": 5, "reason": "Language, judgement or prediction with data: AI adds value."}
    return {"label": "more research", "rule": 6, "reason": "Not enough information to decide."}


def _ids(a: dict, k: str, known: dict) -> tuple[list[str], str | None]:
    v = a.get(k)
    if not isinstance(v, list) or not all(isinstance(x, str) for x in v):
        return [], f"{k}: missing or not a list of ids"
    bad = [x for x in v if x not in known]
    return [x for x in v if x in known], (f"{k}: unknown ids {bad[:5]}" if bad else None)


def ai_act(a, metric: Path = HERE / "checks.md") -> dict:
    _, cfg, _ = load_metric(metric)
    a = a if isinstance(a, dict) else {}
    art5, p5 = _ids(a, "art5_practices", cfg["art5"])
    art50, p50 = _ids(a, "art50", cfg["art50"])
    area = a.get("annex_iii_area") if isinstance(a.get("annex_iii_area"), str) else None
    problems = [p for p in (p5, p50) if p]
    if area is not None and area != "none" and area not in cfg["annex_iii"]:
        problems.append(f"annex_iii_area: unknown id {area[:40]!r}")
    for k in ("annex_i_safety_component", "profiles_people", "narrow_or_preparatory"):
        if _bool(a, k) is None:
            problems.append(f"{k}: missing or not true/false")
    out = {"transparency": [f"{cfg['art50'][k]} ({cfg['dates']['art50']})" for k in art50], "citations": [],
           "problems": problems, "answers": a, "disclaimer": "Preliminary screening, not legal advice."}
    if art5:
        return {**out, "tier": "prohibited", "citations": [cfg["art5"][k] for k in art5], "applies": cfg["dates"]["prohibited"]}
    if _bool(a, "annex_i_safety_component") is True:
        return {**out, "tier": "high-risk", "citations": ["Art. 6(1) and Annex I"], "applies": cfg["dates"]["high_risk_annex_i"]}
    if area in cfg["annex_iii"]:
        cite = [cfg["annex_iii"][area]]
        if (_bool(a, "profiles_people") is False and _bool(a, "narrow_or_preparatory") is True
                and _bool(a, "annex_i_safety_component") is False):
            return {**out, "tier": "not high-risk (Art. 6(3) exception, document and register)",
                    "citations": cite + ["Art. 6(3), 6(4), Art. 49(2)"]}
        return {**out, "tier": "high-risk", "citations": cite, "applies": cfg["dates"]["high_risk_annex_iii"]}
    if problems or area is None:
        return {**out, "tier": "needs_review"}
    return {**out, "tier": "minimal"}


def evaluate(idea) -> dict:
    idea = idea if isinstance(idea, dict) else {}
    inputs = json.loads(json.dumps(idea.get("rice_inputs") if isinstance(idea.get("rice_inputs"), dict) else {}))
    transcript = idea.get("transcript") if isinstance(idea.get("transcript"), str) else ""
    dropped, estimated = check_evidence(inputs, transcript)
    score = rice_score(inputs, estimated)
    if dropped:
        score["open_questions"].append(f"Evidence missing or not found for: {', '.join(dropped)}.")
    act = ai_act(idea.get("act_answers"))
    hits = sorted({m.group(0).lower() for m in RISK_TERMS.finditer(transcript)})
    if act["tier"] == "minimal" and hits:
        act = {**act, "tier": "needs_review", "problems": act["problems"] + [f"risk terms in the idea: {hits[:5]}"]}
    return {"id": str(idea.get("id", "?"))[:80], "score": score, "ai_fit": ai_fit(idea.get("fit_answers")),
            "ai_act": act, "review_required": act["tier"] != "minimal" or bool(act["transparency"]),
            "checked_inputs": inputs}


def _reject_constant(c):
    raise ValueError(f"invalid number {c}")


if __name__ == "__main__":
    text = (HERE / "examples" / "ideas.json").read_text(encoding="utf-8")
    rows = []
    for idea in json.loads(text, parse_constant=_reject_constant):
        try:
            rows.append(evaluate(idea))
        except Exception as e:
            rows.append({"id": str(idea.get("id", "?"))[:80], "error": type(e).__name__})
    rows.sort(key=lambda r: (r.get("score", {}).get("value") is None, -(r.get("score", {}).get("value") or 0)))
    for r in rows:
        if "error" in r:
            print(f"{r['id']:<28} error: {r['error']}")
        else:
            print(f"{r['id']:<28} {str(r['score']['value']):>5}  {r['ai_fit']['label']:<24} {r['ai_act']['tier']}")
