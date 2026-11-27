"""The metric: a skill file, and the arithmetic that turns its inputs into a score.

The score agent only fills the inputs. Everything here is deterministic: the same
inputs and metric file always give the same score.
"""

import ast
import math
import operator
import re
from dataclasses import dataclass
from pathlib import Path

import yaml

MIN_QUOTE = 8
MAX_NUMBER = 1e7
INPUT_SETTINGS = {
    "unit",
    "required",
    "default",
    "anchors",
    "min",
    "flag_above",
    "quote_must_contain_value",
    "estimate_is_expected",
}
OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
}
FUNCTIONS = {"log": math.log, "log10": math.log10, "sqrt": math.sqrt, "min": min, "max": max}


@dataclass(frozen=True)
class Metric:
    name: str
    version: int
    formula: str
    inputs: dict[str, dict]
    caps: dict[str, float]
    # The whole file, which is what the agent reads.
    text: str


def front_matter(text: str) -> dict:
    parts = text.split("---\n", 2)
    if len(parts) != 3 or parts[0]:
        raise ValueError("missing front matter")
    return yaml.safe_load(parts[1]) or {}


def calculate(formula: str, values: dict[str, float]) -> float:
    """Evaluate the formula. Only arithmetic is allowed, never other Python."""

    def visit(node: ast.AST) -> float:
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            return float(node.value)
        if isinstance(node, ast.Name) and node.id in values:
            return float(values[node.id])
        if isinstance(node, ast.BinOp) and type(node.op) in OPERATORS:
            return OPERATORS[type(node.op)](visit(node.left), visit(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in OPERATORS:
            return OPERATORS[type(node.op)](visit(node.operand))
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in FUNCTIONS
            and not node.keywords
        ):
            return FUNCTIONS[node.func.id](*(visit(argument) for argument in node.args))
        raise ValueError(f"not allowed in a formula: {ast.unparse(node)}")

    try:
        result = visit(ast.parse(formula, mode="eval").body)
    except (ArithmeticError, SyntaxError, TypeError) as error:
        raise ValueError(f"formula cannot be calculated: {error}") from error
    if not isinstance(result, float) or not math.isfinite(result):
        raise ValueError("formula does not give a finite number")
    return result


def load_metric(path: Path) -> Metric:
    """Read and check a metric skill file. ValueError says what is wrong with it."""
    text = Path(path).read_text(encoding="utf-8")
    try:
        front = front_matter(text)
        block = re.search(r"^```yaml\n(.*?)^```", text, re.S | re.M)
        if not block:
            raise ValueError("missing the yaml block")
        config = yaml.safe_load(block.group(1))
        name, version = front.get("name"), front.get("version")
        if not isinstance(name, str) or type(version) is not int:
            raise ValueError("name must be text and version an integer")
        if front.get("scale") != "0-100":
            raise ValueError("scale must be 0-100")
        inputs, formula = config["inputs"], config["formula"]
        caps = config.get("caps") or {}
        for key, settings in inputs.items():
            if unknown := set(settings) - INPUT_SETTINGS:
                raise ValueError(f"{key}: unknown settings {sorted(unknown)}")
            if not settings.get("required") and "default" not in settings:
                raise ValueError(f"{key}: needs 'required: true' or a 'default'")
        if unknown := set(caps) - set(inputs):
            raise ValueError(f"caps for unknown inputs {sorted(unknown)}")
        # A trial calculation finds unknown names and disallowed syntax now.
        calculate(formula, {key: 1.0 for key in inputs})
    except (KeyError, TypeError, AttributeError, yaml.YAMLError, ValueError) as error:
        raise ValueError(f"{path}: invalid metric file: {error!r}") from error
    return Metric(name, version, formula, inputs, caps, text)


def _normal(text: str) -> str:
    return " ".join(text.lower().split())


def _numbers(text: str) -> set[float]:
    """The numbers written in a text, reading both 1,000 and 1.000 as a thousand."""
    found = set()
    for token in re.findall(r"\d+(?:[.,]\d+)*", text):
        readings = [token.replace(",", "")]
        if re.fullmatch(r"\d{1,3}(\.\d{3})+", token):
            readings.append(token.replace(".", ""))
        if re.fullmatch(r"\d+,\d{1,2}", token):
            readings.append(token.replace(",", "."))
        for reading in readings:
            try:
                found.add(float(reading))
            except ValueError:
                pass  # Something like a version number, 1.2.3.
    return found


def idea_quote(quote: object, idea: str) -> str | None:
    """The quoted text, if it really is in the idea."""
    if not isinstance(quote, str):
        return None
    text = quote.strip().strip('"')
    return text if len(text) >= MIN_QUOTE and _normal(text) in _normal(idea) else None


def document_quote(quote: object, documents: dict[str, str]) -> str | None:
    """The quoted text of "<path>: <text>", if that readable document contains it."""
    if not isinstance(quote, str):
        return None
    path, _, text = quote.strip().partition(":")
    content = documents.get(path.strip().removeprefix("knowledge-base/"))
    text = text.strip().strip('"')
    if content is None or len(text) < MIN_QUOTE or _normal(text) not in _normal(content):
        return None
    return text


def _check(value, field: dict, settings: dict, idea: str, documents: dict) -> str | None:
    """Why this value cannot be used, or None if it can."""
    if type(value) not in (int, float) or not 0 <= value <= MAX_NUMBER:
        return "not a usable number"
    if "anchors" in settings and value not in settings["anchors"]:
        return f"not on the scale {settings['anchors']}"
    source, evidence = field.get("source"), field.get("evidence")
    if source == "estimate":
        basis = field.get("basis") or []
        if basis and all(
            idea_quote(item, idea) or document_quote(item, documents) for item in basis
        ):
            return None
        return "the facts behind the estimate were not found"
    if source == "employee":
        quoted = idea_quote(evidence, idea)
    elif source == "knowledge_base":
        quoted = document_quote(evidence, documents)
    else:
        return "no source given"
    if quoted is None:
        return "the quoted evidence was not found"
    if settings.get("quote_must_contain_value") and value not in _numbers(quoted):
        return "the quoted evidence does not contain the number"
    return None


def score(
    metric: Metric,
    fields: list[dict],
    idea: str,
    documents: dict[str, str],
    open_questions: list[str] = (),
) -> dict:
    """Check the evidence of every input, then calculate the score.

    Args:
        fields: What the agent filled in: name, value, source, evidence, basis.
        idea: The idea text the agent read.
        documents: The knowledge base documents the agent could read, by path.
    """
    given = {}
    for field in fields:
        given.setdefault(field.get("name"), field)

    inputs, questions, flags = {}, list(open_questions), []
    for name, settings in metric.inputs.items():
        field = given.get(name) or {}
        value = field.get("value")
        if value is not None and (problem := _check(value, field, settings, idea, documents)):
            questions.append(f"{name}: value {value!r} was not used, {problem}.")
            value = None
        inputs[name] = {
            "value": value,
            "source": field.get("source") if value is not None else None,
            "evidence": field.get("evidence") if value is not None else None,
            "basis": field.get("basis") or [] if value is not None else [],
        }

    missing = [name for name, item in inputs.items() if item["value"] is None]
    estimated = [name for name, item in inputs.items() if item["source"] == "estimate"]
    result = {
        "inputs": inputs,
        "missing": missing,
        "estimated": estimated,
        "open_questions": questions,
        "flags": flags,
    }
    if unknown := [name for name in missing if metric.inputs[name].get("required")]:
        return {
            **result,
            "status": "needs_info",
            "value": None,
            "rationale": f"No score: {', '.join(unknown)} unknown.",
        }

    used = {}
    for name, settings in metric.inputs.items():
        value = inputs[name]["value"]
        value = settings["default"] if value is None else value
        used[name] = max(value, settings.get("min", value))
        if "flag_above" in settings and used[name] > settings["flag_above"]:
            flags.append(f"{name} {used[name]:g} is above {settings['flag_above']:g}.")
    unsure = missing + [
        name for name in estimated if not metric.inputs[name].get("estimate_is_expected")
    ]
    if unsure:
        for name, cap in metric.caps.items():
            used[name] = min(used[name], cap)

    value = max(0, min(100, round(calculate(metric.formula, used))))
    rationale = ", ".join(f"{name} {number:g}" for name, number in used.items())
    rationale = f"{rationale} -> {value}/100."
    if estimated:
        rationale += f" Estimated: {', '.join(estimated)}."
    if missing:
        rationale += f" Unknown, default used: {', '.join(missing)}."
    if unsure and metric.caps:
        rationale += f" Limited because of that: {', '.join(metric.caps)}."
    return {**result, "status": "scored", "value": value, "rationale": rationale}
