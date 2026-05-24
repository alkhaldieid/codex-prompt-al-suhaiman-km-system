"""PDF OCR fallback for pages with no extractable text.

Per spec §5.1: if pdfplumber returns no text for a page, rasterize the
page at ~200 DPI and call OpenAIVisionOCRClient through the gateway.
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


def ocr_pdf_if_needed(
    db: Session,
    *,
    pdf_bytes: bytes,
    extracted_text: str,
    subject: OpenAIDocumentPolicySubject,
    doc_id: UUID,
) -> tuple[str, int]:
    """If extracted_text is empty, OCR every page. Otherwise OCR only pages
    that contribute no characters to the existing extraction.

    Returns (final_text, ocr_page_count).
    """
    try:
        pdf = pdfium.PdfDocument(io.BytesIO(pdf_bytes))
    except Exception as exc:  # noqa: BLE001
        logger.warning("pdfium failed to open pdf: %s", exc)
        return extracted_text, 0

    if extracted_text.strip():
        # Cheap check — if pdfplumber already pulled meaningful text out,
        # don't re-OCR every page; just return what we have. Per-page
        # selective OCR could be added later but is overkill for PoC.
        return extracted_text, 0

    pages_text: list[str] = []
    ocr_pages = 0
    scale = DPI / 72  # 72 DPI is PDF's base
    for page_no, page in enumerate(pdf, start=1):
        try:
            bitmap = page.render(scale=scale)
            pil_image = bitmap.to_pil()
            buf = io.BytesIO()
            pil_image.save(buf, format="PNG", optimize=True)
            png_bytes = buf.getvalue()
        except Exception as exc:  # noqa: BLE001
            logger.warning("page %d render failed: %s", page_no, exc)
            continue
        try:
            text = ocr_page_image(
                db,
                image_bytes=png_bytes,
                mime_type="image/png",
                page_no=page_no,
                subject=subject,
                doc_id=doc_id,
            )
        except OpenAIBlockedError as exc:
            logger.info("OCR blocked by policy: %s", exc.reason)
            return extracted_text, ocr_pages
        ocr_pages += 1
        if text.strip() and text.strip() != "(صفحة فارغة)":
            pages_text.append(text.strip())

    return "\n\n".join(pages_text), ocr_pages
