# smm-agent

An AI agent that automates **SOP-01 "Market Research"** — stage 1 of a 6-stage social media agency
workflow (Research → Branding & Guidelines → Content Calendar → Production → Publishing → Reporting). Given
a brand's uploaded material (and, in later steps, live market/competitor data), it produces a complete,
citation-verified Market Research document and routes it through a human (Team Lead) approval gate before
it feeds the next stage.

This is a real-world social media management agent with live inference against brand and market data — not
a generic "AI architect" tool. (`docs/Agent Pipeline UI Mockups/` contains two mockups from an unrelated
generic template example — ignore their D365/Contoso content; only the "Signal Brand Run" / "Signal Market
Intel" mockups describe this product.)

## Read first

1. `docs/Agent Pipeline UI Mockups/uploads/files/pipeline.md` and `dual-kb.md` — **the normative spec**:
   the P1–P7 pipeline invariants, the precise 3-call-site rule, the dual-KB trust boundary and topology
   choice (UNION vs BRIDGE), the build order. Written against a generic worked example (unrelated "D365"
   domain) — read for the invariants, not the example domain.
2. `docs/implement/dev_guidelines.md` — those invariants applied as concrete LLM/prompt engineering rules
   for this codebase (Jinja templates, structured output, domain knowledge store, guardrails, eval harness).
3. `docs/implement/step1_foundation.md`, `step2_ingest_hardening.md`, `step3_retrieval_generation.md` — the
   SMM-specific staged build plan. **Build in this order. Each step is additive on the previous one's proven
   contract — never a rewrite.** Step 3's file also lists the Step 4–9 roadmap.
4. `docs/SOP_1_Market_Research.docx`, `docs/TEMPLATE_1_Market_Research.docx` — the human process and exact
   output shape (11 sections) the agent encodes.
5. `docs/smm-agent-architecture-v2.mermaid` — four-plane architecture (Ingest → Retrieve → Generate →
   Deliver), two memories (Brand Workspace + Market Intel Core), human approval gate — the SMM-specific
   redraw of `dual-kb-architecture.mermaid`/`rag-pipeline-architecture.mermaid` in the same uploads folder.

This is a real-world social media management agent with live inference against brand and market data.
`docs/Agent Pipeline UI Mockups/` also contains two mockups from the same *generic* framework example
("Agent Runtime Pipeline v1", "Knowledge Base Build Pipeline v1" — D365/Contoso content) — irrelevant to
this project's domain, ignore them; only "Signal Brand Run" / "Signal Market Intel" describe this product.

## Non-negotiable engineering principles

**Pipeline invariants (`pipeline.md §1`)** — "the pipeline should be able to point at the page":

| | Invariant |
|---|---|
| P1 | One contract per boundary — no stage reaches two stages back |
| P2 | Exactly 3 generative call sites on the *query path*: Plan, Synthesize, Repair. Ingest-time calls are exempt if cached, off the latency path, and budgeted with a floor |
| P3 | Confinement (grant → `kb_id`) before retrieval, re-checked at hydration — never a post-hoc filter |
| P4 | Citation-or-reject, deterministic — no model judges its own grounding |
| P5 | Degrade, never fail — every ladder has a floor |
| P6 | Idempotent by content hash — re-ingest is a no-op |
| P7 | Confidence travels with the artifact — a boundary that drops it is a bug |

**Dual-KB trust boundary (`dual-kb.md`)**: Brand Workspace (`run:<brand_id>`) is the *query unit* —
per-brand, untrusted input, TTL-scoped, chunked finer/atomic. Market Intel Core (`core:<name>@v<N>`) is the
*evidence unit* — shared, curated, permanent/versioned, promoted only through a human-gated eval gate, never
written to automatically. Same code, different `ChunkConfig` profile — never fork the codebase for this.
Run content is always data (tagged `<evidence kb_id=... chunk_id=...>`), never instruction. Edges may point
lower-trust→higher-trust only (`run → core` legal, `core → run` never minted). Plan (call site ①) chooses
UNION (search both, RRF-fuse) vs BRIDGE (each Run chunk queries Core — this is where the agent earns its
keep vs. plain document Q&A; before writing BRIDGE code for Step 5, write the one-sentence bridge relation
first: *"for each `<run unit>`, find the `<core unit>` that `<relation>`"* — fixes chunk granularity on both
sides, expensive to change later).

**Applied concretely in this codebase:**
1. Prompts are `.jinja` files, never Python strings — rendered from a typed Pydantic context model. Never
   edit a versioned template in place — bump `v1 → v2`. Every call site declares a `response_model`.
2. Approval and quality gates are server-enforced — the API endpoint itself evaluates the gate and 422s on
   failure; disabled frontend buttons are UX convenience only, not the control.
3. Config over hardcoding — model names, temperature, token budgets live in `pydantic-settings`.
4. Domain knowledge (SMM terminology, tone rules) is a third, static YAML store — reviewed like code,
   injected unconditionally, never retrieved/ranked, never mixed into Core's cited chunks.

Full detail and rationale: `pipeline.md`, `dual-kb.md`, `docs/implement/dev_guidelines.md`.

## Testing policy

TDD, but keep total test volume minimal — bias heavily toward **integration tests** that drive a real
pipeline run or a real API call; reserve **unit tests** for genuinely pure/deterministic core logic where an
integration test would be slow or indirect (citation verification, C1–C8 validators, RRF fusion math,
quality-checkpoint evaluation, content-hash idempotency). Each step's own acceptance-test list (Step 1 §10,
Step 2 §10, Step 3 §9 in `docs/implement/`) is the target suite for that step — implement those first, add
more only when a real bug demonstrates a gap. See `TESTING.md`.

## Repo layout (target, per `docs/implement/step1_foundation.md §1`)

```
backend/
├── app/
│   ├── api/            # FastAPI routers
│   ├── domain/          # Pydantic models — the phase contracts
│   ├── orchestration/  # LangGraph nodes + graph
│   ├── retrieval/       # typed retrieval interface
│   ├── infra/            # db session, celery app, settings
│   ├── workers/         # Celery tasks
│   └── prompts/          # .jinja templates + partials
├── alembic/
├── tests/
└── pyproject.toml
frontend/
├── app/                  # Next.js App Router
├── components/
├── lib/                  # generated OpenAPI types, SSE client
└── package.json
infra/
├── docker-compose.yml   # postgres+pgvector, redis
└── alembic.ini
```

Stack: FastAPI + LangGraph orchestration + Postgres/pgvector + Redis/Celery + Next.js (App Router), an
OpenAI-compatible LLM client, prompts as Jinja templates.

## Current status

No code yet — Step 1 (`docs/implement/step1_foundation.md`) has not been started. Build in the order laid
out in "Read first" above.
