"""Score ideas with the active metric.

    .venv/bin/python portal/score_ideas.py             # every pending idea
    .venv/bin/python portal/score_ideas.py RI-0001     # one idea, even if scored
    .venv/bin/python portal/score_ideas.py --all       # every idea again

The portal also calls this after an idea is submitted or updated.
"""

import argparse
import asyncio
import hashlib
import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

import yaml

from checks import load_checks, screen
from db import connect, create_tables
from idea_store import RawIdea, list_raw_ideas
from knowledge import load_knowledge, remove_names
from score_agent import ScoreContext, ScoreInputs, fill_inputs
from score_store import Score, current_scores, save_score
from scoring import Metric, load_metric, score

PORTAL_DIR = Path(__file__).resolve().parent
METRICS_DIR = PORTAL_DIR.parent / "metrics"
CHECKS_FILE = METRICS_DIR / "checks.md"
MAX_IDEA_CHARS = 20_000


@dataclass(frozen=True)
class Setup:
    """The active metric and checks. Read from the files each time they are needed."""

    metric: Metric
    checks: dict
    checks_text: str
    model: str

    @property
    def sha(self) -> str:
        text = self.metric.text + self.checks_text
        return hashlib.sha256(text.encode()).hexdigest()[:12]


def load_setup() -> Setup:
    config = yaml.safe_load((PORTAL_DIR / "config.yaml").read_text(encoding="utf-8"))
    checks, checks_text = load_checks(CHECKS_FILE)
    return Setup(
        load_metric(METRICS_DIR / config["metric"]),
        checks,
        checks_text,
        config["models"]["score_agent"],
    )


def assess(
    idea: RawIdea,
    text: str,
    filled: ScoreInputs,
    documents: dict[str, str],
    setup: Setup,
) -> Score:
    """Turn what the agent filled in into a score and flags. No model involved.

    Args:
        text: The idea text the agent read.
    """
    result = score(
        setup.metric,
        [field.model_dump() for field in filled.inputs],
        text,
        documents,
        filled.open_questions,
    )
    checks = screen(
        filled.fit_answers.model_dump(), filled.act_answers.model_dump(), text, setup.checks
    )
    value, rationale = result.pop("value"), result.pop("rationale")
    return Score(
        idea_id=idea.id,
        idea_version=idea.version,
        metric_name=setup.metric.name,
        metric_version=setup.metric.version,
        metric_sha=setup.sha,
        value=value,
        rationale=rationale,
        details=result | checks,
    )


def score_idea(idea: RawIdea, setup: Setup) -> Score:
    """Score one idea and store the result."""
    with connect() as connection:
        documents, employees = load_knowledge(connection)
    # The agent judges the idea without knowing who anyone is.
    text = remove_names(idea.text, employees)[:MAX_IDEA_CHARS]
    context = ScoreContext(documents, setup.metric.text, setup.checks_text)
    filled = asyncio.run(fill_inputs(text, context, setup.model))
    result = assess(idea, text, filled, documents, setup)
    save_score(result)
    return result


def score_ideas(idea_ids: list[str] | None = None, rescore: bool = False) -> tuple[int, int]:
    """Score ideas that have no current score. How many succeeded and failed.

    Args:
        idea_ids: Only these ideas. All ideas if None.
        rescore: Also score ideas that already have a current score.
    """
    setup = load_setup()
    done = set()
    if not rescore:
        done = set(current_scores(setup.metric.name, setup.metric.version, setup.sha))
    succeeded = failed = 0
    for idea in list_raw_ideas():
        if idea.id in done or (idea_ids is not None and idea.id not in idea_ids):
            continue
        try:
            score_idea(idea, setup)
            succeeded += 1
        except Exception:
            # One idea that cannot be scored must not stop the others.
            logging.exception("Could not score %s", idea.id)
            failed += 1
    return succeeded, failed


# One at a time, so a burst of submissions does not flood the API.
_background = ThreadPoolExecutor(max_workers=1, thread_name_prefix="score")


def _score_quietly(idea_id: str) -> None:
    try:
        score_ideas([idea_id])
    except Exception:
        logging.exception("Could not score %s", idea_id)


def score_in_background(idea_id: str) -> None:
    """Score a new or changed idea without making anyone wait.

    If it fails, the idea stays pending and can be scored from the dashboard.
    """
    _background.submit(_score_quietly, idea_id)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("ids", nargs="*", help="score these ideas, even if already scored")
    parser.add_argument("--all", action="store_true", help="score every idea again")
    arguments = parser.parse_args()
    logging.basicConfig(level=logging.WARNING)
    with connect() as connection:
        create_tables(connection)
    ids = [idea_id.upper() for idea_id in arguments.ids] or None
    succeeded, failed = score_ideas(ids, rescore=arguments.all or ids is not None)
    print(f"Scored {succeeded}, failed {failed}.")
    if failed or (ids and succeeded < len(set(ids))):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
