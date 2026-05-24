from pydantic import BaseModel
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.services.rag import ask as rag_ask
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
                "chunk_id": str(item.chunk.chunk_id),
                "title_ar": item.doc.title_ar,
                "snippet_ar": item.snippet,
                "doc_type": item.doc.doc_type,
                "doc_type_ar": item.doc.doc_type,
                "practice_area": item.doc.practice_area,
                "paragraph_no": item.chunk.paragraph_no,
                "date_gregorian": None,
                "score": round(item.score, 6),
                "bm25_score": round(item.bm25_score, 4),
                "vector_score": round(item.vector_score, 4),
                "source_track": item.doc.source_track.value,
                "source_url": item.doc.source_url,
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
    """RAG Q&A across the entire regulatory + uploaded corpus."""
    result = rag_ask(db, payload.question)
    return {
        "answer_ar": result.answer_ar,
        "citations": result.citations,
        "model": result.model,
        "took_ms": result.took_ms,
        "retrieved_chunks": result.retrieved_chunks,
        "refused": result.refused,
        "refusal_reason": result.refusal_reason,
    }
