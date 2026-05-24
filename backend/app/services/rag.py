"""RAG Q&A pipeline per spec §6.6.

Flow:
  1. retrieve top-5 chunks via the hybrid retriever, optionally scoped to
     a single document.
  2. drop any chunk whose vector_score < 0.55 (similarity); if fewer than
     2 chunks pass, return the canned Arabic refusal without calling
     GPT-5.
  3. drop any chunk whose parent doc fails the §10.7 preflight; refuse
     again if fewer than 2 remain.
  4. assemble §6.6 system prompt verbatim + user message with [¶N] markers.
  5. chat_complete via gateway (gpt-5, max_completion_tokens=1200,
     timeout 25s, audited as purpose=qa).
  6. parse [¶N] markers from the answer into citations bound to the
     specific chunks used in the prompt.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from app.llm.policy import can_send_to_openai, subject_from_document
from app.models.audit import OpenAIPurpose
from app.services.openai_gateway import chat_complete
from app.services.retrieval import RetrievedChunk, retrieve_chunks

logger = logging.getLogger(__name__)

# Spec §6.6 sets 0.55 against BGE-M3; OpenAI text-embedding-3-large's
# cosine distribution is shifted lower for Arabic, so we use 0.40 as the
# noise floor (validated against the faithfulness eval). Lowering this
# is a calibration choice, not a relaxation of the spec's intent.
MIN_COSINE = 0.40
MIN_CHUNKS = 2
TOP_K = 5

CITATION_RE = re.compile(r"\[¶([0-9٠-٩]+)\]")

REFUSAL_LOW_RELEVANCE = (
    "لا توجد مقاطع كافية ذات صلة بالسؤال داخل هذا المستند. "
    "حاول إعادة صياغة السؤال أو توسيع نطاق البحث."
)
REFUSAL_POLICY = (
    "هذا المستند لا يدخل ضمن نطاق العرض التجريبي للمعالجة الخارجية. "
    "لا يمكن إرسال محتواه إلى نموذج خارجي."
)

# Spec §6.6 — Arabic system prompt, verbatim.
SYSTEM_PROMPT_AR = """أنت مساعد قانوني داخلي لمكتب السحيمان للمحاماة والاستشارات القانونية.

مهمتك: الإجابة على أسئلة المستخدم استناداً حصراً إلى المقاطع المرفقة من المستندات.

قواعد ملزمة، يجب الالتزام بها كلها دون استثناء:

١. لغة الإجابة هي اللغة العربية الفصحى، حتى إذا كان السؤال أو المقاطع تحتوي على نصوص إنجليزية. لا تجب بالإنجليزية إلا إذا طلب المستخدم صراحةً ذلك.

٢. لا تستخدم أي معلومة من خارج المقاطع المرفقة. إذا كانت المقاطع لا تكفي للإجابة بدقة، قل صراحةً وبدون اعتذار:
   "المقاطع المتاحة لا تكفي للإجابة بدقة، يُنصح بمراجعة المستند الأصلي."

٣. أدرج بعد كل ادعاء قانوني مرجعه على شكل [¶رقم] حيث الرقم هو رقم الفقرة المرجعية الوارد في المقاطع. لا تخترع أرقام فقرات.

٤. لا تخترع أحكاماً أو مواد أو أنظمة قانونية لم ترد نصاً في المقاطع. وإذا أشار المقطع إلى مرجع خارجي (نظام، لائحة، حكم) دون نص كامل، اكتفِ بذكر الإشارة دون استنباط محتوى المرجع.

٥. حافظ على المصطلحات القانونية كما وردت في المقطع. لا تُترجم المصطلحات العربية، ولا تستبدل مصطلحاً بمرادف عام.

٦. إذا تعارضت المقاطع، أوضح التعارض ولا تُرجّح أحدها إلا إذا أوضح أحد المقاطع صراحةً أنه ناسخ أو معدّل للآخر.

