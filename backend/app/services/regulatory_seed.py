"""Load fetched BOE law text into the canonical store as Track 1 docs.

Replaces the prior placeholder seed (10 descriptive paragraphs about each
regulator) with actual Saudi law text fetched by
scripts/fetch_regulatory_corpus.py and committed under fixtures/regulatory/.

Idempotency: keyed by content_hash_sha256 of the raw law text. Re-seeding
across container restarts is a no-op once the corpus is loaded.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Document, DocumentChunk, DocumentStatus, SourceTrack
from app.services.text_processing import chunk_text, normalize_arabic


# fixtures/regulatory/ lives at repo root; backend runs in /app inside the
# container with the repo mounted via the build context — fixtures got
# copied in via `COPY . .` in the Dockerfile.
FIXTURES_DIR_CANDIDATES = [
    Path(__file__).resolve().parents[3] / "fixtures" / "regulatory",
    Path("/app/fixtures/regulatory"),
    Path("fixtures/regulatory"),
]


def _fixtures_dir() -> Path | None:
    for candidate in FIXTURES_DIR_CANDIDATES:
        if (candidate / "manifest.json").exists():
            return candidate
    return None


def _stable_doc_id(slug: str) -> uuid.UUID:
    """Derive a deterministic UUID from the slug so re-seeding is idempotent
    even if content_hash changes (e.g. BOE re-fetches with whitespace
    differences)."""
    return uuid.uuid5(uuid.NAMESPACE_URL, f"suhaiman-km://regulatory/{slug}")


def seed_regulatory_corpus(db: Session) -> None:
    fixtures_dir = _fixtures_dir()
    if fixtures_dir is None:
        return

    manifest = json.loads((fixtures_dir / "manifest.json").read_text(encoding="utf-8"))
    for item in manifest["items"]:
        slug = item["slug"]
        doc_id = _stable_doc_id(slug)
        text_path = fixtures_dir / item["filename"]
        if not text_path.exists():
            continue
        body = text_path.read_text(encoding="utf-8")
        content_hash = hashlib.sha256(body.encode("utf-8")).hexdigest()

        existing = db.scalar(select(Document).where(Document.doc_id == doc_id))
        if existing and existing.content_hash_sha256 == content_hash and existing.chunks:
            continue
        if existing:
            # Hash changed (corpus was re-fetched) — drop old chunks/doc and
            # rebuild so chunking changes propagate.
            db.delete(existing)
            db.flush()

        doc = Document(
            doc_id=doc_id,
            title_ar=item["title_ar"],
            doc_type=item["doc_type"],
            practice_area=item.get("practice_area", []),
            jurisdiction="KSA",
            source_track=SourceTrack.track1_external,
            visibility="firm_wide",
            status=DocumentStatus.published,
            content_hash_sha256=content_hash,
            storage_key=f"seed/{slug}",
            original_filename=item["filename"],
            mime_type="text/plain",
            processing_stage="done",
            status_detail_ar="مصدر تنظيمي رسمي من هيئة الخبراء، مفهرس للبحث",
            extracted_text=body,
            source_url=item.get("source_url"),
            source_connector_id="boe_laws_v1",
        )
        db.add(doc)

        for index, chunk in enumerate(chunk_text(body), start=1):
            db.add(
                DocumentChunk(
                    doc_id=doc.doc_id,
                    chunk_index=index,
                    text_ar=chunk,
                    text_normalized=normalize_arabic(chunk),
                    paragraph_no=index,
                )
            )

    db.commit()
