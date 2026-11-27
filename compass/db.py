"""SQLite storage for everything derived.

Raw ideas stay where employee_interface put them: markdown files under
knowledge-base/ideas/raw/. That is deliberate and matches ARCHITECTURE.md -
they are the submitter's own words and must stay auditable and greppable.

Everything in this database is derived and regenerable: parsed records,
assessments, overlap links, review items, decisions, rank snapshots and the
knowledge graph. Deleting compass.db loses no employee input.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS use_cases (
    id            TEXT PRIMARY KEY,
    title         TEXT NOT NULL,
    author_id     TEXT,
    department    TEXT,
    source        TEXT NOT NULL,          -- employee_interface | seed
    source_path   TEXT,
    status        TEXT NOT NULL,          -- draft|submitted|assessed|in_review|selected|parked|rejected
    version       INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS core_fields (
    use_case_id   TEXT NOT NULL,
    field_key     TEXT NOT NULL,
    value         TEXT,
    state         TEXT NOT NULL,          -- provided|unclear|missing|assumed
    evidence      TEXT,                   -- quoted from the submitter
    PRIMARY KEY (use_case_id, field_key),
    FOREIGN KEY (use_case_id) REFERENCES use_cases(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS derived_params (
    use_case_id   TEXT NOT NULL,
    key           TEXT NOT NULL,
    value         TEXT,
    origin        TEXT NOT NULL,          -- submitter|agent|config
    PRIMARY KEY (use_case_id, key),
    FOREIGN KEY (use_case_id) REFERENCES use_cases(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS assessments (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    use_case_id     TEXT NOT NULL,
    use_case_version INTEGER NOT NULL,
    kind            TEXT NOT NULL,        -- ai_fit|risk|feasibility|score
    payload         TEXT NOT NULL,        -- JSON
    model           TEXT NOT NULL,
    config_name     TEXT,
    config_version  TEXT,
    created_at      TEXT NOT NULL,
    FOREIGN KEY (use_case_id) REFERENCES use_cases(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_assessments_lookup
    ON assessments(use_case_id, kind, created_at DESC);

CREATE TABLE IF NOT EXISTS overlaps (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    a_id        TEXT NOT NULL,
    b_id        TEXT NOT NULL,
    similarity  REAL NOT NULL,
    verdict     TEXT NOT NULL,            -- duplicate|related|distinct
    rationale   TEXT,
    status      TEXT NOT NULL DEFAULT 'suggested',  -- suggested|confirmed|rejected
    created_at  TEXT NOT NULL,
    UNIQUE (a_id, b_id)
);

CREATE TABLE IF NOT EXISTS review_items (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    use_case_id TEXT NOT NULL,
    reason      TEXT NOT NULL,
    detail      TEXT,
    severity    TEXT NOT NULL,            -- high|medium|low
    field_key   TEXT,
    assignee_id TEXT,
    status      TEXT NOT NULL DEFAULT 'open',  -- open|resolved
    created_at  TEXT NOT NULL,
    resolved_at TEXT,
    FOREIGN KEY (use_case_id) REFERENCES use_cases(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS decisions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    use_case_id TEXT NOT NULL,
    decision    TEXT NOT NULL,            -- selected|parked|rejected
    actor_id    TEXT NOT NULL,
    note        TEXT,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS rank_snapshots (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    config_name     TEXT NOT NULL,
    config_version  TEXT NOT NULL,
    payload         TEXT NOT NULL,        -- JSON: ordered [{use_case_id, score, factors}]
    created_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS active_config (
    key     TEXT PRIMARY KEY,
    value   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    actor       TEXT NOT NULL,
    action      TEXT NOT NULL,
    target      TEXT,
    detail      TEXT,
    created_at  TEXT NOT NULL
);

-- Knowledge graph, rebuilt from the knowledge base by compass.kg.ingest.
CREATE TABLE IF NOT EXISTS kg_node (
    id              TEXT PRIMARY KEY,
    type            TEXT NOT NULL,
    name            TEXT NOT NULL,
    attrs           TEXT NOT NULL DEFAULT '{}',
    classification  TEXT NOT NULL DEFAULT 'internal',
    source_path     TEXT
);
CREATE INDEX IF NOT EXISTS idx_kg_node_type ON kg_node(type);
CREATE INDEX IF NOT EXISTS idx_kg_node_name ON kg_node(name);

CREATE TABLE IF NOT EXISTS kg_edge (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    src     TEXT NOT NULL,
    rel     TEXT NOT NULL,
    dst     TEXT NOT NULL,
    attrs   TEXT NOT NULL DEFAULT '{}',
    UNIQUE (src, rel, dst)
);
CREATE INDEX IF NOT EXISTS idx_kg_edge_src ON kg_edge(src, rel);
CREATE INDEX IF NOT EXISTS idx_kg_edge_dst ON kg_edge(dst, rel);

CREATE TABLE IF NOT EXISTS kb_chunk (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    source_path     TEXT NOT NULL,
    heading         TEXT,
    text            TEXT NOT NULL,
    classification  TEXT NOT NULL DEFAULT 'internal'
);
CREATE INDEX IF NOT EXISTS idx_kb_chunk_path ON kb_chunk(source_path);
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect(path: Path | None = None) -> sqlite3.Connection:
    target = Path(path or config.DB_PATH)
    target.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(target)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def session(path: Path | None = None) -> Iterator[sqlite3.Connection]:
    conn = connect(path)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init(path: Path | None = None) -> None:
    with session(path) as conn:
        conn.executescript(SCHEMA)
        _init_fts(conn)


def _init_fts(conn: sqlite3.Connection) -> bool:
    """Full-text index over knowledge-base chunks.

    FTS5 is normally compiled into SQLite. If it is not, retrieval falls back
    to the TF-IDF scorer in compass.kg.retrieve, so this is an optimisation and
    not a requirement.
    """
    try:
        conn.executescript(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS kb_chunk_fts
                USING fts5(text, heading, source_path UNINDEXED,
                           content='kb_chunk', content_rowid='id');
            """
        )
        return True
    except sqlite3.OperationalError:
        return False


