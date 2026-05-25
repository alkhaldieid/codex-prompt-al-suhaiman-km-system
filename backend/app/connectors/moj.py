"""Saudi Ministry of Justice — laws.moj.gov.sa connector.

Source-of-truth design notes live in docs/MOJ_CONNECTOR.md (the
discovery doc). Headline:

  - Ingest source is the detail JSON's inlined statuteStructure, NOT
    the PDF download endpoint. PDFs return 400 for every public caller
    including the SPA itself; the SPA never calls /document/download.
  - The JSON delivers article-numbered HTML fragments (just <p>, <ol>,
    <li>) with zero website chrome — much cleaner than the BOE HTML
    we scraped previously.
  - Endpoints:
      POST /apis/legislations/v1/statute/section-search   (listing)
      GET  /apis/legislations/v1/statute/get-Statute-gateway-Detail (detail)
  - No auth: open public API. Cookies are session/affinity only.

Each statuteStructure tree has three node types:
  type=3  →  باب (chapter)
  type=2  →  فصل (section)
  type=1  →  مادة (article — leaf, carries text)

We walk the tree depth-first and emit one ArticleChunk per article
leaf. Change detection uses statuteVersionId (etag) keyed by serial.
"""

from __future__ import annotations

import html
import logging
import re
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Document, DocumentChunk, DocumentStatus, SourceTrack
from app.services.text_processing import normalize_arabic

logger = logging.getLogger(__name__)

GATEWAY = "https://laws-gateway.moj.gov.sa"
CONNECTOR_ID = "moj_v1"
USER_AGENT = "ETHKA-Suhaiman-KM/1.0 (+legal@ethka.dev)"
DEFAULT_TIMEOUT = httpx.Timeout(30.0, connect=10.0)
PACING_SECONDS = 2.0
MAX_RETRIES = 3
RATE_LIMIT_BACKOFF = 60.0  # for 429s

# Map MoJ's Arabic legal types to the canonical doc_type enum (§3.1).
LEGAL_TYPE_TO_DOC_TYPE = {
    "نظام": "regulation",
    "لائحة": "regulation",
    "مرسوم ملكي": "royal_decree",
    "قرار مجلس الوزراء": "council_resolution",
    "تعميم": "circular",
    "قرار": "council_resolution",
}


# ──────────────────────────────────────────────────────────────────────
# Dataclasses
# ──────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class MoJItem:
    """One row from the listing endpoint."""
    serial: str
    statute_id: str
    statute_name: str
    legal_type: str


@dataclass(frozen=True)
class ArticleChunk:
    """One leaf article from statuteStructure."""
    breadcrumb: str   # e.g. "الباب الأول · أحكام عامة · المادة الأولى"
    label: str        # e.g. "المادة الأولى"
    text_html: str    # the raw HTML fragment from MoJ
    text_plain: str   # HTML stripped, whitespace normalised
    leaf_id: str      # MoJ's stable item id


@dataclass
class MoJDetail:
    serial: str
    statute_id: str
    statute_version_id: str
    name: str
    legal_type: str
    legal_status_id: int | None
    legal_status_name: str | None
    classification_id: int | None
    classification_name: str | None
    publish_date_gregorian: datetime | None
    issuance_date_gregorian: datetime | None
    articles: list[ArticleChunk]
    raw_model: dict


@dataclass
class SyncResult:
    items_seen: int = 0
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    skipped_empty: int = 0
    errors: list[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.errors is None:
            self.errors = []


# ──────────────────────────────────────────────────────────────────────
# HTTP helpers (httpx, polite pacing, retries)
# ──────────────────────────────────────────────────────────────────────


def _make_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        timeout=DEFAULT_TIMEOUT,
        follow_redirects=True,
        headers={
            "User-Agent": USER_AGENT,
            "Accept-Language": "ar,en;q=0.5",
            "Accept": "application/json",
            "Referer": "https://laws.moj.gov.sa/",
        },
    )


