"""PDF OCR fallback for pages with no extractable text (spec §5.1).

Per-page strategy: walk every page, OCR only pages whose pdfplumber
text is empty or whitespace-only, then concatenate. This is the
specification's intended behaviour and correctly handles mixed
documents where most pages have a text layer but a few are scanned
images (court ruling exhibits, hand-stamped seals, signature pages).

The previous implementation bailed the moment any text was extracted —
that missed every page beyond the first text-bearing one in a mixed
PDF.
"""

from __future__ import annotations

import io
import logging
from uuid import UUID

import pypdfium2 as pdfium
from sqlalchemy.orm import Session

from app.llm.policy import OpenAIDocumentPolicySubject
from app.services.openai_gateway import OpenAIBlockedError, ocr_page_image

logger = logging.getLogger(__name__)

DPI = 200
EMPTY_OCR_MARKER = "(صفحة فارغة)"


def _extract_text_per_page(pdf_bytes: bytes) -> list[str]:
    """Per-page pdfplumber text. Returns one string per page (possibly empty).

    Defers the pdfplumber import so test environments that don't have
    it set up don't crash importing this module.
    """
    import pdfplumber  # local import

    pages_text: list[str] = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            try:
                text = page.extract_text() or ""
            except Exception as exc:  # noqa: BLE001
                logger.warning("pdfplumber page extract failed: %s", exc)
                text = ""
            pages_text.append(text.strip())
    return pages_text


def ocr_pdf_if_needed(
    db: Session,
    *,
    pdf_bytes: bytes,
    extracted_text: str,
    subject: OpenAIDocumentPolicySubject,
    doc_id: UUID,
) -> tuple[str, int]:
    """Return (final_text, ocr_page_count).

    extracted_text is what the caller already pulled with pdfplumber's
    full-doc API (used as a cheap "has any text" signal). We then go
    per-page and OCR only the empty pages.

    For non-PDFs or if pdfium can't open the bytes, returns
    (extracted_text, 0) unchanged.
    """
    try:
        pdf = pdfium.PdfDocument(io.BytesIO(pdf_bytes))
    except Exception as exc:  # noqa: BLE001
        logger.warning("pdfium open failed: %s", exc)
        return extracted_text, 0

    try:
        per_page = _extract_text_per_page(pdf_bytes)
    except Exception as exc:  # noqa: BLE001
        logger.warning("pdfplumber per-page failed: %s; falling back to full-page OCR", exc)
        per_page = ["" for _ in range(len(pdf))]

    # Normalise: a page is "needs OCR" if it has no non-whitespace text.
    needs_ocr_idx = [i for i, t in enumerate(per_page) if not t.strip()]

    # If every page already had text, skip the OCR pass entirely.
    if not needs_ocr_idx:
        return "\n\n".join(t for t in per_page if t.strip()), 0

    scale = DPI / 72  # 72 DPI is PDF's base
    ocr_pages = 0
    for page_idx in needs_ocr_idx:
        try:
            bitmap = pdf[page_idx].render(scale=scale)
            pil_image = bitmap.to_pil()
            buf = io.BytesIO()
            pil_image.save(buf, format="PNG", optimize=True)
            png_bytes = buf.getvalue()
        except Exception as exc:  # noqa: BLE001
            logger.warning("page %d render failed: %s", page_idx + 1, exc)
            continue
        try:
            text = ocr_page_image(
                db,
                image_bytes=png_bytes,
                mime_type="image/png",
                page_no=page_idx + 1,
                subject=subject,
                doc_id=doc_id,
            )
        except OpenAIBlockedError as exc:
            logger.info("OCR blocked by policy: %s", exc.reason)
            return _concat(per_page), ocr_pages
        ocr_pages += 1
        if text.strip() and text.strip() != EMPTY_OCR_MARKER:
            per_page[page_idx] = text.strip()

    return _concat(per_page), ocr_pages


def _concat(pages: list[str]) -> str:
    return "\n\n".join(t.strip() for t in pages if t.strip())
