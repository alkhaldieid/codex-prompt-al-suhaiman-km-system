"""OpenSearch BM25 indexing for chunks (spec §6.4).

Single index `documents_v1` with the Arabic analyzer chain:
  standard tokenizer + lowercase + arabic_normalization + arabic_stemmer
  + decimal_digit + asciifolding

`ensure_index()` is idempotent — runs at startup.
`index_chunks()` bulk-loads a set of chunks for one doc.
`backfill_all_chunks()` reindexes everything (used on first boot if the
index is empty).
"""

from __future__ import annotations

import logging
import os
from typing import Iterable

from opensearchpy import OpenSearch, helpers
from opensearchpy.exceptions import ConnectionError as OSConnectionError

from app.models import Document, DocumentChunk

logger = logging.getLogger(__name__)

INDEX_NAME = "documents_v1"

_client: OpenSearch | None = None


def get_client() -> OpenSearch:
    global _client
    if _client is None:
        host = os.environ.get("OPENSEARCH_HOST", "opensearch")
        port = int(os.environ.get("OPENSEARCH_PORT", "9200"))
        _client = OpenSearch(
            hosts=[{"host": host, "port": port}],
            http_compress=True,
            use_ssl=False,
            verify_certs=False,
            timeout=15,
        )
    return _client


# Spec §6.4 analyzer chain.
INDEX_BODY = {
    "settings": {
        "analysis": {
            "analyzer": {
                "arabic_legal": {
                    "type": "custom",
                    "tokenizer": "standard",
                    "filter": [
                        "lowercase",
                        "arabic_normalization",
                        "arabic_stemmer_filter",
                        "decimal_digit",
                        "asciifolding",
                    ],
                }
            },
            "filter": {
                "arabic_stemmer_filter": {
                    "type": "stemmer",
                    "language": "arabic",
                }
            },
        }
    },
    "mappings": {
        "properties": {
            "doc_id": {"type": "keyword"},
            "chunk_id": {"type": "keyword"},
            "title_ar": {"type": "text", "analyzer": "arabic_legal"},
            "text_ar": {"type": "text", "analyzer": "arabic_legal"},
            "paragraph_no": {"type": "integer"},
            "page_no": {"type": "integer"},
            "doc_type": {"type": "keyword"},
            "practice_area": {"type": "keyword"},
            "source_track": {"type": "keyword"},
        }
    },
}


def ensure_index() -> None:
    client = get_client()
    try:
        if client.indices.exists(index=INDEX_NAME):
            return
        client.indices.create(index=INDEX_NAME, body=INDEX_BODY)
        logger.info("created OpenSearch index %s", INDEX_NAME)
    except OSConnectionError as exc:
        logger.warning("OpenSearch unreachable, skipping index ensure: %s", exc)


def _chunk_action(doc: Document, chunk: DocumentChunk) -> dict:
    return {
        "_op_type": "index",
        "_index": INDEX_NAME,
        "_id": str(chunk.chunk_id),
        "_source": {
            "doc_id": str(doc.doc_id),
            "chunk_id": str(chunk.chunk_id),
            "title_ar": doc.title_ar,
            "text_ar": chunk.text_ar,
            "paragraph_no": chunk.paragraph_no,
            "page_no": chunk.page_no,
            "doc_type": doc.doc_type,
            "practice_area": doc.practice_area or [],
            "source_track": doc.source_track.value if hasattr(doc.source_track, "value") else doc.source_track,
        },
    }


def index_chunks(doc: Document, chunks: Iterable[DocumentChunk]) -> int:
    client = get_client()
    actions = [_chunk_action(doc, c) for c in chunks]
    if not actions:
        return 0
    try:
        success, _ = helpers.bulk(client, actions, refresh="wait_for")
        return success
    except Exception as exc:  # noqa: BLE001
        logger.warning("opensearch bulk index failed: %s", exc)
        return 0


def backfill_all_chunks(db) -> int:
    """If the index is empty (first boot after Step 2 deploys), reindex
    every chunk in the database. Returns count indexed."""
    client = get_client()
    try:
        ensure_index()
        count = client.count(index=INDEX_NAME)["count"]
    except OSConnectionError as exc:
        logger.warning("OpenSearch unreachable, skipping backfill: %s", exc)
        return 0
    if count > 0:
        logger.info("OpenSearch already has %d chunks; skipping backfill", count)
        return 0

    from sqlalchemy.orm import selectinload  # local import to keep top clean
    from sqlalchemy import select

    docs = db.scalars(select(Document).options(selectinload(Document.chunks))).all()
    total = 0
    for doc in docs:
        total += index_chunks(doc, doc.chunks)
    logger.info("backfilled %d chunks into %s", total, INDEX_NAME)
    return total


def search_bm25(query: str, *, top_k: int = 50) -> list[dict]:
    """Return [{chunk_id, doc_id, score, snippet}] from OpenSearch BM25."""
    client = get_client()
    body = {
        "size": top_k,
        "query": {
            "multi_match": {
                "query": query,
                "type": "best_fields",
                "fields": ["text_ar^3", "title_ar^2"],
                "operator": "or",
                "minimum_should_match": "30%",
            }
        },
        "highlight": {
            "pre_tags": ["<em>"],
            "post_tags": ["</em>"],
            "fields": {"text_ar": {"fragment_size": 240, "number_of_fragments": 1}},
        },
        "_source": ["doc_id", "chunk_id", "paragraph_no", "text_ar"],
    }
    try:
        resp = client.search(index=INDEX_NAME, body=body)
    except Exception as exc:  # noqa: BLE001
        logger.warning("opensearch query failed: %s", exc)
        return []
    hits = resp.get("hits", {}).get("hits", [])
    out = []
    for hit in hits:
        src = hit["_source"]
        highlight = hit.get("highlight", {}).get("text_ar", [None])[0]
        out.append(
            {
                "chunk_id": src["chunk_id"],
                "doc_id": src["doc_id"],
                "score": hit["_score"],
                "snippet": highlight or src["text_ar"][:240],
                "paragraph_no": src.get("paragraph_no"),
            }
        )
    return out