async def _request_with_retry(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    json: dict | None = None,
) -> httpx.Response:
    last_exc: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            resp = await client.request(method, url, json=json)
            if resp.status_code == 429:
                logger.warning("MoJ 429 — sleeping %ss before single retry", RATE_LIMIT_BACKOFF)
                await _sleep(RATE_LIMIT_BACKOFF)
                resp = await client.request(method, url, json=json)
            if resp.status_code >= 500:
                raise httpx.HTTPStatusError(
                    f"server error {resp.status_code}", request=resp.request, response=resp
                )
            resp.raise_for_status()
            return resp
        except (httpx.TimeoutException, httpx.HTTPStatusError, httpx.NetworkError) as exc:
            last_exc = exc
            wait = 2 ** attempt
            logger.warning("MoJ %s %s failed (%s); retry in %ss", method, url, exc, wait)
            if attempt < MAX_RETRIES - 1:
                await _sleep(wait)
    raise RuntimeError(f"MoJ request failed after {MAX_RETRIES} attempts: {last_exc}")


async def _sleep(seconds: float) -> None:
    import asyncio
    await asyncio.sleep(seconds)


# ──────────────────────────────────────────────────────────────────────
# API calls
# ──────────────────────────────────────────────────────────────────────


async def list_statutes(
    client: httpx.AsyncClient,
    *,
    page_number: int,
    page_size: int = 9,
    sorting_by: int = 7,
) -> list[MoJItem]:
    """Return one page of listing results, sorted newest-first by default."""
    payload = {
        "pageNumber": page_number,
        "pageSize": page_size,
        "sortingBy": sorting_by,
        "detailsKeyword": "",
        "LegalStatue": None,
        "classificationId": None,
        "statuteIssueDateFrom": None,
        "statuteIssueDateTo": None,
        "statuteName": "",
        "statutePublishDateFrom": None,
        "statutePublishDateTo": None,
        "statuteType": None,
        "keyword": "",
        "isSearch": False,
        "identityNumber": "",
    }
    resp = await _request_with_retry(
        client,
        "POST",
        f"{GATEWAY}/apis/legislations/v1/statute/section-search",
        json=payload,
    )
    data = resp.json()
    if not data.get("success"):
        raise RuntimeError(f"MoJ listing returned success=false: {data.get('message')}")
    items = data.get("model", {}).get("collection", []) or []
    return [
        MoJItem(
            serial=it["serial"],
            statute_id=it["statuteId"],
            statute_name=it["statuteName"],
            legal_type=it.get("legalType") or "",
        )
        for it in items
        if it.get("serial") and it.get("statuteName")
    ]


async def fetch_detail(client: httpx.AsyncClient, serial: str) -> MoJDetail:
    """Fetch detail JSON for a statute. Walks statuteStructure into
    article-level chunks ready for ingestion."""
    resp = await _request_with_retry(
        client,
        "GET",
        f"{GATEWAY}/apis/legislations/v1/statute/get-Statute-gateway-Detail"
        f"?Serial={serial}&identityNumber=",
    )
    data = resp.json()
    if not data.get("success"):
        raise RuntimeError(f"MoJ detail({serial}) returned success=false: {data.get('message')}")
    m = data["model"]
    return MoJDetail(
        serial=m["serial"],
        statute_id=m["statuteId"],
        statute_version_id=m["statuteVersionId"],
        name=m["name"],
        legal_type=m.get("legalType") or "",
        legal_status_id=m.get("legalStatueId"),
        legal_status_name=m.get("legalStatueName"),
        classification_id=m.get("classificationId"),
        classification_name=m.get("classificationName"),
        publish_date_gregorian=_parse_iso(m.get("publishDateGerogian")),
        issuance_date_gregorian=_parse_iso(m.get("gregorianValidFromDate")),
        articles=list(walk_statute_structure(m.get("statuteStructure") or [])),
        raw_model=m,
    )


# ──────────────────────────────────────────────────────────────────────
# Statute structure walker + HTML→plain
# ──────────────────────────────────────────────────────────────────────


_HTML_TAG_RE = re.compile(r"<[^>]+>")
_HTML_OL_BREAK = re.compile(r"</li\s*>", re.I)
_WHITESPACE_RUN = re.compile(r"[ \t]+")


def _html_to_plain(text_html: str) -> str:
    """Turn the MoJ's tiny HTML fragments into plain Arabic with newlines
    preserved between list items."""
    if not text_html:
        return ""
    s = _HTML_OL_BREAK.sub("\n", text_html)
    s = _HTML_TAG_RE.sub("", s)
    s = html.unescape(s)
    s = _WHITESPACE_RUN.sub(" ", s)
    lines = [line.strip() for line in s.splitlines()]
    return "\n".join(line for line in lines if line).strip()


