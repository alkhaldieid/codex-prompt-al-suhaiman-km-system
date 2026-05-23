# Al-Suhaiman Arabic-First KM PoC

Week 1 foundation for the ETHKA / Al-Suhaiman legal knowledge management proof-of-concept.

## Quick Start

```bash
docker compose up --build
```

Services:

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API docs: http://localhost:8000/docs

Seed users:

- lawyer.a@demo.suhaiman.sa / DemoPass123!
- lawyer.b@demo.suhaiman.sa / DemoPass123!
- reviewer@demo.suhaiman.sa / DemoPass123!
- admin@demo.suhaiman.sa / DemoPass123!

## Week 1 Scope Implemented

- Monorepo skeleton: `backend`, `frontend`, `infra`, `evals`.
- FastAPI backend with health/startup self-checks, JWT auth, RBAC dependency, Arabic problem responses, and LLMClient abstraction.
- PostgreSQL schema outline from the canonical data model, including audit and external LLM call tables.
- Next.js Arabic-first RTL login and empty home dashboard shell.
- Docker Compose development stack with Postgres, Redis, MinIO, OpenSearch, Vault dev, backend, and frontend.
- Terraform demo environment module structure and scaffolded AWS me-central-2 configuration.
- GitHub Actions CI scaffold with lint/test/security/AI-quality placeholders.

## Week 1 Open Decisions / Assumptions to Surface

- D2: SAMA access method still needs live verification. Default remains HTML scrape.
- D3: Cloud provider defaulted to AWS `me-central-2` pending ETHKA confirmation.
- D8: OpenAI ZDR request is human-owned by ETHKA.
- D9: OpenAI spend caps are human-owned account settings.
- A1-A8: PoC proceeds with the assumptions in the specification until validated by ETHKA / Al-Suhaiman.
