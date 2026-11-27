"""The core use-case record, and adapters that produce one.

Two sources feed the same record shape:

1. employee_interface writes markdown to knowledge-base/ideas/raw/RI-NNNN.md
   with seven fields of its own. Four of them map onto core fields; the other
   four core fields (deployment context, data, effort, human oversight) are not
   collected there yet, so they arrive as `missing`. They are NOT inferred -
   the brief forbids inventing facts, and a guessed deployment context would
   corrupt the Article 50 screening. They become review items instead.

2. seed/data/use_cases.json carries all eight fields, for the demo portfolio.

config/intake-questionnaire.yaml is the authority on which fields exist.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from . import config

FieldState = Literal["provided", "unclear", "missing", "assumed"]

# employee_interface section heading -> core field key.
# Only mappings that are genuinely the same question are listed here.
SECTION_TO_CORE = {
    "Problem": "problem",
    "Proposed improvement": "intended_purpose",
    "Who is affected": "users_affected",
    "Expected benefit": "expected_benefit",
}

# Sections that give useful context but are not a core field on their own.
CONTEXT_SECTIONS = ["Scope", "Current process"]

NOT_COLLECTED_BY_EMPLOYEE_INTERFACE = [
    "deployment_context", "data", "effort", "human_oversight",
]

# Phrases a submitter uses when they genuinely do not know. Treated as an
# answered-but-unknown field rather than silence, because it changes the
# follow-up: there is no point asking again.
UNKNOWN_MARKERS = (
    "unknown", "not known", "no idea", "nicht bekannt", "weiss nicht",
    "weiß nicht", "unclear", "tbd", "to be determined", "n/a",
)


@dataclass
class CoreField:
    key: str
    value: str = ""
    state: FieldState = "missing"
    evidence: str = ""

    @property
    def is_usable(self) -> bool:
        return self.state == "provided" and bool(self.value.strip())


@dataclass
class UseCaseRecord:
    id: str
    title: str
    author_id: str = ""
    department: str = ""
    source: str = "seed"
    source_path: str = ""
    created_at: str = ""
    status: str = "submitted"
    version: int = 1
    fields: dict[str, CoreField] = field(default_factory=dict)
    context: dict[str, str] = field(default_factory=dict)
    derived: dict[str, Any] = field(default_factory=dict)

    def get(self, key: str) -> CoreField:
        return self.fields.get(key, CoreField(key=key))

    def value(self, key: str) -> str:
        return self.get(key).value

    def missing_fields(self) -> list[str]:
        return [k for k in config.core_field_keys()
                if not self.get(k).is_usable]

    def missing_required(self) -> list[str]:
        return [k for k in config.required_field_keys()
                if not self.get(k).is_usable]

    def completeness(self) -> tuple[int, int]:
        keys = config.core_field_keys()
        return sum(1 for k in keys if self.get(k).is_usable), len(keys)

    def searchable_text(self) -> str:
        """What similarity search compares. Context included: two departments
        describing the same manual workaround should look alike."""
        parts = [self.title]
        parts += [self.value(k) for k in config.core_field_keys()]
        parts += list(self.context.values())
        return "\n".join(p for p in parts if p)

    def as_prompt_block(self) -> str:
        """The record as the agents see it, states included.

        Stating `missing` explicitly matters: it is what stops a model quietly
        filling the gap with something plausible.
        """
        lines = [f"Idea {self.id}: {self.title}"]
        if self.department:
            lines.append(f"Submitted by: {self.department}")
        for key in config.core_field_keys():
            core = self.get(key)
            if core.is_usable:
                lines.append(f"- {key} [provided]: {core.value}")
            elif core.state == "unclear":
                lines.append(f"- {key} [UNCLEAR, too vague to evaluate]: {core.value}")
            elif core.state == "assumed":
                lines.append(f"- {key} [ASSUMED by agent, not evidence]: {core.value}")
            else:
                lines.append(f"- {key} [MISSING - not provided by the submitter]")
        for name, text in self.context.items():
            lines.append(f"- context/{name}: {text}")
        return "\n".join(lines)


def _state_for(text: str, key: str) -> FieldState:
    """Classify an answer without judging its content beyond usability."""
    stripped = text.strip()
    if not stripped:
        return "missing"
    lowered = stripped.lower()
    if any(marker in lowered for marker in UNKNOWN_MARKERS) and len(stripped) < 60:
        return "missing"

    spec = next((f for f in config.questionnaire()["core_fields"]
                 if f["key"] == key), None)
    minimum = (spec or {}).get("validation", {}).get("min_words", 0)
    if minimum and len(stripped.split()) < minimum:
        return "unclear"
    return "provided"


def parse_front_matter(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    meta: dict[str, str] = {}
    for line in parts[1].strip().splitlines():
        if ":" in line:
            name, _, raw = line.partition(":")
            meta[name.strip()] = raw.strip().strip('"')
    return meta, parts[2]


def parse_sections(body: str) -> tuple[str, dict[str, str]]:
    """Split `# Title` and `## Section` markdown into a title and sections."""
    title_match = re.search(r"^#\s+(.+)$", body, re.MULTILINE)
    title = title_match.group(1).strip() if title_match else ""

    sections: dict[str, str] = {}
    for match in re.finditer(r"^##\s+(.+?)\n(.*?)(?=^##\s|\Z)",
                             body, re.MULTILINE | re.DOTALL):
        sections[match.group(1).strip()] = match.group(2).strip()
    return title, sections


def from_raw_idea_file(path: Path) -> UseCaseRecord:
    """Build a record from an employee_interface submission."""
    text = Path(path).read_text(encoding="utf-8")
    meta, body = parse_front_matter(text)
    title, sections = parse_sections(body)

    record = UseCaseRecord(
        id=meta.get("id") or Path(path).stem,
        title=title or meta.get("title", "Untitled"),
        author_id=meta.get("author_id", ""),
        source="employee_interface",
        source_path=str(Path(path).relative_to(config.ROOT)),
        created_at=meta.get("created_at", ""),
        status="submitted",
    )

    for heading, key in SECTION_TO_CORE.items():
        value = sections.get(heading, "").strip()
        record.fields[key] = CoreField(
            key=key, value=value, state=_state_for(value, key),
            evidence=f"{record.source_path}#{heading}" if value else "",
        )

    for heading in CONTEXT_SECTIONS:
        if sections.get(heading):
            record.context[heading.lower().replace(" ", "_")] = sections[heading]

    # Deliberately left missing rather than inferred. See the module docstring.
    for key in NOT_COLLECTED_BY_EMPLOYEE_INTERFACE:
        record.fields[key] = CoreField(key=key, state="missing")

    return record


def from_seed(data: dict) -> UseCaseRecord:
    """Build a record from seed/data/use_cases.json (all eight fields)."""
    record = UseCaseRecord(
        id=data["id"],
        title=data["title"],
        author_id=data.get("author_id", ""),
        department=data.get("department", ""),
        source="seed",
        created_at=data.get("created_at", ""),
        status=data.get("status", "submitted"),
    )
    answers = data.get("fields", {})
    for key in config.core_field_keys():
        entry = answers.get(key)
        if entry is None:
            record.fields[key] = CoreField(key=key, state="missing")
            continue
        if isinstance(entry, str):
            entry = {"value": entry}
        value = entry.get("value", "")
        record.fields[key] = CoreField(
            key=key,
            value=value,
            state=entry.get("state") or _state_for(value, key),
            evidence=entry.get("evidence", "submitted answer"),
        )
    record.context = data.get("context", {})
    record.derived = data.get("derived", {})
    return record


def load_raw_ideas(directory: Path | None = None) -> list[UseCaseRecord]:
    target = Path(directory or config.RAW_IDEAS_DIR)
    if not target.exists():
        return []
    return [from_raw_idea_file(p) for p in sorted(target.glob("RI-*.md"))]
