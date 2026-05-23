from pydantic import BaseModel
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.services.retrieval import retrieve_chunks

router = APIRouter(prefix="/search", tags=["search"])


class AskRequest(BaseModel):
    question: str


@router.get("")
def search(
    q: str = Query(min_length=1),
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    retrieved, took_ms = retrieve_chunks(db, q, limit=10)
    return {
        "query": q,
        "total": len(retrieved),
        "took_ms": took_ms,
        "results": [
            {
                "doc_id": str(item.doc.doc_id),
                "title_ar": item.doc.title_ar,
                "snippet_ar": item.snippet,
                "doc_type": item.doc.doc_type,
                "doc_type_ar": item.doc.doc_type,
                "date_gregorian": None,
                "score": item.score,
                "source_track": item.doc.source_track.value,
            }
            for item in retrieved
        ],
    }


@router.post("/ask")
def ask_regulatory_corpus(
    payload: AskRequest,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    retrieved, took_ms = retrieve_chunks(db, payload.question, limit=5)
    if not retrieved:
        return {
            "answer_ar": "لم أجد في الفهرس التنظيمي الحالي مقاطع كافية للإجابة. جرّب صياغة أخرى أو حدد الجهة التنظيمية.",
            "citations": [],
            "took_ms": took_ms,
        }

    lines = ["أقرب ما وجدته في الفهرس التنظيمي الحالي:"]
    citations = []
    for index, item in enumerate(retrieved[:3], start=1):
        marker = f"¶{item.chunk.paragraph_no or item.chunk.chunk_index}"
        lines.append(f"{index}. {item.doc.title_ar}: {item.snippet} [{marker}]")
        citations.append(
            {
                "marker": marker,
                "doc_id": str(item.doc.doc_id),
                "title_ar": item.doc.title_ar,
                "chunk_id": str(item.chunk.chunk_id),
                "paragraph_no": item.chunk.paragraph_no,
                "quoted_text_ar": item.chunk.text_ar,
            }
        )

    lines.append("هذه إجابة استرجاعية من الفهرس الحالي وليست فتوى قانونية نهائية.")
    return {
        "answer_ar": "\n".join(lines),
        "citations": citations,
        "took_ms": took_ms,
    }
