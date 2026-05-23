import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class OpenAIPurpose(str, enum.Enum):
    qa = "qa"
    autotag = "autotag"
    summarize = "summarize"
    embeddings = "embeddings"
    ocr = "ocr"


class ExternalOpenAICall(Base):
    __tablename__ = "external_openai_calls"

    event_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    action: Mapped[str] = mapped_column(String(64), default="external_openai_call")
    model: Mapped[str] = mapped_column(String(128))
    purpose: Mapped[OpenAIPurpose] = mapped_column(Enum(OpenAIPurpose))
    doc_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    doc_source_track: Mapped[str | None] = mapped_column(String(64), nullable=True)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    vector_count: Mapped[int] = mapped_column(Integer, default=0)
    page_count: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