def walk_statute_structure(nodes: Iterable[dict]) -> Iterable[ArticleChunk]:
    """DFS walk. Yields one ArticleChunk per leaf article (type=1) with a
    breadcrumb built from ancestor type=3 (باب) / type=2 (فصل) labels."""
    def _walk(node_list: Iterable[dict], breadcrumbs: list[str]):
        for node in node_list:
            seq = (node.get("sequence") or "").strip()
            name = (node.get("name") or "").strip()
            text_html = (node.get("text") or "").strip()
            children = node.get("items") or []
            # type=1 is article leaf with body text
            if node.get("type") == 1 and text_html:
                label = seq or "مادة"
                crumbs = breadcrumbs + ([label] if label else [])
                yield ArticleChunk(
                    breadcrumb=" · ".join(c for c in crumbs if c),
                    label=label,
                    text_html=text_html,
                    text_plain=_html_to_plain(text_html),
                    leaf_id=node.get("id") or "",
                )
            # Non-leaf — push breadcrumb and recurse
            if children:
                # Build the breadcrumb segment for this non-leaf node
                segment_bits = [s for s in (seq, name) if s]
                segment = " · ".join(segment_bits) if segment_bits else ""
                next_crumbs = breadcrumbs + ([segment] if segment else [])
                yield from _walk(children, next_crumbs)

    yield from _walk(nodes, [])


