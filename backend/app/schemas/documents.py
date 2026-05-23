from pydantic import BaseModel


class DocumentUploadResponse(BaseModel):
    doc_id: str
    status: str
    status_url: str
    document_url: str
    estimated_ready_seconds: int
    message_ar: str


class DocumentStatusResponse(BaseModel):
    doc_id: str
    status: str
    stage: str
    stage_label_ar: str
    detail_ar: str
    estimated_ready_seconds: int


class DocumentDetailResponse(BaseModel):
    doc_id: str
    title_ar: str
    status: str
    source_track: str
    original_filename: str
    mime_type: str
    status_detail_ar: str
    extracted_text_preview: str
    chunk_count: int
