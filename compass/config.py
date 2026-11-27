"""Paths, settings and config-file loading."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
KNOWLEDGE_BASE = ROOT / "knowledge-base"
RAW_IDEAS_DIR = KNOWLEDGE_BASE / "ideas" / "raw"
CONFIG_DIR = ROOT / "config"
SCORING_DIR = CONFIG_DIR / "scoring"
SEED_DIR = ROOT / "seed" / "data"
DB_PATH = Path(os.environ.get("COMPASS_DB", ROOT / "compass.db"))

ENV_FILE = ROOT / ".env"

QUESTIONNAIRE = CONFIG_DIR / "intake-questionnaire.yaml"
RISK_CONFIG = CONFIG_DIR / "risk" / "eu-ai-act.yaml"
DEFAULT_SCORING = "rice-v1"

# Classification levels, least to most restricted. An employee sees `internal`
# and below; only the decision board sees `confidential`.
CLASSIFICATION_ORDER = ["public", "internal", "confidential"]
ROLE_MAX_CLASSIFICATION = {
    "employee": "internal",
    "reviewer": "internal",
    "admin": "confidential",
}


def load_env_file(path: Path | None = None) -> list[str]:
    """Read KEY=value lines from .env into the environment.

    A deliberate 15 lines rather than a python-dotenv dependency. Existing
    environment variables win, so an explicit `export` still overrides the
    file. .env is gitignored: putting a key there keeps it out of git history
    and out of your shell history.
    """
    target = Path(path or ENV_FILE)
    if not target.exists():
        return []
    loaded = []
    for line in target.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value
            loaded.append(key)
    return loaded


# Loaded once at import, before anything reads os.environ for a provider.
LOADED_FROM_ENV_FILE = load_env_file()


def provider() -> str:
    """Which LLM backend to use.

    `offline` is a deterministic rule engine. It is the default precisely so
    that a missing key degrades the output quality instead of breaking the
    demo.
    """
    explicit = os.environ.get("LLM_PROVIDER", "").strip().lower()
    if explicit:
        return explicit
    if os.environ.get("OPENAI_API_KEY"):
        return "openai"
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic"
    return "offline"


def model_name() -> str:
    defaults = {
        "openai": "gpt-4.1-mini",
        "anthropic": "claude-opus-5",
        "offline": "offline-rules-v1",
    }
    return os.environ.get("COMPASS_MODEL") or defaults.get(provider(), "unknown")


@lru_cache(maxsize=None)
def load_yaml(path: Path) -> dict[str, Any]:
    with Path(path).open(encoding="utf-8") as file:
        return yaml.safe_load(file)


def questionnaire() -> dict[str, Any]:
    return load_yaml(QUESTIONNAIRE)


def risk_config() -> dict[str, Any]:
    return load_yaml(RISK_CONFIG)


def scoring_config(name: str = DEFAULT_SCORING) -> dict[str, Any]:
    """Load a scoring config, resolving `inherits` one level deep."""
    config = dict(load_yaml(SCORING_DIR / f"{name}.yaml"))
    parent_name = config.get("inherits")
    if parent_name:
        parent = dict(load_yaml(SCORING_DIR / f"{parent_name}.yaml"))
        parent.pop("inherits", None)
        merged = {**parent, **config}
        merged["inherits_resolved"] = parent_name
        return merged
    return config


def available_scoring_configs() -> list[str]:
    return sorted(p.stem for p in SCORING_DIR.glob("*.yaml"))


def core_field_keys() -> list[str]:
    fields = questionnaire()["core_fields"]
    return [f["key"] for f in sorted(fields, key=lambda f: f["order"])]


def required_field_keys() -> list[str]:
    return list(questionnaire()["submission_gate"]["require_all"])


def max_classification_for(role: str) -> str:
    return ROLE_MAX_CLASSIFICATION.get(role, "internal")


def may_see(role: str, classification: str) -> bool:
    limit = CLASSIFICATION_ORDER.index(max_classification_for(role))
    try:
        level = CLASSIFICATION_ORDER.index(classification)
    except ValueError:
        return False  # unknown level: refuse rather than leak
    return level <= limit
