"""Backfill embeddings for any DocumentChunk where embedding IS NULL.

Idempotent: re-running it does nothing once every chunk has a vector. Used
after the regulatory corpus is seeded (chunks land synchronously but are
embedded on the same request path; if seeding ran with no key set, this
catches up afterward).

Honors the §10.7 preflight on each parent document. Track 2 / privileged /
PII / restricted-matter docs are skipped, their chunks left unembedded.

Run inside the backend container:
  docker compose exec backend python /app/scripts/embed_unembedded_chunks.py
"""

from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

# Inside the backend container the app package is at /app/app and is
# already on PYTHONPATH (Dockerfile WORKDIR /app + pip install .). Outside
# the container, the package lives under backend/. Try both.
for candidate in [Path("/app"), Path(__file__).resolve().parent.parent / "backend"]:
    if (candidate / "app").exists() and str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from sqlalchemy import select  # noqa: E402

from app.db.session import SessionLocal  # noqa: E402
from app.llm.policy import subject_from_document  # noqa: E402
from app.models import Document, DocumentChunk  # noqa: E402
from app.services.openai_gateway import (  # noqa: E402
    OpenAIBlockedError,
    embed_texts_sync,
)

BATCH = 32


def main() -> int:
    db = SessionLocal()
    try:
        rows = db.scalars(
            select(DocumentChunk).where(DocumentChunk.embedding.is_(None))
        ).all()
        if not rows:
            print("nothing to embed; all chunks have vectors.")
            return 0
        by_doc: dict = defaultdict(list)
        for chunk in rows:
            by_doc[chunk.doc_id].append(chunk)

        total_embedded = 0
        total_blocked = 0
        for doc_id, chunks in by_doc.items():
            doc = db.get(Document, doc_id)
            if doc is None:
                continue
            subject = subject_from_document(doc)
            try:
                for start in range(0, len(chunks), BATCH):
                    batch = chunks[start : start + BATCH]
                    vectors = embed_texts_sync(
                        db,
                        [c.text_ar for c in batch],
                        subject=subject,
                        doc_id=doc.doc_id,
                    )
                    for chunk, vector in zip(batch, vectors):
                        chunk.embedding = vector
                    db.commit()
                    total_embedded += len(batch)
                    print(f"  [{doc.title_ar[:60]}] +{len(batch)} (total {total_embedded})")
            except OpenAIBlockedError as exc:
                total_blocked += len(chunks)
                print(f"  [SKIP {doc.title_ar[:60]}] {exc.reason}")
        print(f"\nEmbedded {total_embedded} chunks. Blocked {total_blocked}.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
