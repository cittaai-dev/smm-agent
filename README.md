# smm-agent

A grounded, citation-verified AI agent that automates SOP-01 "Market Research" for a social media agency
workflow. See [CLAUDE.md](CLAUDE.md) for architecture, engineering principles, and the staged build plan;
see [TESTING.md](TESTING.md) for the testing policy.

Status: scaffolding only — Step 1 implementation (`docs/implement/step1_foundation.md`) has not started yet.

## Layout

- `backend/` — FastAPI + LangGraph orchestration + Postgres/pgvector + Celery/Redis
- `frontend/` — Next.js (App Router)
- `infra/` — docker-compose for local dev (postgres+pgvector, redis)
- `docs/` — SOPs, templates, architecture diagram, and the `implement/` build plan
