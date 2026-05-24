"""Auto-tagging via GPT-5 (spec §7.2).

JSON-mode classification over the first two chunks of a document.
Returns the parsed JSON or a sentinel that leaves doc fields blank.
"""

from __future__ import annotations

import json
import logging
from uuid import UUID

from sqlalchemy.orm import Session

from app.llm.policy import OpenAIDocumentPolicySubject
from app.models.audit import OpenAIPurpose
from app.services.openai_gateway import OpenAIBlockedError, chat_complete

logger = logging.getLogger(__name__)


VALID_DOC_TYPES = {
    "judicial_ruling", "legal_opinion", "memo", "pleading", "contract",
    "engagement_letter", "regulation", "royal_decree", "council_resolution",
    "circular", "template", "precedent_note", "other",
}
VALID_PRACTICE_AREAS = {
    "corporate_commercial", "litigation_dispute", "banking_finance",
    "real_estate", "labor_employment", "regulatory_compliance", "ip",
    "tax_zakat", "construction", "family_inheritance", "criminal",
    "administrative",
}


SYSTEM_AR = (
    "أنت مصنّف قانوني آلي. مهمتك تحديد نوع المستند ومجال الممارسة بناءً على "
    "النص المقدم. الإجابة يجب أن تكون JSON صالحاً فقط، دون أي شرح إضافي."
)


def _user_prompt(title: str, first_chunks_text: str) -> str:
    return f"""المقتطف:
{first_chunks_text[:3500]}

العنوان المقترح: {title}

أجب بـ JSON بالشكل التالي:
{{
  "doc_type": "<one of: judicial_ruling, legal_opinion, memo, pleading, contract, engagement_letter, regulation, royal_decree, council_resolution, circular, template, precedent_note, other>",
  "doc_type_confidence": <0.0-1.0>,
  "practice_area": ["<one or more of: corporate_commercial, litigation_dispute, banking_finance, real_estate, labor_employment, regulatory_compliance, ip, tax_zakat, construction, family_inheritance, criminal, administrative>"],
  "practice_area_confidence": <0.0-1.0>,
  "rationale_ar": "<short Arabic justification>"
}}"""


def autotag(
    db: Session,
    *,
    title: str,
    first_chunks_text: str,
    subject: OpenAIDocumentPolicySubject,
    doc_id: UUID,
) -> dict | None:
    """Run §7.2 autotagging. Returns dict with normalized fields, or None."""
    if not first_chunks_text.strip():
        return None
    messages = [
        {"role": "system", "content": SYSTEM_AR},
        {"role": "user", "content": _user_prompt(title, first_chunks_text)},
    ]
    try:
        result = chat_complete(
            db,
            messages,
            purpose=OpenAIPurpose.autotag,
            subject=subject,
            doc_id=doc_id,
            max_output_tokens=400,
            response_format="json_object",
            timeout_s=15,
        )
    except OpenAIBlockedError:
        logger.info("autotag blocked by policy")
        return None
    except Exception as exc:  # noqa: BLE001
        logger.warning("autotag call failed: %s", exc)
        return None

    try:
        parsed = json.loads(result.text)
    except json.JSONDecodeError:
        logger.warning("autotag JSON parse failed; raw=%r", result.text[:200])
        return None

    doc_type = parsed.get("doc_type") if parsed.get("doc_type") in VALID_DOC_TYPES else None
    practice = parsed.get("practice_area") or []
    if not isinstance(practice, list):
        practice = [practice]
    practice = [p for p in practice if p in VALID_PRACTICE_AREAS]
    return {
        "doc_type": doc_type,
        "doc_type_confidence": float(parsed.get("doc_type_confidence", 0) or 0),
        "practice_area": practice,
        "practice_area_confidence": float(parsed.get("practice_area_confidence", 0) or 0),
        "rationale_ar": (parsed.get("rationale_ar") or "")[:500],
    }
