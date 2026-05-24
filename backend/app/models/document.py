import enum
import uuid
from datetime import datetime, timezone

from pgvector.sqlalchemy import Vector
from sqlalchemy import ARRAY, Boolean, DateTime, Enum, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

EMBEDDING_DIM = 1536


class DocumentStatus(str, enum.Enum):
    uploaded = "uploaded"
    processing = "processing"
    pending_review = "pending_review"
    published = "published"
    archived = "archived"
    rejected = "rejected"
    duplicate_of = "duplicate_of"
    processing_failed = "processing_failed"


class SourceTrack(str, enum.Enum):
    track1_external = "track1_external"
    track2_legacy = "track2_legacy"
    track3_capture = "track3_capture"
    synthetic = "synthetic"


class Document(Base):
    __tablename__ = "documents"

    doc_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    title_ar: Mapped[str] = mapped_column(Text)
    title_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    doc_type: Mapped[str] = mapped_column(String(64), default="other")
    jurisdiction: Mapped[str] = mapped_column(String(32), default="KSA")
    source_track: Mapped[SourceTrack] = mapped_column(Enum(SourceTrack), default=SourceTrack.track3_capture)
    visibility: Mapped[str] = mapped_column(String(64), default="firm_wide")
    privilege_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    pii_flags: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[DocumentStatus] = mapped_column(Enum(DocumentStatus), default=DocumentStatus.uploaded)
    duplicate_of_doc_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    content_hash_sha256: Mapped[str] = mapped_column(String(64), index=True)
    storage_key: Mapped[str] = mapped_column(Text)
    original_filename: Mapped[str] = mapped_column(Text)
    mime_type: Mapped[str] = mapped_column(String(255))
    processing_stage: Mapped[str] = mapped_column(String(64), default="uploading")
    status_detail_ar: Mapped[str] = mapped_column(Text, default="تم استلام المستند")
    extracted_text: Mapped[str] = mapped_column(Text, default="")
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_connector_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    practice_area: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    auto_tag_confidence: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    ocr_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    summary_ar: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    chunks: Mapped[list["DocumentChunk"]] = relationship(back_populates="document")


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    chunk_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    doc_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.doc_id", ondelete="CASCADE"))
    chunk_index: Mapped[int] = mapped_column(Integer)
    text_ar: Mapped[str] = mapped_column(Text)
    text_normalized: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM), nullable=True)
    page_no: Mapped[int | None] = mapped_column(Integer, nullable=True)
    paragraph_no: Mapped[int | None] = mapped_column(Integer, nullable=True)
    char_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    char_end: Mapped[int | None] = mapped_column(Integer, nullable=True)

    document: Mapped[Document] = relationship(back_populates="chunks")
