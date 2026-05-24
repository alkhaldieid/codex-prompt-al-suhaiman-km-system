"""Apply *.sql migrations under backend/sql/ idempotently at startup.

Tracks applied filenames in schema_migrations. Each .sql file must be
written to be idempotent on its own (using IF NOT EXISTS guards) since
the table didn't exist before this commit.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from sqlalchemy import text

from app.db.session import engine

logger = logging.getLogger(__name__)

SQL_DIR_CANDIDATES = [
    Path("/app/sql"),
    Path(__file__).resolve().parents[2] / "sql",
]


def _sql_dir() -> Path | None:
    for d in SQL_DIR_CANDIDATES:
        if d.exists() and any(d.glob("*.sql")):
            return d
    return None


def apply_migrations() -> None:
    sql_dir = _sql_dir()
    if sql_dir is None:
        logger.info("no sql dir found; skipping migrations")
        return

    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
              filename TEXT PRIMARY KEY,
              applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
        """))
        applied = {row[0] for row in conn.execute(text("SELECT filename FROM schema_migrations"))}

        for sql_file in sorted(sql_dir.glob("*.sql")):
            # 001 is bootstrap — Postgres ran it via /docker-entrypoint-initdb.d
            # on first volume init. Skip to avoid re-creating types.
            if sql_file.name == "001_foundation.sql":
                continue
            if sql_file.name in applied:
                continue
            logger.info("applying migration %s", sql_file.name)
            stmt = sql_file.read_text(encoding="utf-8")
            # SQLAlchemy's engine.exec wants statements split for some
            # drivers; psycopg accepts multi-statement strings.
            conn.exec_driver_sql(stmt)
            conn.execute(
                text("INSERT INTO schema_migrations(filename) VALUES (:f)"),
                {"f": sql_file.name},
            )
