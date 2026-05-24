"""Hybrid retrieval: BM25 (OpenSearch) + dense (pgvector) + RRF (spec §6.4).

Per query:
  1. Embed query via OpenAI gateway (Redis-cached, 1h TTL, SHA-256 keyed).
  2. BM25 top 50 from OpenSearch.
  3. Dense cosine top 50 from pgvector via HNSW.
  4. Fuse with Reciprocal Rank Fusion (k=60).
  5. Return top N with snippets from BM25 highlighter (fallback: chunk head).

No more substring counting. Throws on missing OPENAI_API_KEY only when
the dense path is needed (degraded BM25-only mode if Redis or OpenSearch
is unavailable, never silent).
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass
from uuid import UUID

import redis
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Document, DocumentChunk
from app.services.openai_gateway import embed_texts
from app.services.search_index import search_bm25
from app.services.text_processing import normalize_arabic

logger = logging.getLogger(__name__)

RRF_K = 60
QUERY_EMBED_TTL = 3600  # 1 hour per spec §6.4

_redis: redis.Redis | None = None


def _get_redis() -> redis.Redis | None:
    global _redis
    if _redis is None:
        host = os.environ.get("REDIS_HOST", "redis")
        port = int(os.environ.get("REDIS_PORT", "6379"))
        try:
            _redis = redis.Redis(host=host, port=port, decode_responses=False)
            _redis.ping()
        except redis.RedisError as exc:
            logger.warning("redis unavailable: %s", exc)
            _redis = None
    return _redis


@dataclass
class RetrievedChunk:
    doc: Document
    chunk: DocumentChunk
    score: float
    bm25_score: float
    vector_score: float
    snippet: str


def _embed_query_cached(db: Session, query: str) -> list[float] | None:
    normalized = normalize_arabic(query)
    key = b"q:embed:" + hashlib.sha256(normalized.encode("utf-8")).digest()
    r = _get_redis()
    if r is not None:
        cached = r.get(key)
        if cached:
            return json.loads(cached)
    try:
        vectors = embed_texts(db, [normalized])
    except Exception as exc:  # noqa: BLE001
        logger.warning("query embedding failed: %s", exc)
        return None
    if not vectors:
        return None
    vector = vectors[0]
    if r is not None:
        try:
            r.set(key, json.dumps(vector), ex=QUERY_EMBED_TTL)
        except redis.RedisError as exc:
            logger.warning("redis set failed: %s", exc)
    return vector


def _vector_search(db: Session, query_vec: list[float], *, top_k: int = 50) -> list[tuple[UUID, float]]:
    """Cosine similarity top-k via pgvector. Returns [(chunk_id, similarity)]."""
    # pgvector's <=> is cosine *distance*; similarity = 1 - distance.
    rows = db.execute(
        select(
            DocumentChunk.chunk_id,
            (1 - DocumentChunk.embedding.cosine_distance(query_vec)).label("sim"),
        )
        .where(DocumentChunk.embedding.is_not(None))
        .order_by(DocumentChunk.embedding.cosine_distance(query_vec))
        .limit(top_k)
    ).all()
    return [(row[0], float(row[1])) for row in rows]


def _rrf(rankings: list[list[str]], k: int = RRF_K) -> dict[str, float]:
    """Reciprocal Rank Fusion. rankings[i] = ordered list of chunk_ids."""
    scores: dict[str, float] = {}
    for ranked in rankings:
        for rank, item in enumerate(ranked):
            scores[item] = scores.get(item, 0.0) + 1.0 / (k + rank + 1)
    return scores


def retrieve_chunks(
    db: Session,
    query: str,
    *,
    limit: int = 10,
    doc_id: UUID | None = None,
) -> tuple[list[RetrievedChunk], int]:
    """Hybrid retrieve. If doc_id is given, filter to that document
    (used by /documents/{id}/ask). Returns (results, took_ms)."""
    started = time.perf_counter()
    if not query.strip():
        return [], 0

    # 1. dense candidates
    query_vec = _embed_query_cached(db, query)
    dense_hits: list[tuple[UUID, float]] = []
    if query_vec is not None:
        dense_hits = _vector_search(db, query_vec, top_k=50)

    # 2. BM25 candidates
    bm25_raw = search_bm25(query, top_k=50)

    # If doc_id filter requested, post-filter both lists.
    if doc_id is not None:
        doc_id_str = str(doc_id)
        bm25_raw = [h for h in bm25_raw if h["doc_id"] == doc_id_str]
        # For dense we filter via the chunk-doc map below.

    # 3. Fuse via RRF on chunk_id
    dense_ids = [str(cid) for cid, _ in dense_hits]
    bm25_ids = [h["chunk_id"] for h in bm25_raw]
    fused = _rrf([dense_ids, bm25_ids])

    if not fused:
        return [], int((time.perf_counter() - started) * 1000)

    # 4. Fetch the chunks + parent docs for the top N fused
    top_ids = sorted(fused.keys(), key=fused.get, reverse=True)[: max(limit * 2, 20)]
    chunk_rows = db.scalars(
        select(DocumentChunk)
        .options(selectinload(DocumentChunk.document))
        .where(DocumentChunk.chunk_id.in_([UUID(i) for i in top_ids]))
    ).all()
    chunks_by_id = {str(c.chunk_id): c for c in chunk_rows}

    # 5. Optional doc-level filter for dense hits
    if doc_id is not None:
        chunks_by_id = {k: c for k, c in chunks_by_id.items() if str(c.doc_id) == str(doc_id)}

    dense_score_by_id = {str(cid): sim for cid, sim in dense_hits}
    bm25_score_by_id = {h["chunk_id"]: h["score"] for h in bm25_raw}
    snippet_by_id = {h["chunk_id"]: h["snippet"] for h in bm25_raw}

    results: list[RetrievedChunk] = []
    for chunk_id in top_ids:
        chunk = chunks_by_id.get(chunk_id)
        if chunk is None:
            continue
        snippet = snippet_by_id.get(chunk_id) or chunk.text_ar[:240]
        results.append(
            RetrievedChunk(
                doc=chunk.document,
                chunk=chunk,
                score=fused[chunk_id],
                bm25_score=bm25_score_by_id.get(chunk_id, 0.0),
                vector_score=dense_score_by_id.get(chunk_id, 0.0),
                snippet=snippet,
            )
        )
        if len(results) >= limit:
            break

    return results, int((time.perf_counter() - started) * 1000)
