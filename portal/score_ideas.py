"""Score raw and refined ideas with the active metrics.

    .venv/bin/python portal/score_ideas.py             # every missing score
    .venv/bin/python portal/score_ideas.py RI-0001     # one idea, even if scored
    .venv/bin/python portal/score_ideas.py --all       # every idea again

The portal also calls this after an idea is submitted, updated or merged.
"""

import argparse
import asyncio
import hashlib
import logging
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

import yaml

from checks import load_checks, screen
from db import connect, create_tables
from idea_store import RawIdea, list_raw_ideas, raw_idea_texts
from knowledge import load_knowledge, remove_names
from refined_store import RefinedIdea, list_refined_ideas
from score_agent import ScoreContext, ScoreInputs, fill_inputs
from score_store import Score, current_scores, save_score
from scoring import Metric, load_metric, score

PORTAL_DIR = Path(__file__).resolve().parent
METRICS_DIR = PORTAL_DIR.parent / "metrics"
CHECKS_FILE = METRICS_DIR / "checks.md"
MAX_IDEA_CHARS = 20_000


@dataclass(frozen=True)
class Setup:
    """One active metric and the checks. Read from the files each time they are needed."""

    metric: Metric
    checks: dict
    checks_text: str
    model: str

    @property
    def sha(self) -> str:
        text = self.metric.text + self.checks_text
        return hashlib.sha256(text.encode()).hexdigest()[:12]


def load_setups() -> list[Setup]:
    """One setup for each active metric, in the order of the config file."""
    config = yaml.safe_load((PORTAL_DIR / "config.yaml").read_text(encoding="utf-8"))
    checks, checks_text = load_checks(CHECKS_FILE)
    setups = [
        Setup(
            load_metric(METRICS_DIR / file),
            checks,
            checks_text,
            config["models"]["score_agent"],
        )
        for file in config["metrics"]
    ]
    # Scores are stored by metric name, so two files must not share one.
    if not setups or len({setup.metric.name for setup in setups}) != len(setups):
        raise ValueError("config.yaml: list at least one metric, each with its own name")
    return setups


def idea_texts(
    text: str, sources: dict[str, str], employees: dict[str, str]
) -> tuple[str, str]:
    """What the agent reads, and the employees' own words that quotes must match.

    Args:
        sources: By ID, the ideas a refined idea was merged from. Empty for a raw
            idea, whose text is already the employee's own.
    """

    def clean(value: str) -> str:
        # The agent judges the idea without knowing who anyone is.
        return remove_names(value, employees)[:MAX_IDEA_CHARS]

    if not sources:
        return clean(text), clean(text)
    originals = {idea_id: clean(source) for idea_id, source in sorted(sources.items())}
    read = "\n\n".join(
        [clean(text)]
        + [f"--- Source idea {idea_id} ---\n{source}" for idea_id, source in originals.items()]
    )
    # The refined text was written by a model, so it proves nothing.
    return read, "\n\n".join(originals.values())


def assess(
    idea: RawIdea | RefinedIdea,
    text: str,
    filled: ScoreInputs,
    documents: dict[str, str],
    setup: Setup,
) -> Score:
    """Turn what the agent filled in into a score and flags. No model involved.

    Args:
        text: The employees' own words, which quotes are checked against.
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


def score_idea(idea: RawIdea | RefinedIdea, setups: list[Setup]) -> None:
    """Score one idea with each of these metrics and store the results.

    The metrics run side by side. If some fail, the others are still stored, and
    the first failure is raised.
    """
    with connect() as connection:
        documents, employees = load_knowledge(connection)
    sources = {}
    if isinstance(idea, RefinedIdea):
        # The versions it was written from, even if an author has edited since.
        sources = raw_idea_texts(idea.sources)
    read, own_words = idea_texts(idea.text, sources, employees)

    async def fill() -> list[ScoreInputs | BaseException]:
        runs = [
            fill_inputs(
                read,
                ScoreContext(documents, setup.metric.text, setup.checks_text),
                setup.model,
            )
            for setup in setups
        ]
        return await asyncio.gather(*runs, return_exceptions=True)

    errors = []
    for setup, filled in zip(setups, asyncio.run(fill())):
        try:
            if isinstance(filled, BaseException):
                raise filled
            save_score(assess(idea, own_words, filled, documents, setup))
        except Exception as error:
            errors.append(error)
    if errors:
        raise errors[0]


def score_progress(
    idea_ids: list[str] | None = None, rescore: bool = False
) -> Iterator[tuple[int, int, int]]:
    """Give ideas the scores they lack, one idea per step.

    Yields how many ideas succeeded, failed and are to be scored in all: once
    before the first idea, then after each one.

    Args:
        idea_ids: Only these ideas. All ideas if None.
        rescore: Also replace current scores.
    """
    setups = load_setups()
    done: dict[str, set[str]] = {}
    if not rescore:
        for setup in setups:
            metric = setup.metric
            done[metric.name] = set(current_scores(metric.name, metric.version, setup.sha))
    queue = []
    for idea in [*list_raw_ideas(), *list_refined_ideas()]:
        if idea_ids is not None and idea.id not in idea_ids:
            continue
        if pending := [s for s in setups if idea.id not in done.get(s.metric.name, ())]:
            queue.append((idea, pending))
    succeeded = failed = 0
    yield succeeded, failed, len(queue)
    for idea, pending in queue:
        try:
            score_idea(idea, pending)
            succeeded += 1
        except Exception:
            # One idea that cannot be scored must not stop the others.
            logging.exception("Could not score %s", idea.id)
            failed += 1
        yield succeeded, failed, len(queue)


def score_ideas(idea_ids: list[str] | None = None, rescore: bool = False) -> tuple[int, int]:
    """Run score_progress to the end. How many ideas succeeded and failed."""
    *_, (succeeded, failed, _) = score_progress(idea_ids, rescore)
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
