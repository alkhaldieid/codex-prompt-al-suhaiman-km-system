"""In-request ingestion pipeline (PoC sync path; pilot moves to Celery).

Flow per spec §5.1:
  1. extract text (pdfplumber/python-docx for now; OCR fallback added Step 4)
  2. clean + paragraph-aware chunk per §6.1
  3. persist chunks
  4. embed in batches of 32 via the OpenAI gateway (preflight + audit)
  5. flip status to pending_review

If OPENAI_API_KEY is missing or LLM_REQUIRED=false, chunks are persisted
without embeddings — searchable via BM25 only until backfill runs.
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.llm.policy import subject_from_document
from app.models import Document, DocumentChunk, DocumentStatus
from app.services.openai_gateway import OpenAIBlockedError, embed_texts_sync
from app.services.text_extraction import extract_text_from_upload
from app.services.text_processing import chunk_text, clean_extracted_text, normalize_arabic

logger = logging.getLogger(__name__)

EMBED_BATCH_SIZE = 32


def _embed_chunks(db: Session, doc: Document, chunks: list[DocumentChunk]) -> int:
    """Embed any chunks that don't yet have a vector. Returns number embedded."""
    settings = get_settings()
    if not settings.openai_api_key:
        logger.info("skip embeddings, no OPENAI_API_KEY")
        return 0

    subject = subject_from_document(doc)
    todo = [c for c in chunks if c.embedding is None]
    embedded = 0
    for start in range(0, len(todo), EMBED_BATCH_SIZE):
        batch = todo[start : start + EMBED_BATCH_SIZE]
        texts = [c.text_ar for c in batch]
        try:
            vectors = embed_texts_sync(db, texts, subject=subject, doc_id=doc.doc_id)
        except OpenAIBlockedError as exc:
            doc.status_detail_ar = (
                "تم استخراج النص لكن سياسة العرض التجريبي منعت إرسال المقاطع إلى OpenAI "
                f"(السبب: {exc.reason}). المقاطع متاحة للبحث النصي فقط."
            )
            return embedded
        for chunk, vector in zip(batch, vectors):
            chunk.embedding = vector
            embedded += 1
        db.commit()
    return embedded


def process_uploaded_document_inline(db: Session, *, doc: Document, content: bytes) -> None:
    doc.status = DocumentStatus.processing
    doc.processing_stage = "ocr"
    doc.status_detail_ar = "جاري استخراج النص من المستند"
    db.flush()

    extracted_text = extract_text_from_upload(filename=doc.original_filename, content=content)
    if not extracted_text.strip():
        # OCR fallback wired in Step 4. For now, save the file and surface
        # status so the reviewer knows it needs OCR.
        doc.status = DocumentStatus.pending_review
        doc.processing_stage = "metadata"
        doc.status_detail_ar = (
            "تم حفظ الملف. لم يتم استخراج نص قابل للقراءة؛ يتطلب OCR."
        )
        doc.extracted_text = ""
        db.commit()
        return

    clean_text = clean_extracted_text(extracted_text)
    doc.extracted_text = clean_text
    doc.processing_stage = "indexing"
    doc.status_detail_ar = "تم استخراج النص؛ جاري التجزئة والفهرسة الدلالية"

    chunks: list[DocumentChunk] = []
    for index, piece in enumerate(chunk_text(clean_text), start=1):
        chunk = DocumentChunk(
            doc_id=doc.doc_id,
            chunk_index=index,
            text_ar=piece,
            text_normalized=normalize_arabic(piece),
            page_no=None,
            paragraph_no=index,
            char_start=None,
            char_end=None,
        )
        chunks.append(chunk)
        db.add(chunk)
    db.flush()

    embedded = _embed_chunks(db, doc, chunks)

    # Index into OpenSearch (Step 2). Defer import to keep this path
    # working even before the OS index exists.
    try:
        from app.services.search_index import index_chunks  # noqa: WPS433

        index_chunks(doc, chunks)
    except Exception as exc:  # noqa: BLE001
        logger.warning("opensearch index failed: %s", exc)

    doc.status = DocumentStatus.pending_review
    doc.processing_stage = "done"
    detail_parts = [f"تم استخراج {len(chunks)} مقطعاً"]
    if embedded:
        detail_parts.append(f"وإنشاء {embedded} تضمين دلالي")
    doc.status_detail_ar = "؛ ".join(detail_parts) + ". المستند جاهز للمراجعة."
    db.commit()
