# pipeline.md

**Purpose.** One pipeline, four planes, one contract per boundary. Everything from a raw file to a cited answer whose every claim resolves to a page span in the original.

**Working point.** A RAG system fails at its seams, not its stages. Each stage is easy alone. What kills the system is a stage reaching past its neighbour, or a confidence number getting dropped at a boundary. This file owns the seams.

**Scope guard.** Index and law. Stage internals live in `parsers.md`, `chunking.md`, `ingestion.md`. This file owns the plane boundaries, the pipeline invariants, and the retrieval + generation halves the whiteboard never drew.

**Essence.** *The pipeline should be able to point at the page.* Every design choice below is downstream of that one sentence.

---

## 1. Pipeline invariants

| | Invariant | Why it exists |
|---|---|---|
| **P1** | **One contract per boundary.** Block IR is the only thing crossing parse→chunk. The Chunk record is the only thing crossing ingest→retrieve. No stage reaches two stages back. | Seams are where systems rot |
| **P2** | **Three generative call sites on the query path.** Plan, Synthesize, Repair. Ingest-time model calls are exempt — see §2. | Latency, cost, and reasoning surface area |
| **P3** | **Confinement before retrieval, re-checked at hydration.** Grants resolve to a `kb_id` set at the Postgres role *before* the first search. Never a post-hoc filter. | Post-filtering leaks through result counts and timings |
| **P4** | **Citation-or-reject, deterministic.** Claim → `chunk_id` → `block_span` → page span, or the claim is rejected. No model judges its own grounding. | A model grading itself is not a control |
| **P5** | **Degrade, never fail.** Every ladder has a floor. Ingest falls to L0. Retrieval falls to dense-only. Generation falls to returning evidence. | Outages should cost quality, not availability |
| **P6** | **Idempotent by content hash.** Re-ingesting a document is a no-op. Bumping a version invalidates exactly the affected rows. | Re-index is the most expensive accident in RAG |
| **P7** | **Confidence travels with the artifact.** `parser_confidence` → `order_confidence` → retrieval score → citation coverage. A boundary that drops confidence is a bug. | Silent degradation is worse than loud failure |

---

## 2. Reconciling the three-call-site rule

Ingest added model calls: document understanding, vision descriptions, table descriptions, vision reorder, L2 embeddings, L3 split planning, R3 disambiguation. That looks like a violation. It isn't — the rule needs stating precisely.

> **The three-call-site budget is a *query-path* budget, and it counts *generative* calls only.**

Ingest calls are exempt on three conditions, all enforced:

1. **Content-addressed and cached.** Same input hash → same output, no call. So they are pure functions with a slow first evaluation.
2. **Off the latency path.** They cost throughput, never response time.
3. **Budgeted with a floor.** Each has a per-document cap and a deterministic fallback (P5).

Non-generative model calls — embedding, cross-encoder reranking — are not call sites either. They are deterministic scorers, cacheable, and they add no reasoning surface.

**The query path holds at exactly three:**

| | Call site | Fires | Output |
|---|---|---|---|
| ① | **Plan** | always | typed `RetrievalPlan`, not prose |
| ② | **Synthesize** | always | answer with per-claim `chunk_id` tags |
| ③ | **Repair** | only on verifier rejection | one bounded retry |

Three, and the third is conditional. That is the whole reasoning budget of the query path.

---

## 3. Plane 1 — Ingest

Fully specified in `parsers.md` and `chunking.md`. Shape only:

```
sources → document understanding → parser ladder → typed blocks
        → stage 0 reading order → pre-pass → chunk router
        → chunk ladder L0–L3 → assembler → validator C1–C8 → embed → store
```

Two loops hang off it: the validator returns failures to the router, and the reference resolver re-sweeps `pending_references` whenever a new document lands.

---

## 4. Plane 2 — Retrieve

### 4.1 Grant resolution comes first

Before anything else, the principal resolves to a `kb_id` set at the Postgres role. Search runs *inside* that scope.

Post-hoc filtering is the standard mistake and it leaks even when the text never renders — result counts, score distributions, and latency all carry signal about documents the principal cannot read. Scope first, and the leak is structurally impossible rather than defended against.

### 4.2 ① Plan — LLM call site 1

Query in, a **typed plan** out — never prose:

```python
@dataclass(frozen=True)
class RetrievalPlan:
    sub_queries: list[str]
    filters: dict          # doc_type, date_range, section, source
    edge_kinds: list[str]  # which hydration edges are worth following
    k_per_query: int
```

Emitting a typed object rather than a rewritten string is what keeps this a call *site* rather than an agent loop. It is one call, it returns a struct, the struct is validated, and control returns to deterministic code.