def _parse_iso(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def _doc_type_for(legal_type: str) -> str:
    return LEGAL_TYPE_TO_DOC_TYPE.get(legal_type.strip(), "regulation")


# ──────────────────────────────────────────────────────────────────────
# DB upsert
# ──────────────────────────────────────────────────────────────────────


def _upsert_document(db: Session, detail: MoJDetail) -> tuple[Document, bool, bool]:
    """Find or create the Document row for this MoJ serial.

    Returns (doc, is_created, content_changed). content_changed is True
    when the existing doc's etag differs from the new statuteVersionId
    (i.e. the law was amended).
    """
    existing = db.scalar(
        select(Document).where(
            Document.source_connector_id == CONNECTOR_ID,
            Document.source_external_id == detail.serial,
        )
    )
    if existing is None:
        doc = Document(
            title_ar=detail.name,
            doc_type=_doc_type_for(detail.legal_type),
            jurisdiction="KSA",
            source_track=SourceTrack.track1_external,
            visibility="firm_wide",
            status=DocumentStatus.published,
            content_hash_sha256="",  # filled after chunks built
            storage_key=f"moj/{detail.serial}",
            original_filename=f"{detail.name}.json",
            mime_type="application/json",
            processing_stage="done",
            status_detail_ar="مصدر تنظيمي رسمي من وزارة العدل، مفهرس للبحث",
            extracted_text="",  # filled below
            source_url=f"https://laws.moj.gov.sa/ar/legislation/{detail.serial}",
            source_connector_id=CONNECTOR_ID,
            source_external_id=detail.serial,
            source_external_etag=detail.statute_version_id,
            source_updated_at=detail.publish_date_gregorian,
        )
        db.add(doc)
        return doc, True, True

    content_changed = existing.source_external_etag != detail.statute_version_id
    if content_changed:
        # Wipe old chunks; new ones get added below.
        for chunk in list(existing.chunks):
            db.delete(chunk)
        existing.title_ar = detail.name
        existing.doc_type = _doc_type_for(detail.legal_type)
        existing.source_external_etag = detail.statute_version_id
        existing.source_updated_at = detail.publish_date_gregorian
        existing.status_detail_ar = "مصدر تنظيمي رسمي محدّث من وزارة العدل"
    return existing, False, content_changed


def _persist_chunks(db: Session, doc: Document, articles: list[ArticleChunk]) -> None:
    import hashlib
    parts = []
    for index, art in enumerate(articles, start=1):
        # text_ar carries the breadcrumb + the article body so retrieval
        # snippets show the full article location.
        body = f"{art.breadcrumb}\n\n{art.text_plain}".strip()
        parts.append(body)
        db.add(
            DocumentChunk(
                doc_id=doc.doc_id,
                chunk_index=index,
                text_ar=body,
                text_normalized=normalize_arabic(body),
                page_no=None,
                paragraph_no=index,
            )
        )
    full_text = "\n\n".join(parts)
    doc.extracted_text = full_text
    doc.content_hash_sha256 = hashlib.sha256(full_text.encode("utf-8")).hexdigest()


# ──────────────────────────────────────────────────────────────────────
# Sync orchestration
# ──────────────────────────────────────────────────────────────────────


async def sync(
    db: Session,
    *,
    max_pages: int = 5,
    page_size: int = 9,
    embed: bool = True,
    index_opensearch: bool = True,
) -> SyncResult:
    """Walk pages newest-first, upsert each statute. Stop early when a
    full page is all unchanged (we've hit known ground).

    Set embed=False to skip embedding (e.g. when OPENAI_API_KEY is
    missing); the backfill script picks them up later.
    """
    result = SyncResult()
    async with _make_client() as client:
        for page in range(1, max_pages + 1):
            try:
                items = await list_statutes(client, page_number=page, page_size=page_size)
            except Exception as exc:  # noqa: BLE001
                logger.warning("MoJ listing page %d failed: %s", page, exc)
                result.errors.append(f"page {page}: {exc}")
                break

            if not items:
                logger.info("MoJ listing page %d returned empty; stopping", page)
                break

            page_changed = 0
            for item in items:
                result.items_seen += 1
                try:
                    detail = await fetch_detail(client, item.serial)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("MoJ detail(%s) failed: %s", item.serial, exc)
                    result.errors.append(f"detail {item.serial}: {exc}")
                    continue
                # Polite pacing between detail calls
                await _sleep(PACING_SECONDS)

                if not detail.articles:
                    logger.info("MoJ %s has no articles in statuteStructure; skipping",
                                detail.name)
                    result.skipped_empty += 1
                    continue

                doc, is_new, content_changed = _upsert_document(db, detail)
                if is_new:
                    db.flush()  # need doc_id for chunk FK
                    _persist_chunks(db, doc, detail.articles)
                    db.commit()
                    result.created += 1
                    page_changed += 1
                elif content_changed:
                    db.flush()
                    _persist_chunks(db, doc, detail.articles)
                    db.commit()
                    result.updated += 1
                    page_changed += 1
                else:
                    result.unchanged += 1

                # Index into OpenSearch as we go
                if index_opensearch and (is_new or content_changed):
                    try:
                        from app.services.search_index import index_chunks  # noqa: WPS433
                        index_chunks(doc, doc.chunks)
                    except Exception as exc:  # noqa: BLE001
                        logger.warning("MoJ OS index for %s failed: %s", detail.name, exc)

            if embed:
                # Embed everything that landed unembedded this page
                try:
                    _embed_pending(db)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("MoJ post-page embed failed: %s", exc)

            # If nothing on this page changed, we've reached steady state
            if page_changed == 0:
                logger.info("MoJ sync: page %d all unchanged; stopping", page)
                break

    return result


def _embed_pending(db: Session) -> int:
    """Embed any unembedded chunks for MoJ docs, in batches of 32."""
    from app.core.config import get_settings
    from app.llm.policy import subject_from_document
    from app.services.openai_gateway import OpenAIBlockedError, embed_texts

    settings = get_settings()
    if not settings.openai_api_key:
        return 0

    docs = db.scalars(
        select(Document).where(Document.source_connector_id == CONNECTOR_ID)
    ).all()
    embedded = 0
    for doc in docs:
        todo = [c for c in doc.chunks if c.embedding is None]
        if not todo:
            continue
        subject = subject_from_document(doc)
        for start in range(0, len(todo), 32):
            batch = todo[start : start + 32]
            try:
                vectors = embed_texts(
                    db, [c.text_ar for c in batch], subject=subject, doc_id=doc.doc_id
                )
            except OpenAIBlockedError as exc:
                logger.info("MoJ embedding blocked for %s: %s", doc.title_ar, exc.reason)
                break
            for chunk, vec in zip(batch, vectors):
                chunk.embedding = vec
                embedded += 1
            db.commit()
    return embedded


# Sync wrapper for non-async callers (FastAPI startup is sync today)
def sync_blocking(db: Session, **kwargs) -> SyncResult:
    import asyncio
    return asyncio.run(sync(db, **kwargs))
