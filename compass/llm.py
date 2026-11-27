"""One model interface, three backends, and a fallback that cannot fail.

    generate_json(system, user, offline=...)  -> (payload, model_used)
    generate_text(system, user, offline=...)  -> (text, model_used)

Backends are chosen by LLM_PROVIDER, or inferred from whichever API key is
present (see config.provider).

The `offline` callable is not an afterthought. It is a deterministic rule engine
supplied by each agent, and it runs in three situations:

  1. no API key is configured
  2. the provider errors or rate-limits
  3. the model returns something that is not valid JSON

So a missing key or a bad night on the API degrades the quality of the output
instead of breaking the pipeline. Every result records which backend produced
it, and the dashboard shows that, because a rule-based verdict and a model
verdict should not look identical to a decision maker.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Callable

from . import config

OFFLINE_MODEL = "offline-rules-v1"

# Set when a provider call fails, so the UI can say why it degraded.
last_degradation: str | None = None


def _strip_json(text: str) -> str:
    """Pull a JSON object out of a reply that may be fenced or prefixed."""
    fenced = re.search(r"```(?:json)?\s*(.+?)```", text, re.DOTALL)
    if fenced:
        return fenced.group(1).strip()
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        return text[start : end + 1]
    return text.strip()


# --------------------------------------------------------------------------- #
# providers
# --------------------------------------------------------------------------- #
def _openai_chat(system: str, user: str, as_json: bool) -> str:
    from openai import OpenAI

    client = OpenAI()
    kwargs: dict[str, Any] = {
        "model": config.model_name(),
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
        "temperature": 0,
    }
    if as_json:
        kwargs["response_format"] = {"type": "json_object"}
    response = client.chat.completions.create(**kwargs)
    return response.choices[0].message.content or ""


def _anthropic_chat(system: str, user: str, as_json: bool) -> str:
    import anthropic

    client = anthropic.Anthropic()
    model = config.model_name()
    if as_json:
        user = f"{user}\n\nReply with a single JSON object and nothing else."

    request: dict[str, Any] = {
        "model": model,
        # Thinking is adaptive by default on current models and consumes
        # tokens, so leave room. Non-streaming, so kept under the HTTP timeout.
        "max_tokens": 16000,
        "system": system,
        "messages": [{"role": "user", "content": user}],
    }
    # No temperature: sampling parameters are removed on Opus 5, Sonnet 5 and
    # the 4.7+ family and return a 400. Determinism comes from the prompts and
    # from effort, not from temperature.
    if _supports_effort(model):
        # These calls are structured extraction and classification, not
        # open-ended reasoning, so the cheapest useful depth is right. Override
        # with COMPASS_EFFORT if a verdict looks shallow.
        request["output_config"] = {
            "effort": os.environ.get("COMPASS_EFFORT", "low")}

    response = client.messages.create(**request)
    if getattr(response, "stop_reason", None) == "refusal":
        details = getattr(response, "stop_details", None)
        raise ValueError(
            f"model declined: {getattr(details, 'category', 'unknown')}")
    return "".join(block.text for block in response.content
                   if getattr(block, "type", "") == "text")


def _supports_effort(model: str) -> bool:
    """`output_config.effort` is rejected by Haiku 4.5 and older models."""
    return not any(tag in model for tag in ("haiku", "sonnet-4-5", "-3-"))


PROVIDERS: dict[str, Callable[[str, str, bool], str]] = {
    "openai": _openai_chat,
    "anthropic": _anthropic_chat,
}


# --------------------------------------------------------------------------- #
# public interface
# --------------------------------------------------------------------------- #
def generate_json(system: str, user: str,
                  offline: Callable[[], dict[str, Any]],
                  required_keys: tuple[str, ...] = ()) -> tuple[dict, str]:
    """Structured output, with the offline rules as the safety net."""
    global last_degradation
    name = config.provider()

    if name == "offline" or name not in PROVIDERS:
        return offline(), OFFLINE_MODEL

    try:
        raw = PROVIDERS[name](system, user, True)
        payload = json.loads(_strip_json(raw))
        if not isinstance(payload, dict):
            raise ValueError("model returned a non-object")
        missing = [k for k in required_keys if k not in payload]
        if missing:
            raise ValueError(f"missing keys in model output: {missing}")
        last_degradation = None
        return payload, config.model_name()
    except Exception as error:  # provider, network, or malformed output
        last_degradation = f"{name}: {type(error).__name__}: {error}"
        fallback = offline()
        fallback.setdefault("_degraded", last_degradation)
        return fallback, f"{OFFLINE_MODEL} (fallback from {name})"


def generate_text(system: str, user: str,
                  offline: Callable[[], str]) -> tuple[str, str]:
    """Free-text output, same fallback contract."""
    global last_degradation
    name = config.provider()

    if name == "offline" or name not in PROVIDERS:
        return offline(), OFFLINE_MODEL

    try:
        text = PROVIDERS[name](system, user, False).strip()
        if not text:
            raise ValueError("empty reply")
        last_degradation = None
        return text, config.model_name()
    except Exception as error:
        last_degradation = f"{name}: {type(error).__name__}: {error}"
        return offline(), f"{OFFLINE_MODEL} (fallback from {name})"


def status() -> dict[str, Any]:
    """What the dashboard shows about how assessments were produced."""
    name = config.provider()
    return {
        "provider": name,
        "model": config.model_name() if name != "offline" else OFFLINE_MODEL,
        "live_model": name in PROVIDERS,
        "openai_key_present": bool(os.environ.get("OPENAI_API_KEY")),
        "anthropic_key_present": bool(os.environ.get("ANTHROPIC_API_KEY")),
        "last_degradation": last_degradation,
    }


def banner() -> str:
    state = status()
    if state["live_model"]:
        return f"Model: {state['model']} via {state['provider']}"
    return ("Model: offline rule engine (no API key configured). Verdicts are "
            "deterministic and deliberately conservative.")


def smoke_test() -> int:
    """One real call, to check a key works before spending on 43 ideas.

    Run: python -m compass.llm
    """
    state = status()
    print("provider:        ", state["provider"])
    print("model:           ", state["model"])
    print("OPENAI_API_KEY:  ", "set" if state["openai_key_present"] else "not set")
    print("ANTHROPIC_API_KEY:",
          "set" if state["anthropic_key_present"] else "not set")
    if config.LOADED_FROM_ENV_FILE:
        print("loaded from .env:", ", ".join(config.LOADED_FROM_ENV_FILE))

    if not state["live_model"]:
        print("\nNo provider configured, so the pipeline would use the offline "
              "rule engine.\nTo use a model, put a key in .env (gitignored):")
        print('  LLM_PROVIDER=anthropic\n  ANTHROPIC_API_KEY=sk-ant-...')
        return 0

    print("\nMaking one real call (a few hundred tokens)...")
    payload, model = generate_json(
        "You extract structured data. Reply with JSON only.",
        'Return {"ok": true, "reach": <the number in this sentence>} for: '
        '"about 1,250 tickets arrive per month".',
        offline=lambda: {"ok": False, "reach": None, "_offline": True},
        required_keys=("ok",),
    )
    print("response:", payload)
    print("produced by:", model)

    if payload.get("_offline") or model.startswith(OFFLINE_MODEL):
        print(f"\nFAILED - fell back to the offline rules.\n"
              f"reason: {last_degradation}")
        return 1
    print("\nOK. The key works. Now re-assess the portfolio with:\n"
          "  python -m seed.load")
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(smoke_test())
