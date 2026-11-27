"""Scores, stored as app-generated data.

A score belongs to one version of an idea and one version of the metric. Only
scores of the current metric and idea version are ranked; the rest are pending.
"""

from psycopg.rows import class_row
from psycopg.types.json import Jsonb
from pydantic import BaseModel

from db import connect


class Score(BaseModel):
    idea_id: str
    idea_version: int
    metric_name: str
    metric_version: int
    # Fingerprint of the metric and checks files that produced the score.
    metric_sha: str
    # None while the metric lacks a required input.
    value: int | None
    rationale: str
    # Status, inputs with their evidence, open questions and check results.
    details: dict


def save_score(score: Score) -> None:
    """Store a score, replacing an earlier one of the same idea and metric version."""
    row = score.model_dump() | {"details": Jsonb(score.details)}
    with connect() as connection:
        connection.execute(
            "INSERT INTO app_generated.score (idea_id, idea_version, metric_name, "
            "metric_version, metric_sha, value, rationale, details) "
            "VALUES (%(idea_id)s, %(idea_version)s, %(metric_name)s, "
            "%(metric_version)s, %(metric_sha)s, %(value)s, %(rationale)s, %(details)s) "
            "ON CONFLICT (idea_id, idea_version, metric_name, metric_version) "
            "DO UPDATE SET metric_sha = EXCLUDED.metric_sha, value = EXCLUDED.value, "
            "rationale = EXCLUDED.rationale, details = EXCLUDED.details, "
            "scored_at = now()",
            row,
        )


def current_scores(name: str, version: int, sha: str) -> dict[str, Score]:
    """By idea ID, the scores of this metric that match the idea's current version."""
    with connect() as connection:
        rows = (
            connection.cursor(row_factory=class_row(Score))
            .execute(
                "SELECT score.idea_id, score.idea_version, score.metric_name, "
                "score.metric_version, score.metric_sha, score.value, "
                "score.rationale, score.details "
                "FROM app_generated.score AS score "
                "JOIN app_generated.raw_idea AS idea "
                "ON idea.id = score.idea_id AND idea.version = score.idea_version "
                "WHERE score.metric_name = %s AND score.metric_version = %s "
                "AND score.metric_sha = %s",
                (name, version, sha),
            )
            .fetchall()
        )
    return {score.idea_id: score for score in rows}
