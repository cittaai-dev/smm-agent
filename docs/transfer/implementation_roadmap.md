---
name: implementation-roadmap
description: "Staged build plan for smm-agent (Steps 1-9) and current status — where we are, what's proven, what's next"
metadata: 
  node_type: memory
  type: project
  originSessionId: 3c2927fc-d3fc-4131-94ed-20459d6449d7
  modified: 2026-08-11T01:21:34.645Z
---

Staged plan from `docs/implement/step{1,2,3}_*.md`. Each step is additive on a proven contract from the
previous one — never a rewrite. See [[project-overview]] and [[engineering-principles]].

| Step | Scope | Status as of 2026-08-11 |
|---|---|---|
| 1 | Foundation: one brand, one file, one SOP-1 section (§1 Brand overview). Proves upload→chunk→plan→retrieve→synthesize→verify→deliver→approve end to end. 3 Postgres tables, 2 real call sites (Plan+Synthesize; Repair wired but untested). | **Done and merged to `main`** (2026-08-11). Backend: PR #1 (`step-1/backend`). Frontend + integration fixes: PR #2 (`step-1/frontend`), which also fixed two real bugs found only once a real browser hit the stack: (1) backend had no `CORSMiddleware` at all — every browser request failed preflight even though curl/scripted calls worked fine; fixed via a config-driven `SMM_API_CORS_ORIGINS` (`app/infra/settings.py` `ApiSettings`), not hardcoded; (2) a missing `SMM_LLM_OPENAI_API_KEY` crashed as an opaque 500 — now a clear 503 with an actionable message (`LLMNotConfiguredError` + FastAPI exception handler), surfaced into the frontend's `ApiError` message via parsing the `{"detail": ...}` body. Also fixed: `.env.example` documented the wrong var name (`OPENAI_API_KEY` vs. actual `SMM_LLM_OPENAI_API_KEY`), and no settings class had `env_file=".env"` configured so a local `.env` was never actually loaded. **Verified with a real OpenAI key**, full live round trip: upload → real Celery/Redis ingest → real GPT Plan+Synthesize → deterministic Verify (all claims verified, repair didn't need to fire) → approve. Frontend has 5 lite Vitest tests (core rendering/gating/request-shape only); backend has 9 tests (verifier units, Step 1 acceptance integration tests, CORS regression, missing-key regression). All 7 tests pass (3 unit on `verify_claims`, 4 integration matching `step1_foundation.md §10` exactly) against a real postgres+pgvector container; `ruff check` clean; FastAPI app boots and serves the expected routes. Frontend wizard (step1 §8) not started. Notable implementation choices: embeddings fall back to a deterministic offline hash-based vector when `OPENAI_API_KEY` unset (keeps ingest/retrieval testable without network); `call_site_trace` on `Deliverable` is derived from graph state (`plan`/`synthesize` always 1, `repair` = `int(repair_attempted)`) rather than a global call counter, so it stays correct under test doubles — the module-level `traced_llm_call` budget-enforcement decorator in `app/orchestration/tracing.py` is a separate, redundant safety net for production. LLM call sites (`call_plan`/`call_synthesize`/`call_repair` in `app/orchestration/llm.py`) are untested against a real OpenAI key — no key was available in the dev sandbox; tests monkeypatch these functions directly. |
| 2 | Ingest hardening: multi-file types (pdf/ppt/doc/png/csv/xlsx), full C1–C8 validators, chunk router (L0/L1), all 11 SOP-1 sections wired via a data-driven `SOP1_SECTIONS` registry. Core-dependent sections (§5/§6/§9/§10) deliberately degrade to `insufficient_evidence` — proves P5, not a gap. | Not started |
| 3 | Retrieve/Generate hardening: hybrid (dense+sparse, RRF-fused) retrieval + cross-encoder rerank, Repair actually exercised against fixtures, deterministic `QualityCheckpoint` gate, Annotate→Approve→Distribute flow with server-enforced gates, OTel spans + citation-rejection-rate metric. | Not started |
| 4 | Market Intel Core builder — curated corpus, eval gate, promotion workflow; unblocks §5/§6/§9/§10 | Not started |
| 5 | BRIDGE topology + live competitor/site crawl tools | Not started |
| 6 | Multi-tenant grant enforcement, TTL sweep, second brand onboarded | Not started |
| 7 | Client-facing reduced-projection view, distribution to client channel | Not started |
| 8 | Load testing, cost budgets, rate limiting, prompt-injection security review | Not started |
| 9 | CI/CD, staged deploy, production monitoring dashboards | Not started |

**Step 1 definition of done** (the bar for "ready to move to Step 2"): a claim in the delivered §1 text
traces `chunk_id → block_span → source file`, verifiable by opening the original doc, and all four
acceptance tests in `step1_foundation.md §10` pass (`test_citation_resolves`,
`test_fabricated_citation_rejected`, `test_idempotent_reupload`, `test_approval_gate_blocks_default`).

**Repo layout target (Step 1, `step1_foundation.md §1`):** `backend/app/{api,domain,orchestration,
retrieval,infra,workers}`, `backend/alembic`, `backend/tests`, `frontend/{app,components,lib}`,
`infra/docker-compose.yml`. Stack: FastAPI + LangGraph + Postgres/pgvector + Redis/Celery + Next.js App
Router, OpenAI-compatible LLM client, prompts as Jinja templates under `backend/app/prompts/`.
