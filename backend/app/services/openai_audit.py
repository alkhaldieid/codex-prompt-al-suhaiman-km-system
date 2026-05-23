from uuid import UUID

from sqlalchemy.orm import Session

from app.models.audit import ExternalOpenAICall, OpenAIPurpose


def record_external_openai_call(
    db: Session,
    *,
    model: str,
    purpose: OpenAIPurpose,
    doc_id: UUID | None = None,
    doc_source_track: str | None = None,
    input_tokens: int = 0,
    output_tokens: int = 0,
    vector_count: int = 0,
    page_count: int = 0,
    latency_ms: int = 0,
) -> ExternalOpenAICall:
    event = ExternalOpenAICall(
        model=model,
        purpose=purpose,
        doc_id=doc_id,
        doc_source_track=doc_source_track,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        vector_count=vector_count,
        page_count=page_count,
        latency_ms=latency_ms,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event
