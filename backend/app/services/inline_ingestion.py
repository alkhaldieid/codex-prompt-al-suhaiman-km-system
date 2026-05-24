"""In-request ingestion pipeline (PoC sync path; pilot moves to Celery).

Flow per spec §5.1 + §7.2:
  1. extract text (pdfplumber / python-docx)
  2. if PDF returned nothing → OCR fallback via GPT-5 vision
  3. clean + paragraph-aware chunk per §6.1
  4. persist chunks
  5. autotag (doc_type, practice_area, confidence) via GPT-5 json_object
  6. embed chunks in batches of 32 via the OpenAI gateway
  7. bulk-index into OpenSearch
  8. flip status to pending_review (or auto-publish if rules allow)

If OPENAI_API_KEY is missing or LLM_REQUIRED=false, the OpenAI-dependent
steps are skipped — text-only chunks are persisted and BM25-searchable.
"""

from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.llm.policy import subject_from_document
from app.models import Document, DocumentChunk, DocumentStatus
from app.services.autotag import autotag
from app.services.openai_gateway import OpenAIBlockedError, embed_texts
from app.services.pdf_ocr import ocr_pdf_if_needed
from app.services.text_extraction import extract_text_from_upload
from app.services.text_processing import chunk_text, clean_extracted_text, normalize_arabic

logger = logging.getLogger(__name__)

EMBED_BATCH_SIZE = 32


def _embed_chunks(db: Session, doc: Document, chunks: list[DocumentChunk]) -> int:
    settings = get_settings()
    if not settings.openai_api_key:
        return 0
    subject = subject_from_document(doc)
    todo = [c for c in chunks if c.embedding is None]
    embedded = 0
    for start in range(0, len(todo), EMBED_BATCH_SIZE):
        batch = todo[start : start + EMBED_BATCH_SIZE]
        texts = [c.text_ar for c in batch]
        try:
            vectors = embed_texts(db, texts, subject=subject, doc_id=doc.doc_id)
        except OpenAIBlockedError as exc:
            doc.status_detail_ar = (
                "تم استخراج النص لكن سياسة العرض التجريبي منعت التضمين الدلالي "
                f"(السبب: {exc.reason})."
            )
            return embedded
        for chunk, vector in zip(batch, vectors):
            chunk.embedding = vector
            embedded += 1
        db.commit()
    return embedded


def _maybe_autotag(db: Session, doc: Document, chunks: list[DocumentChunk]) -> None:
    settings = get_settings()
    if not settings.openai_api_key or not chunks:
        return
    first_two_text = "\n\n".join(c.text_ar for c in chunks[:2])
    tagging = autotag(
        db,
        title=doc.title_ar,
        first_chunks_text=first_two_text,
        subject=subject_from_document(doc),
        doc_id=doc.doc_id,
    )
    if not tagging:
        return
    if tagging.get("doc_type"):
        doc.doc_type = tagging["doc_type"]
    if tagging.get("practice_area"):
        doc.practice_area = tagging["practice_area"]
    doc.auto_tag_confidence = {
        "doc_type": tagging.get("doc_type_confidence", 0.0),
        "practice_area": tagging.get("practice_area_confidence", 0.0),
        "rationale_ar": tagging.get("rationale_ar", ""),
    }
    db.commit()


def process_uploaded_document_inline(db: Session, *, doc: Document, content: bytes) -> None:
    doc.status = DocumentStatus.processing
    doc.processing_stage = "ocr"
    doc.status_detail_ar = "جاري استخراج النص من المستند"
    db.flush()

    extracted_text = extract_text_from_upload(filename=doc.original_filename, content=content)

    # Step 4: OCR fallback for PDFs where pdfplumber returned nothing.
    if not extracted_text.strip() and Path(doc.original_filename).suffix.lower() == ".pdf":
        doc.status_detail_ar = "النص غير قابل للاستخراج مباشرة؛ جاري OCR عبر GPT-5 vision"
        db.flush()
        extracted_text, ocr_pages = ocr_pdf_if_needed(
            db,
            pdf_bytes=content,
            extracted_text=extracted_text,
            subject=subject_from_document(doc),
            doc_id=doc.doc_id,
        )
        if ocr_pages:
            doc.ocr_metadata = {"engine": "gpt-5-vision", "pages": ocr_pages}

    if not extracted_text.strip():
        doc.status = DocumentStatus.pending_review
        doc.processing_stage = "metadata"
        doc.status_detail_ar = "تم حفظ الملف. لم يتم استخراج نص قابل للقراءة."
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
            paragraph_no=index,
        )
        chunks.append(chunk)
        db.add(chunk)
    db.flush()

    # Autotag BEFORE embedding so the doc has its final practice_area/doc_type
    # baked into the OS index.
    _maybe_autotag(db, doc, chunks)

    embedded = _embed_chunks(db, doc, chunks)

    try:
        from app.services.search_index import index_chunks  # noqa: WPS433

        index_chunks(doc, chunks)
    except Exception as exc:  # noqa: BLE001
        logger.warning("opensearch index failed: %s", exc)

    doc.status = DocumentStatus.pending_review
    doc.processing_stage = "done"
    detail = [f"تم استخراج {len(chunks)} مقطعاً"]
    if embedded:
        detail.append(f"و{embedded} تضمين دلالي")
    if doc.auto_tag_confidence:
        detail.append("وتصنيف تلقائي")
    doc.status_detail_ar = "؛ ".join(detail) + ". جاهز للمراجعة والاعتماد."
    db.commit()
