from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Header, Response, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.core.config import get_settings
from app.core.errors import AppProblem
from app.db.session import get_db
from app.models import Document, DocumentStatus, SourceTrack, User
from app.schemas.documents import DocumentDetailResponse, DocumentStatusResponse, DocumentUploadResponse
from app.services.ingestion_progress import INGESTION_STAGES, INGESTION_TARGET_SECONDS
from app.services.storage import LocalObjectStorage, get_storage
from app.services.upload_validation import is_allowed_upload_filename

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("/recent")
def recent_documents(_: User = Depends(get_current_user)) -> dict:
    return {
        "items": [],
        "message": "لا توجد مستندات حديثة بعد",
    }


@router.post("", response_model=DocumentUploadResponse, status_code=202)
async def upload_document(
    response: Response,
    file: UploadFile = File(...),
    confirm_no_real_client_data: bool = Form(False),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    storage: LocalObjectStorage = Depends(get_storage),
) -> DocumentUploadResponse:
    settings = get_settings()
    if settings.env == "demo" and not confirm_no_real_client_data:
        raise AppProblem(
            status=400,
            title="يلزم تأكيد بيئة العرض",
            detail="يجب تأكيد أن المستند لا يحتوي على بيانات عميل حقيقية قبل الرفع",
            type_="https://ethka.dev/errors/demo-upload-confirmation-required",
        )

    if not file.filename or not is_allowed_upload_filename(file.filename):
        raise AppProblem(
            status=415,
            title="صيغة الملف غير مدعومة",
            detail="الصيغ المدعومة هي PDF و DOCX و JPG و PNG و TIFF حتى 100 ميجابايت",
            type_="https://ethka.dev/errors/unsupported-upload-type",
        )

    content = await file.read()
    if len(content) > settings.max_upload_bytes:
        raise AppProblem(
            status=413,
            title="حجم الملف كبير",
            detail="الحد الأقصى لحجم الملف هو 100 ميجابايت",
            type_="https://ethka.dev/errors/upload-too-large",
        )

    import hashlib

    content_hash = hashlib.sha256(content).hexdigest()
    existing = db.scalar(select(Document).where(Document.content_hash_sha256 == content_hash))
    if existing:
        response.status_code = 201
        response.headers["X-Idempotent-Replay"] = "true"
        return DocumentUploadResponse(
            doc_id=str(existing.doc_id),
            status=existing.status.value,
            status_url=f"/api/v1/documents/{existing.doc_id}/status",
            estimated_ready_seconds=INGESTION_TARGET_SECONDS,
            message_ar="تم العثور على مستند مطابق محفوظ مسبقاً",
        )

    title = Path(file.filename).stem.replace("_", " ").strip() or file.filename
    doc = Document(
        title_ar=title,
        doc_type="other",
        jurisdiction="KSA",
        source_track=SourceTrack.track3_capture,
        visibility="firm_wide",
        status=DocumentStatus.uploaded,
        content_hash_sha256=content_hash,
        storage_key="pending",
        original_filename=file.filename,
        mime_type=file.content_type or "application/octet-stream",
        processing_stage="uploading",
        status_detail_ar="تم استلام المستند وسيبدأ الاستخلاص والفهرسة",
        created_by=user.user_id,
    )
    db.add(doc)
    db.flush()
    doc.storage_key = storage.put_raw(doc_id=doc.doc_id, filename=file.filename, content=content)
    db.commit()

    if idempotency_key:
        response.headers["Idempotency-Key"] = idempotency_key

    return DocumentUploadResponse(
        doc_id=str(doc.doc_id),
        status=doc.status.value,
        status_url=f"/api/v1/documents/{doc.doc_id}/status",
        estimated_ready_seconds=INGESTION_TARGET_SECONDS,
        message_ar="تم الرفع — ستظهر مراحل المعالجة باللغة العربية",
    )


@router.get("/{doc_id}/status", response_model=DocumentStatusResponse)
def document_status(
    doc_id: UUID,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DocumentStatusResponse:
    doc = db.get(Document, doc_id)
    if doc is None:
        raise AppProblem(
            status=404,
            title="المستند غير موجود",
            detail="لا يوجد مستند بالمعرف المُقدَّم",
            type_="https://ethka.dev/errors/document-not-found",
        )

    stage = next((item for item in INGESTION_STAGES if item.key == doc.processing_stage), INGESTION_STAGES[0])
    return DocumentStatusResponse(
        doc_id=str(doc.doc_id),
        status=doc.status.value,
        stage=stage.key,
        stage_label_ar=stage.label_ar,
        detail_ar=doc.status_detail_ar,
        estimated_ready_seconds=INGESTION_TARGET_SECONDS,
    )


@router.get("/{doc_id}", response_model=DocumentDetailResponse)
def get_document(
    doc_id: UUID,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DocumentDetailResponse:
    doc = db.get(Document, doc_id)
    if doc is None:
        raise AppProblem(
            status=404,
            title="المستند غير موجود",
            detail="لا يوجد مستند بالمعرف المُقدَّم",
            type_="https://ethka.dev/errors/document-not-found",
        )
    return DocumentDetailResponse(
        doc_id=str(doc.doc_id),
        title_ar=doc.title_ar,
        status=doc.status.value,
        source_track=doc.source_track.value,
        original_filename=doc.original_filename,
        mime_type=doc.mime_type,
    )
