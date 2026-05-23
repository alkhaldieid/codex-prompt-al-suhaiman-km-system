from sqlalchemy.orm import Session

from app.models import Document, DocumentChunk, DocumentStatus
from app.services.text_extraction import extract_text_from_upload
from app.services.text_processing import clean_extracted_text, chunk_text, normalize_arabic


def process_uploaded_document_inline(db: Session, *, doc: Document, content: bytes) -> None:
    doc.status = DocumentStatus.processing
    doc.processing_stage = "ocr"
    doc.status_detail_ar = "جاري استخراج النص من المستند"
    db.flush()

    extracted_text = extract_text_from_upload(filename=doc.original_filename, content=content)
    if not extracted_text.strip():
        doc.status = DocumentStatus.pending_review
        doc.processing_stage = "metadata"
        doc.status_detail_ar = (
            "تم حفظ الملف. لم يتم استخراج نص قابل للقراءة بعد؛ سيحتاج إلى OCR عبر GPT-5 vision في خطوة العامل القادمة."
        )
        doc.extracted_text = ""
        db.commit()
        return

    clean_text = clean_extracted_text(extracted_text)
    doc.extracted_text = clean_text
    doc.processing_stage = "indexing"
    doc.status_detail_ar = "تم استخراج النص وتجزئته مبدئياً"
    for index, chunk in enumerate(chunk_text(clean_text), start=1):
        db.add(
            DocumentChunk(
                doc_id=doc.doc_id,
                chunk_index=index,
                text_ar=chunk,
                text_normalized=normalize_arabic(chunk),
                page_no=None,
                paragraph_no=index,
                char_start=None,
                char_end=None,
            )
        )

    doc.status = DocumentStatus.pending_review
    doc.processing_stage = "done"
    doc.status_detail_ar = "تم استخراج النص وإنشاء المقاطع. التضمينات والفهرسة الدلالية هي الخطوة التالية."
    db.commit()