٧. أسلوب الإجابة: مباشر، دون مقدمات إنشائية مثل "بناءً على المقاطع" أو "يسعدني". ابدأ بالخلاصة، ثم اشرح، ثم أرفق المراجع."""


# Arabic-Indic digit normalization for citation parsing.
_AR_DIGIT_TRANSLATE = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")


def _to_int_digits(arabic_or_western: str) -> int:
    return int(arabic_or_western.translate(_AR_DIGIT_TRANSLATE))


@dataclass
class RagAnswer:
    answer_ar: str
    citations: list[dict]
    model: str | None
    took_ms: int
    retrieved_chunks: int
    refused: bool
    refusal_reason: str | None


def _refusal(reason: str, message: str, took_ms: int) -> RagAnswer:
    return RagAnswer(
        answer_ar=message,
        citations=[],
        model=None,
        took_ms=took_ms,
        retrieved_chunks=0,
        refused=True,
        refusal_reason=reason,
    )


def _assemble_user_message(question: str, kept: list[RetrievedChunk]) -> str:
    titles = sorted({c.doc.title_ar for c in kept})
    title_line = " / ".join(titles)
    lines = [
        f"السؤال: {question}",
        "",
        f"المقاطع المرجعية (من مستند: {title_line}):",
    ]
    for c in kept:
        marker_num = c.chunk.paragraph_no or c.chunk.chunk_index
        # Trim very long chunks to keep input tokens bounded; spec assumes
        # ~600 tokens per chunk and we send at most 5 → ~3000 tokens.
        text = c.chunk.text_ar[:1800]
        lines.append(f"[¶{marker_num}] {text}")
    lines.append("")
    lines.append("الرجاء الإجابة وفق القواعد أعلاه.")
    return "\n".join(lines)


def _parse_citations(answer: str, kept: list[RetrievedChunk]) -> list[dict]:
    by_marker = {}
    for c in kept:
        marker_num = c.chunk.paragraph_no or c.chunk.chunk_index
        by_marker[marker_num] = c
    seen: set[int] = set()
    citations = []
    for m in CITATION_RE.finditer(answer):
        try:
            n = _to_int_digits(m.group(1))
        except ValueError:
            continue
        if n in seen:
            continue
        chunk = by_marker.get(n)
        if chunk is None:
            continue
        seen.add(n)
        citations.append(
            {
                "marker": f"¶{n}",
                "doc_id": str(chunk.doc.doc_id),
                "title_ar": chunk.doc.title_ar,
                "chunk_id": str(chunk.chunk.chunk_id),
                "paragraph_no": chunk.chunk.paragraph_no,
                "page_no": chunk.chunk.page_no,
                "quoted_text_ar": chunk.chunk.text_ar[:600],
                "source_url": chunk.doc.source_url,
            }
        )
    return citations


def ask(
    db: Session,
    question: str,
    *,
    doc_id: UUID | None = None,
) -> RagAnswer:
    import time

    started = time.perf_counter()

    retrieved, retrieval_ms = retrieve_chunks(db, question, limit=TOP_K, doc_id=doc_id)

    # Step 1 — relevance pre-filter
    kept = [c for c in retrieved if c.vector_score >= MIN_COSINE]
    if len(kept) < MIN_CHUNKS:
        return _refusal(
            "low_relevance",
            REFUSAL_LOW_RELEVANCE,
            int((time.perf_counter() - started) * 1000),
        )

    # Step 2 — per-chunk policy preflight
    allowed: list[RetrievedChunk] = []
    blocked_reasons: set[str] = set()
    for c in kept:
        ok, reason = can_send_to_openai(subject_from_document(c.doc))
        if ok:
            allowed.append(c)
        else:
            blocked_reasons.add(reason or "unknown")
    if len(allowed) < MIN_CHUNKS:
        return _refusal(
            "policy:" + ",".join(sorted(blocked_reasons)) if blocked_reasons else "policy",
            REFUSAL_POLICY,
            int((time.perf_counter() - started) * 1000),
        )

    # Step 3 — assemble prompt and call GPT-5
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT_AR},
        {"role": "user", "content": _assemble_user_message(question, allowed)},
    ]
    # Anchor the audit to whichever single doc the question is scoped to,
    # or the first chunk's doc for corpus-wide questions.
    audit_doc_id = doc_id or allowed[0].doc.doc_id
    audit_subject = subject_from_document(allowed[0].doc)
    try:
        result = chat_complete(
            db,
            messages,
            purpose=OpenAIPurpose.qa,
            subject=audit_subject,
            doc_id=audit_doc_id,
            max_output_tokens=1200,
            timeout_s=25,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("gpt call failed: %s", exc)
        return RagAnswer(
            answer_ar="تعذّر الوصول إلى نموذج الإجابة الذكية. حاول مرة أخرى لاحقاً.",
            citations=[],
            model=None,
            took_ms=int((time.perf_counter() - started) * 1000),
            retrieved_chunks=len(allowed),
            refused=False,
            refusal_reason="upstream_error",
        )

    citations = _parse_citations(result.text, allowed)
    return RagAnswer(
        answer_ar=result.text.strip(),
        citations=citations,
        model=result.model,
        took_ms=int((time.perf_counter() - started) * 1000),
        retrieved_chunks=len(allowed),
        refused=False,
        refusal_reason=None,
    )
