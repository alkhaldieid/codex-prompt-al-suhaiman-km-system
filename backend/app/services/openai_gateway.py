"""Single egress point for OpenAI calls.

Every embedding, OCR, autotag, summarization, and Q&A call goes through
this module. The §10.7 contract requires that each external call:
  1. Pass can_send_to_openai() preflight on the document policy subject.
  2. Be audited via record_external_openai_call() with token + latency
     details. The audit row is the receipts trail under the residency
     exception.

Block decisions raise OpenAIBlockedError so callers can surface a clean
Arabic message instead of silently dropping the request.
"""

from __future__ import annotations

import base64
import time
from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from openai import OpenAI
from prometheus_client import Counter
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.llm.policy import OpenAIDocumentPolicySubject, can_send_to_openai
from app.models.audit import OpenAIPurpose
from app.services.openai_audit import record_external_openai_call


PREFLIGHT_BLOCKED = Counter(
    "llm_preflight_blocked_total",
    "Times can_send_to_openai() refused to forward a document",
    ["reason", "purpose"],
)


class OpenAIBlockedError(RuntimeError):
    """Raised when the §10.7 preflight refuses the call."""

    def __init__(self, reason: str, purpose: str) -> None:
        super().__init__(f"OpenAI call blocked: reason={reason} purpose={purpose}")
        self.reason = reason
        self.purpose = purpose


@dataclass
class ChatResult:
    text: str
    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: int


# Lazy module-level client. Synchronous because FastAPI handlers can call
# sync functions cleanly from the worker threadpool, but cannot nest
# asyncio.run() inside an already-running loop. Each call is one HTTP
# request — the simpler sync API costs us nothing here.
_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        settings = get_settings()
        if not settings.openai_api_key:
            raise RuntimeError(
                "OPENAI_API_KEY not set; cannot reach OpenAI. "
                "Set in .env or LLM_REQUIRED=false to skip external calls."
            )
        _client = OpenAI(
            api_key=settings.openai_api_key,
            timeout=settings.llm_timeout_ms / 1000,
        )
    return _client


def _preflight(
    subject: OpenAIDocumentPolicySubject | None,
    purpose: str,
) -> None:
    """Run the §10.7 policy check. Public/no-subject calls (e.g. a generic
    user query that isn't tied to a particular doc) skip the check; callers
    that have a doc MUST pass it."""
    if subject is None:
        return
    ok, reason = can_send_to_openai(subject)
    if not ok:
        PREFLIGHT_BLOCKED.labels(reason=reason or "unknown", purpose=purpose).inc()
        raise OpenAIBlockedError(reason or "unknown", purpose)


def embed_texts(
    db: Session,
    texts: list[str],
    *,
    subject: OpenAIDocumentPolicySubject | None = None,
    doc_id: UUID | None = None,
    request_id: str | None = None,
) -> list[list[float]]:
    """Embed a batch of texts. Caller is expected to batch ≤32 per call."""
    if not texts:
        return []
    _preflight(subject, OpenAIPurpose.embeddings.value)

    settings = get_settings()
    client = _get_client()
    started = time.perf_counter()
    response = client.embeddings.create(
        model=settings.embeddings_model,
        input=texts,
        dimensions=settings.embeddings_dimensions,
        extra_headers={"OpenAI-Beta": "no-training", "X-Request-ID": request_id or ""},
    )
    latency_ms = int((time.perf_counter() - started) * 1000)
    usage = response.usage

    record_external_openai_call(
        db,
        model=response.model,
        purpose=OpenAIPurpose.embeddings,
        doc_id=doc_id,
        doc_source_track=subject.source_track if subject else None,
        input_tokens=usage.prompt_tokens if usage else 0,
        output_tokens=0,
        vector_count=len(response.data),
        latency_ms=latency_ms,
    )
    return [item.embedding for item in response.data]