def has_fts(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE name = 'kb_chunk_fts'"
    ).fetchone()
    return row is not None


def reset(path: Path | None = None) -> None:
    """Drop everything derived and recreate. Raw idea files are untouched."""
    target = Path(path or config.DB_PATH)
    if target.exists():
        target.unlink()
    init(target)


def log(conn: sqlite3.Connection, actor: str, action: str,
        target: str | None = None, detail: Any = None) -> None:
    conn.execute(
        "INSERT INTO audit_log (actor, action, target, detail, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (actor, action, target,
         json.dumps(detail, ensure_ascii=False) if detail is not None else None,
         now()),
    )


def get_active_scoring(conn: sqlite3.Connection) -> str:
    row = conn.execute(
        "SELECT value FROM active_config WHERE key = 'scoring'"
    ).fetchone()
    return row["value"] if row else config.DEFAULT_SCORING


def set_active_scoring(conn: sqlite3.Connection, name: str) -> None:
    conn.execute(
        "INSERT INTO active_config (key, value) VALUES ('scoring', ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (name,),
    )


def latest_assessment(conn: sqlite3.Connection, use_case_id: str,
                      kind: str) -> dict | None:
    row = conn.execute(
        "SELECT * FROM assessments WHERE use_case_id = ? AND kind = ? "
        "ORDER BY created_at DESC, id DESC LIMIT 1",
        (use_case_id, kind),
    ).fetchone()
    if row is None:
        return None
    record = dict(row)
    record["payload"] = json.loads(record["payload"])
    return record


def save_assessment(conn: sqlite3.Connection, use_case_id: str, version: int,
                    kind: str, payload: dict, model: str,
                    config_name: str | None = None,
                    config_version: str | None = None) -> None:
    conn.execute(
        "INSERT INTO assessments (use_case_id, use_case_version, kind, payload, "
        "model, config_name, config_version, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (use_case_id, version, kind,
         json.dumps(payload, ensure_ascii=False), model,
         config_name, config_version, now()),
    )


def add_review_item(conn: sqlite3.Connection, use_case_id: str, reason: str,
                    severity: str, detail: str | None = None,
                    field_key: str | None = None,
                    assignee_id: str | None = None) -> None:
    """Record a gap or uncertainty for a human to resolve.

    Idempotent per (use case, reason, field): re-running the pipeline must not
    pile up duplicate review items.
    """
    existing = conn.execute(
        "SELECT id FROM review_items WHERE use_case_id = ? AND reason = ? "
        "AND IFNULL(field_key,'') = IFNULL(?,'') AND status = 'open'",
        (use_case_id, reason, field_key),
    ).fetchone()
    if existing:
        return
    conn.execute(
        "INSERT INTO review_items (use_case_id, reason, detail, severity, "
        "field_key, assignee_id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (use_case_id, reason, detail, severity, field_key, assignee_id, now()),
    )
