import time
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Document, DocumentChunk, DocumentStatus
from app.services.text_processing import normalize_arabic


@dataclass
class RetrievedChunk:
    doc: Document
    chunk: DocumentChunk
    score: int
    snippet: str


def tokenize_query(query: str) -> list[str]:
    normalized = normalize_arabic(query)
    return [token for token in normalized.split() if len(token) >= 3]


def retrieve_chunks(db: Session, query: str, *, limit: int = 10) -> tuple[list[RetrievedChunk], int]:
    started = time.perf_counter()
    tokens = tokenize_query(query)
    docs = db.scalars(
        select(Document)
        .options(selectinload(Document.chunks))
        .where(Document.status.in_([DocumentStatus.published, DocumentStatus.pending_review]))
    ).all()
    results: list[RetrievedChunk] = []
    for doc in docs:
        title_norm = normalize_arabic(doc.title_ar)
        for chunk in doc.chunks:
            haystack = f"{title_norm} {chunk.text_normalized}"
            score = sum(haystack.count(token) for token in tokens)
            if not tokens and query.strip():
                score = 1 if normalize_arabic(query) in haystack else 0
            if score <= 0:
                continue
            snippet = make_snippet(chunk.text_ar, tokens)
            results.append(RetrievedChunk(doc=doc, chunk=chunk, score=score, snippet=snippet))
    results.sort(key=lambda item: item.score, reverse=True)
    took_ms = int((time.perf_counter() - started) * 1000)
    return results[:limit], took_ms


def make_snippet(text: str, tokens: list[str], *, max_chars: int = 320) -> str:
    if not text:
        return ""
    normalized = normalize_arabic(text)
    start = 0
    for token in tokens:
        index = normalized.find(token)
        if index >= 0:
            start = max(0, index - 80)
            break
    snippet = text[start : start + max_chars].strip()
    return snippet + ("…" if len(text) > start + max_chars else "")
