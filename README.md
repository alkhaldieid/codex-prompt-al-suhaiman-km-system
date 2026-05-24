# Al-Suhaiman Arabic-First Legal KM PoC

Arabic-first legal knowledge-management proof-of-concept for
Al-Suhaiman Lawyers & Legal Consultants, built by ETHKA. RTL Next.js
frontend, FastAPI + Postgres/pgvector + OpenSearch backend, GPT-5 for
Q&A / OCR / autotag (under the §10.7 residency exception).

The full design lives in **[`docs/spec_v1.1.txt`](docs/spec_v1.1.txt)**.
The current state of the implementation, the deviations from the spec,
the open issues, and the next-step priorities are in
**[`docs/HANDOFF.md`](docs/HANDOFF.md)** — **read that first if you are
picking up this project**.

## Quick start

```bash
# Put OPENAI_API_KEY in .env (see docs/HANDOFF.md §5 for the full template)
cp .env.example .env && $EDITOR .env

docker compose up -d --build
```

| Service | URL |
|---|---|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| OpenAPI docs | http://localhost:8000/docs |
| OpenSearch | http://localhost:9200 |
| MinIO console | http://localhost:9001 (`minioadmin`/`minioadmin`) |

Seed users (all password `DemoPass123!`):
`lawyer.a@demo.suhaiman.sa`, `lawyer.b@demo.suhaiman.sa`,
`reviewer@demo.suhaiman.sa`, `admin@demo.suhaiman.sa`.

After a first boot, run the embedding backfill once:

```bash
docker compose exec backend python /app/scripts/embed_unembedded_chunks.py
```

## What works today

The §1.2 seven-step demo runs end-to-end:

1. Drag-and-drop an Arabic document onto `/upload` →
2. inline pdfplumber/python-docx extraction (OCR fallback via
   GPT-5 vision for scanned PDFs) →
3. article-marker-atomic chunking (spec §6.1) →
4. GPT-5 auto-tagging (`doc_type`, `practice_area`, confidence) →
5. embedding in batches of 32 via the single OpenAI gateway →
6. "تأكيد وفهرسة" promotes to published →
7. `/search` returns hybrid-ranked results (BM25 + pgvector via RRF) →
8. `/documents/{id}` renders a paragraph-numbered reading pane →
9. The Q&A panel calls GPT-5 with the spec §6.6 system prompt verbatim
   and returns an Arabic answer with `[¶N]` citations that smooth-scroll
   the reading pane.

Six real Saudi laws are pre-seeded from the Bureau of Experts
(`fixtures/regulatory/`): Civil Transactions, Labor, Companies, PDPL,
AML, Commercial Courts. 508 chunks, all embedded.

Quality gates pass at thresholds set by spec §1.2:

- Recall@10 = 1.000 (≥0.80), MRR = 0.975 (≥0.60) on 20 queries
- RAG faithfulness = 0.900 (≥0.90) on 20 Q/A pairs

## Run the eval harness

```bash
python3 scripts/run_ai_quality.py --mode smoke       # per-PR gate (5 queries)
python3 scripts/run_ai_quality.py --mode full        # main/nightly (20 queries)
python3 scripts/run_rag_faithfulness.py              # 20 Arabic Q/A pairs
```

All three exit non-zero if thresholds fail. CI wiring is in
`.github/workflows/build.yml`.

## Architecture in one diagram

```
Next.js (RTL, Arabic)  :3000
        │
        ▼
FastAPI :8000  ─── services/openai_gateway.py  ───────► OpenAI
                   (single egress; §10.7 preflight + audit)
        │
        ├── Postgres + pgvector (HNSW cosine, 1536-dim)
        ├── OpenSearch documents_v1 (Arabic analyzer)
        └── Redis (query-embedding cache, 1h TTL)
```

The whole flow plus the deviations from spec is documented in
`docs/HANDOFF.md` §3–§7.

## Repository layout

```
backend/      FastAPI app, SQL migrations, OpenAI gateway
frontend/     Next.js 16 App Router pages and components
fixtures/     6 real Saudi laws (BOE) + synthetic Arabic ruling
scripts/      one-shot fetch + idempotent embedding backfill + quality evals
evals/        retrieval and faithfulness benchmarks
infra/        Terraform skeleton (not deployed in PoC)
docs/         spec v1.1 + handoff document + production target notes
```

## Handing this off

If you are picking this project up (human or AI agent), the canonical
on-boarding path is:

1. **`docs/HANDOFF.md`** — what was built, the trade-offs, the open
   work, the gotchas, the cost numbers.
2. **`docs/spec_v1.1.txt`** — the spec the implementation is measured
   against. §1.2 (demo), §6.6 (RAG prompt), §7.2 (autotag prompt), and
   §10.7 (residency exception) are the load-bearing sections.
3. Then start a `docker compose up -d`, hit `/api/v1/health`, and the
   handoff doc walks you through verifying the live state.

## Cost reality

Cumulative OpenAI spend across the whole build through the §1.2 demo:
**≈ $0.46** against the $50/day soft cap and $1 000 project hard cap.
Breakdown in `docs/HANDOFF.md` §2.