def chat_complete(
    db: Session,
    messages: list[dict],
    *,
    purpose: OpenAIPurpose,
    subject: OpenAIDocumentPolicySubject | None = None,
    doc_id: UUID | None = None,
    model: str | None = None,
    temperature: float | None = None,
    max_output_tokens: int = 1200,
    response_format: Literal["text", "json_object"] = "text",
    timeout_s: int = 25,
    reasoning_effort: str | None = "minimal",
    request_id: str | None = None,
) -> ChatResult:
    """Chat completion. Model defaults to settings.llm_model (gpt-5).

    For gpt-5 we use max_completion_tokens (not max_tokens), do not pass
    temperature (only default is supported), and default reasoning_effort
    to "minimal" so output isn't starved by invisible reasoning tokens.
    Bump the budget for gpt-5 since it counts reasoning + visible output
    against the same cap.
    """
    _preflight(subject, purpose.value)

    settings = get_settings()
    client = _get_client()
    chosen_model = model or settings.llm_model

    request_args: dict = {
        "model": chosen_model,
        "messages": messages,
        "timeout": timeout_s,
        "extra_headers": {"OpenAI-Beta": "no-training", "X-Request-ID": request_id or ""},
    }
    if chosen_model.startswith("gpt-5"):
        # Reserve headroom even with minimal reasoning.
        request_args["max_completion_tokens"] = max(max_output_tokens * 3, 3000)
        if reasoning_effort:
            request_args["reasoning_effort"] = reasoning_effort
    else:
        request_args["max_tokens"] = max_output_tokens
        if temperature is not None:
            request_args["temperature"] = temperature
    if response_format == "json_object":
        request_args["response_format"] = {"type": "json_object"}

    started = time.perf_counter()
    response = client.chat.completions.create(**request_args)
    latency_ms = int((time.perf_counter() - started) * 1000)
    choice = response.choices[0]
    usage = response.usage

    record_external_openai_call(
        db,
        model=response.model,
        purpose=purpose,
        doc_id=doc_id,
        doc_source_track=subject.source_track if subject else None,
        input_tokens=usage.prompt_tokens if usage else 0,
        output_tokens=usage.completion_tokens if usage else 0,
        latency_ms=latency_ms,
    )

    return ChatResult(
        text=choice.message.content or "",
        model=response.model,
        input_tokens=usage.prompt_tokens if usage else 0,
        output_tokens=usage.completion_tokens if usage else 0,
        latency_ms=latency_ms,
    )


def ocr_page_image(
    db: Session,
    *,
    image_bytes: bytes,
    mime_type: str,
    page_no: int,
    subject: OpenAIDocumentPolicySubject | None = None,
    doc_id: UUID | None = None,
    request_id: str | None = None,
) -> str:
    """Run vision-OCR on one rasterized page image. Returns extracted text."""
    _preflight(subject, OpenAIPurpose.ocr.value)

    settings = get_settings()
    client = _get_client()
    encoded = base64.b64encode(image_bytes).decode("ascii")
    data_url = f"data:{mime_type};base64,{encoded}"

    messages = [
        {
            "role": "system",
            "content": (
                "استخرج النص العربي من الصفحة المرفقة بدقة. "
                "أعد النص فقط، محافظاً على ترتيب الفقرات والأرقام قدر الإمكان. "
                "إن كانت الصفحة فارغة أو غير مقروءة، أعد سطراً واحداً: (صفحة فارغة)"
            ),
        },
        {
            "role": "user",
            "content": [
                {"type": "text", "text": f"رقم الصفحة: {page_no}"},
                {"type": "image_url", "image_url": {"url": data_url}},
            ],
        },
    ]

    request_args: dict = {
        "model": settings.ocr_model,
        "messages": messages,
        "timeout": 60,
        "extra_headers": {"OpenAI-Beta": "no-training", "X-Request-ID": request_id or ""},
    }
    if settings.ocr_model.startswith("gpt-5"):
        request_args["max_completion_tokens"] = 3000
    else:
        request_args["max_tokens"] = 3000
        request_args["temperature"] = 0

    started = time.perf_counter()
    response = client.chat.completions.create(**request_args)
    latency_ms = int((time.perf_counter() - started) * 1000)
    usage = response.usage
    text = response.choices[0].message.content or ""

    record_external_openai_call(
        db,
        model=response.model,
        purpose=OpenAIPurpose.ocr,
        doc_id=doc_id,
        doc_source_track=subject.source_track if subject else None,
        input_tokens=usage.prompt_tokens if usage else 0,
        output_tokens=usage.completion_tokens if usage else 0,
        page_count=1,
        latency_ms=latency_ms,
    )
    return text


# Backwards-compatible aliases so callers that imported the *_sync names
# don't break. Internally they're just the sync functions above.
embed_texts_sync = embed_texts
chat_complete_sync = chat_complete
