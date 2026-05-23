# Production Saudi Regulatory RAG Target

This replaces the demo-source assumption. The production system is a Saudi regulatory intelligence and RAG platform whose corpus is built from official public Saudi legal and regulatory sources across domains.

## Target Outcome

- Cover official Saudi laws, regulations, implementing regulations, circulars, rules, decisions, gazette publications, regulatory guides, and public consultation drafts across all legal domains.
- Detect source updates continuously and update the RAG corpus from source-change events.
- Preserve version history so lawyers can ask about the law as of a specific date.
- Cite the official source URL and the exact article/paragraph/page where possible.
- Distinguish binding law/regulation from draft consultations, guidance, news, and explanatory material.

## Source Coverage Model

Source coverage is governed by `backend/app/connectors/registry.py`, not hardcoded connector code. Each source declares:

- official domains and entrypoints,
- legal domain coverage,
- source type,
- update detection strategy,
- priority,
- robots requirement,
- event-driven capability.

Tier 1 sources are mandatory for production launch:

- Bureau of Experts laws database.
- Umm Al-Qura official gazette.
- National Platform rules index.
- SAMA.
- CMA.
- ZATCA.
- MHRSD.

Tier 2 sources expand domain coverage:

- Ministry of Commerce.
- SFDA.
- CST.
- SDAIA / National Data Governance.
- Additional sector regulators added through the same registry contract.

## Event-Driven Update Model

Most government sites do not expose webhooks. The production design therefore uses event-triggered ingestion from detected source changes:

1. Source watchers poll lightweight manifests, list pages, sitemaps, feeds, or HEAD metadata.
2. Watchers compute source fingerprints using ETag, Last-Modified, canonical URL, and content SHA-256.
3. Any changed fingerprint emits `source.changed`.
4. `source.changed` enqueues a fetch/parse/version/index pipeline.
5. New or changed legal documents produce `regulation.version.created`.
6. `regulation.version.created` triggers OCR when needed, extraction, chunking, embeddings, OpenSearch indexing, and RAG cache invalidation.
7. Search and RAG always read from the latest published version unless the user asks for a historical date.

This is event-driven at the system boundary even when the upstream source only supports polling.

## RAG Requirements

- Store canonical regulation records separately from source pages.
- Keep `effective_date`, `published_date`, `gazette_issue`, `issuing_body`, `legal_status`, `source_type`, and supersession/amendment links.
- Chunk by article, clause, paragraph, schedule/table, and page for PDFs.
- Embed every published version.
- Never delete old versions from the legal corpus; mark them superseded.
- Search filters must include domain, issuer, status, date, source, and binding/draft/guidance type.
- RAG answers must cite official source passages and indicate whether the cited text is current, superseded, or draft.

## Completeness Controls

"All available Saudi regulations" is an operational target, not a one-time static list. Production needs:

- source registry reviews,
- source-health dashboards,
- failed-source alerts,
- missing-domain audits,
- legal reviewer sign-off for new source categories,
- periodic reconciliation against BOE, Umm Al-Qura, and regulator indices.

The system should report coverage percentage by source and domain instead of claiming silent completeness.