`edge_kinds` matters more than it looks: a factual lookup wants `describes` and `continues`; a "how does X relate to Y" question wants `references`. Choosing the traversal at plan time avoids hydrating the wrong neighbourhood.

### 4.3 Hybrid search

Dense (pgvector cosine) and sparse (BM25 over tsvector) per sub-query, fused with RRF. Rank fusion rather than score fusion — no normalisation to tune, and it survives the two retrievers disagreeing about scale.

### 4.4 Rerank

Cross-encoder over the fused top-k. Deterministic, cacheable by `(query, chunk_id)`, not a generative call site.

### 4.5 Graph hydration

The payoff for deleting overlap in `chunking.md`. Follow `follows` / `continues` / `describes` / `references` from matched chunks, depth-capped with a visited set.

**The grant is re-checked per edge (C8/P3).** Edges are already KB-scoped at write time; re-checking at read time means a stale or mis-minted edge cannot become a lateral path around the grant. Cheap, and it makes the graph safe by construction rather than by care.

### 4.6 Context assembly

Three deterministic steps:

1. **Dedupe by `block_span` overlap.** Because chunk ids are content-addressed over block spans, overlapping evidence is detectable *exactly*. No fuzzy text similarity, no near-duplicate heuristics.
2. **Restore document order** by `(doc_id, block_index)`. Evidence arrives ranked; the model reads it far better in document order. Ranking decides *what* is included, not *what order* it appears in.
3. **Budget-pack**, dropping the lowest-scoring tail.

---

## 5. Plane 3 — Generate

### 5.1 ② Synthesize — LLM call site 2

Grounded generation. Every claim carries the `chunk_id` it came from. Not a bibliography at the end — per-claim tags, because the verifier needs claim-level granularity.

### 5.2 Verify — deterministic, no model

For each claim: does the tagged `chunk_id` exist in the assembled context, and does it resolve through `derived_from` to a block span and a page span?

That is a lookup, not a judgment. It catches the two failures that matter — a fabricated citation, and a claim with no citation at all. It does not catch a claim that misreads a real chunk, and it is honest about that: use it as a floor, not a truth oracle.

### 5.3 ③ Repair — LLM call site 3

Fires only on rejection. Failing claims are marked, evidence unchanged, single bounded retry. Rejected twice → **return the evidence and say the grounding was insufficient**. Never an ungrounded answer dressed as an answer (P5).

---

## 6. Plane 4 — Observe

OTel `gen_ai.*` spans across all planes. Six metrics carry the system:

| Metric | Reads as |
|---|---|
| **L0 routing ratio** | health of parse + reading order. High means the bug is upstream, not in chunking |
| **Degraded chunk ratio** | how much of the corpus took a fallback |
| **`order_confidence` distribution** | multi-column and scan quality, per source |
| **Citation rejection rate by doc type** | which document classes the retriever cannot ground |
| **Hydration depth + edge-kind mix** | whether `edge_kinds` planning is actually working |
| **Cost per call site + cache hit rate** | the three-site budget, verified rather than assumed |

Two feed back into ingest: **L0 ratio** triggers parser work, **citation rejection rate** triggers `z` recalibration and chunk-strategy review.

---

## 7. Failure matrix

| Failure | Detected by | Degrades to |
|---|---|---|
| Parser returns garbage | `parser_confidence` floor | L0 chunking, `degraded=true` |
| Column order scrambled | continuity probe | vision reorder, then L0 |
| L3 budget exhausted | router counter | L1 structural |
| Embedding service down | call timeout | sparse-only retrieval |
| Rerank service down | call timeout | RRF order |
| Reference target not ingested | resolver miss | stays pending, resolves retroactively |
| Model fabricates a citation | verifier | Repair, then insufficient-grounding |
| Grant mis-scoped edge | hydration re-check | edge skipped silently |

Every row degrades. No row fails the request.

---

## 8. Build order

1. **Contracts** — Block IR, Chunk record, edge table, grant model. Nothing else compiles until these are frozen.
2. **Validator C1–C8** — before any strategy exists, so every strategy is born already checked.
3. **L1 structural** — the default path. A working pipeline with one strategy beats four half-built ones.
4. **Hybrid + RRF** — retrieval end to end, no rerank, no hydration. Measure.
5. **Verifier** — deterministic citation resolution. This is what makes the system trustworthy; add it before the answer quality feels good, not after.
6. **Then the ladders** — Stage 0, L2, L3, hydration, resolver. Each one earns its place against a measured baseline.

Steps 2 and 5 are the ones that get skipped under pressure, and they are the two that make everything after them cheap.
