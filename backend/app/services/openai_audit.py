"""Audit-log every external OpenAI call per spec §10.7.

Uses a raw INSERT with explicit ::source_track cast because the column
is a Postgres enum and SQLAlchemy's psycopg path won't auto-cast a
Python string to it. Keeping this as raw SQL is fine — the audit log is
write-only and we never read it back through the ORM.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.audit import OpenAIPurpose


def record_external_openai_call(
    db: Session,
    *,
    model: str,
    purpose: OpenAIPurpose,
    doc_id: UUID | None = None,
    doc_source_track: str | None = None,
    input_tokens: int = 0,
    output_tokens: int = 0,
    vector_count: int = 0,
    page_count: int = 0,
    latency_ms: int = 0,
) -> None:
    db.execute(
        text(
            """
            INSERT INTO external_openai_calls (
              model, purpose, doc_id, doc_source_track,
              input_tokens, output_tokens, vector_count,
              page_count, latency_ms
            ) VALUES (
              :model, :purpose, :doc_id,
              CAST(:src_track AS source_track),
              :in_tok, :out_tok, :vec_n, :pg_n, :lat_ms
            )
            """
        ),
        {
            "model": model,
            "purpose": purpose.value if hasattr(purpose, "value") else str(purpose),
            "doc_id": doc_id,
            "src_track": doc_source_track,
            "in_tok": input_tokens,
            "out_tok": output_tokens,
            "vec_n": vector_count,
            "pg_n": page_count,
            "lat_ms": latency_ms,
        },
    )
    db.commit()
