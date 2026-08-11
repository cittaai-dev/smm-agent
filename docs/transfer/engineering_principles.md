---
name: engineering-principles
description: "Non-negotiable design rules for smm-agent — the P1-P7 pipeline invariants, 3-call-site budget, dual-KB trust boundary, server-enforced approval gates"
metadata: 
  node_type: memory
  type: project
  originSessionId: 3c2927fc-d3fc-4131-94ed-20459d6449d7
  modified: 2026-08-10T23:59:58.771Z
---

Source of truth: `docs/Agent Pipeline UI Mockups/uploads/files/pipeline.md` and `dual-kb.md` — these are the
generic normative spec (originally written against a "D365 capabilities" example domain) that
`docs/implement/dev_guidelines.md` and `docs/implement/step{1,2,3}_*.md` apply literally to the SMM domain.
Read `pipeline.md`/`dual-kb.md` for the *why*; the step files for the SMM-specific *how*. See
[[project-overview]] and [[implementation-roadmap]].

## Pipeline invariants (`pipeline.md §1`) — "the pipeline should be able to point at the page"

| | Invariant |
|---|---|
| **P1** | One contract per boundary — Block IR crosses parse→chunk, Chunk crosses ingest→retrieve. No stage reaches two stages back. |
| **P2** | Three generative call sites on the *query path only*: Plan, Synthesize, Repair. Ingest-time model calls are exempt if content-addressed/cached, off the latency path, and budgeted with a floor (§2). |
| **P3** | Confinement before retrieval, re-checked at hydration — grants resolve to a `kb_id` set at the Postgres role *before* the first search, never a post-hoc filter (post-filtering leaks via result counts/timing even when text never renders). |
| **P4** | Citation-or-reject, deterministic — claim → `chunk_id` → `block_span` → page span, or rejected. No model judges its own grounding. |
| **P5** | Degrade, never fail — every ladder has a floor (ingest falls to L0, retrieval falls to dense-only, generation falls to returning evidence). Outages cost quality, not availability. |
| **P6** | Idempotent by content hash — re-ingesting a document is a no-op; bumping a version invalidates exactly the affected rows. |
| **P7** | Confidence travels with the artifact — `parser_confidence` → `order_confidence` → retrieval score → citation coverage. A boundary that drops confidence is a bug. |

**3 call sites in detail:** ① Plan (always fires, emits typed `RetrievalPlan` not prose — this is what
keeps it a call *site* not an agent loop). ② Synthesize (always fires, per-claim `chunk_id` tags, not a
bibliography at the end). ③ Repair (fires only on verifier rejection, single bounded retry, evidence
unchanged; rejected twice → return evidence + say grounding was insufficient, never an ungrounded answer
dressed as an answer).

Non-generative model calls (embedding, cross-encoder rerank) are not call sites — deterministic, cacheable,
add no reasoning surface.

## Dual-KB trust boundary (`dual-kb.md`)

- **Core KB chunks are evidence units** (coherent passage). **Run KB chunks are query units** (one atomic
  assertion). Different sizes because different objective functions — Run pipeline chunks finer, toward
  claim-separability not passage-coherence. For SMM: Run KB = Brand Workspace (`run:<brand_id>`), Core KB =
  Market Intel Core (`core:<name>@v<N>`).
- **Same code, different `ChunkConfig` profile** — not a fork. If you feel the urge to fork code for
  Core vs. Run, the profile abstraction is wrong.
- **Trust boundary, structurally enforced:** (1) Run content is data, never instruction — tagged evidence
  with `kb_id` visible, never system/tool text. (2) Run KB never writes into Core KB automatically —
  promotion is explicit, human-gated, never inferred from usage (otherwise upload = poisoning vector).
  (3) **C8′ edge confinement:** an edge may point from lower-trust into higher-trust (`run:x → core:y` is
  legal, stored in the run's scope, expires with it) — never the reverse (`core → run` is never minted).
- **One store, not two** — `kb_id` on the chunk record *is* the partition. A separate schema/DB/vector store
  is a decision you'd have to justify (Run chunks are a rounding error next to Core volume).
- **Two retrieval topologies**, chosen by the Plan call site: **UNION** (search both corpora, RRF fuse —
  "what does this say about X", cheap, one pass) vs **BRIDGE** (each Run chunk becomes a query against Core
  only — "map these to capabilities" / "gap-analyse against the market" — this is where the agent earns its
  keep vs. being a document-QA tool; cost is `n_run_chunks × k`, needs its own budget cap, not a hot-path
  default).
- **Before writing BRIDGE code (Step 5, `implementation-roadmap`):** write the bridge relation as one
  sentence first — *"for each `<run unit>`, find the `<core unit>` that `<relation>`."* This fixes chunk
  granularity on both sides and is expensive to change later. Not yet written for SMM — needs doing when
  Step 5 starts (likely: "for each brand-positioning/competitor claim in Run KB, find the Market Intel Core
  fact that supports or contradicts it").
- **Reproducibility:** `run_manifest: run_id → (core_kb_version, run_kb_hash)` — Core is immutable per
  version; a run pins a version at start so it replays identically months later.
- **Three separate runtimes/deploys** (different scaling signals, different failure modes): Core Builder
  (Service Bus → KEDA, generous amortized budget, staging→eval-gate→promote), Run Ingest (inline/fast
  worker, tight hard timeout), Query (hot path, the 3 call sites).

## Server-side enforcement (from the SMM step files, consistent with P3/P4)

- Approval and quality gates are enforced in the API endpoint itself (422 on failure), never just a
  disabled frontend button.
- Prompts are `.jinja` files rendered from a typed Pydantic context, never Python strings; every call site
  declares a `response_model`; never edit a versioned template in place (`v1 → v2`).
- Config (model names, temperature, token budgets) lives in `pydantic-settings`, never hardcoded.
