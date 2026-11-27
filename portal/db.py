"""Postgres connection and tables, in two schemas:

- knowledge_base: company info, a copy of the files in knowledge-base/.
- app_generated: everything the app creates. It exists only in the database.
"""

import os
from pathlib import Path

import psycopg

ENV_FILE = Path(__file__).resolve().parent.parent / ".env"

TABLES = [
    "CREATE SCHEMA IF NOT EXISTS knowledge_base",
    "CREATE SCHEMA IF NOT EXISTS app_generated",
    """
    CREATE TABLE IF NOT EXISTS knowledge_base.documents (
        path       text PRIMARY KEY,
        content    text NOT NULL,
        updated_at timestamptz NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS knowledge_base.employees (
        id               text PRIMARY KEY,
        name             text NOT NULL,
        email            text NOT NULL,
        role             text NOT NULL,
        department       text NOT NULL,
        manager_id       text NOT NULL,
        work_mode        text NOT NULL,
        start_date       text NOT NULL,
        skills           text NOT NULL,
        responsibilities text NOT NULL,
        deputy_id        text NOT NULL
    )
    """,
    "CREATE SEQUENCE IF NOT EXISTS app_generated.raw_idea_number",
    """
    CREATE TABLE IF NOT EXISTS app_generated.raw_idea (
        id         text PRIMARY KEY,
        author_id  text NOT NULL,
        text       text NOT NULL,
        created_at timestamptz NOT NULL DEFAULT now()
    )
    """,
    # Added after the first release, so existing tables get them too.
    "ALTER TABLE app_generated.raw_idea "
    "ADD COLUMN IF NOT EXISTS version integer NOT NULL DEFAULT 1",
    "ALTER TABLE app_generated.raw_idea ADD COLUMN IF NOT EXISTS updated_at timestamptz",
    """
    CREATE TABLE IF NOT EXISTS app_generated.raw_idea_history (
        idea_id  text NOT NULL REFERENCES app_generated.raw_idea (id),
        version  integer NOT NULL,
        text     text NOT NULL,
        saved_at timestamptz NOT NULL,
        PRIMARY KEY (idea_id, version)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS app_generated.score (
        idea_id        text NOT NULL REFERENCES app_generated.raw_idea (id),
        idea_version   integer NOT NULL,
        metric_name    text NOT NULL,
        metric_version integer NOT NULL,
        metric_sha     text NOT NULL,
        value          integer,
        rationale      text NOT NULL,
        details        jsonb NOT NULL,
        scored_at      timestamptz NOT NULL DEFAULT now(),
        PRIMARY KEY (idea_id, idea_version, metric_name, metric_version)
    )
    """,
]


def database_url() -> str:
    """DATABASE_URL from the environment, otherwise from the .env file."""
    if url := os.environ.get("DATABASE_URL"):
        return url
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            name, _, value = line.partition("=")
            if name.strip() == "DATABASE_URL" and value.strip():
                return value.strip()
    raise RuntimeError("Set DATABASE_URL in the environment or in .env")


def connect() -> psycopg.Connection:
    """A new connection. Used as a context manager it commits, or rolls back."""
    return psycopg.connect(database_url(), connect_timeout=15)


def create_tables(connection: psycopg.Connection) -> None:
    for statement in TABLES:
        connection.execute(statement)
