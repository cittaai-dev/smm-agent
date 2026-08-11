# dual-kb.md

**Purpose.** Separate what the agent *knows* from what the agent was *handed this run* — across process, build, and runtime — without forking the pipeline.

**Working point.** These are not two pipelines. They are one pipeline run under two **profiles**, over one store partitioned by a field the contract already has. Forking the code is the failure mode, not the design.

**Scope guard.** Owns the profile split, the trust boundary, the bridge topology, and the build order. Stage internals stay in `parsers.md`, `chunking.md`, `pipeline.md`.

---

## 1. The first thing to do — before any code

> **Write the bridge relation as one sentence:**
> *For each `<run unit>`, find the `<core unit>` that `<relation>`.*

For the AI Architect agent: *for each requirement statement in the client BRD, find the D365 capability that satisfies it.*

Everything downstream is determined by that sentence, because it fixes **chunk granularity on both sides** — and granularity is the one thing you cannot cheaply change later. Get it wrong and you rebuild both indexes.

Do not skip to architecture. Write the sentence, then continue.

---

## 2. The distinction that actually matters

Budget and trust are the obvious differences. The deep one is **role**:

> **Core KB chunks are evidence units. Run KB chunks are query units.**

A good evidence unit is a coherent passage — enough context to support a claim. A good query unit is a single atomic assertion — one requirement, one clause, one question. These are *different sizes*, and no amount of budget tuning reconciles them.

So the Run pipeline chunks **finer**, and it chunks toward *separability of claims* rather than *coherence of passage*. That is a different objective function, not a cheaper one.

This is why the profiles differ on three axes, not one:

| Axis | Core KB | Run KB |
|---|---|---|
| **Role** | evidence unit | query unit |
| **Trust** | curated | **untrusted input** |
| **Budget** | amortized, generous | on the latency path, tight |

---

## 3. Profile table

| | Core KB | Run KB |
|---|---|---|
| `kb_id` | `core:<name>@v<N>` | `run:<run_id>` |
| Lifetime | permanent, versioned | TTL, dies with the session |
| Latency budget | minutes to hours | user is waiting |
| Stage 0 | all three tiers, vision reorder on | geometric only, no vision call |
| Chunk ladder | L0–L3, high L3 budget | **L1 only**, hard timeout |
| Chunk target | coherent passage | atomic claim |
| Determinism | reproducible, gated, promoted | best-effort, degrade fast |
| Scale | thousands of docs | 1–50 |
| Cost attribution | amortized across all runs | per-run, user-attributed |
| Failure posture | never lose fidelity — retry the build | degrade fast, tell the user |
| Grant | org / KB grant | session principal only |

Same code. Different `ChunkConfig`. If a difference cannot be expressed as config, it belongs in the contract — not in a second codebase.

---

## 4. Trust boundary

**Run KB is untrusted input.** A user-uploaded PDF can carry prompt injection. Three rules, all enforced structurally:

1. **Run content is data, never instruction.** It enters the model as tagged evidence with its `kb_id` visible, never as system or tool text.
2. **Run KB never writes into Core KB.** Promotion is an explicit, human-gated action — never automatic, never inferred from usage. Otherwise upload becomes a poisoning vector for every future run.
3. **Edges are directional across trust levels.**

### C8′ — refinement of the edge confinement invariant

> An edge may point **from lower-trust into higher-trust**, lives in the **lower-trust scope**, and expires with it. Never the reverse.

So `run:abc → core:d365@v7` is legal, stored under the run's scope, and vanishes at TTL. `core → run` is never minted. This is what lets the bridge exist without C8 leaking — the original invariant needed a direction, not an exception.

---

## 5. Storage — one store, not two

The chunk record already carries `kb_id`. That field *is* the separation:

```sql
-- the whole partition scheme
kb_id = 'core:d365@v7'    -- permanent, org grant
kb_id = 'run:01H8X...'    -- TTL, session grant
```

Grant-level confinement (P3) already scopes reads. Nothing new is needed. **A separate schema, a separate database, or a separate vector store is a decision you should have to justify** — and at these volumes you can't. Run chunks are a rounding error next to Core.

Two operational additions only: a TTL sweep on `run:*`, and a partial index so run-scoped queries don't scan the core partition.

---

## 6. Two retrieval topologies

The Plan call site (①) chooses the topology. This is the largest thing it decides — bigger than filters.

**UNION** — search both corpora, RRF fuse, answer.
Use for: *"what does this document say about X"*, *"summarise the uploads"*. Cheap, one pass.

**BRIDGE** — fan out: each Run chunk becomes a query against Core only.
Use for: *"map these requirements to capabilities"*, *"which of our standards does this contract violate"*, *"gap-analyse this against the product"*.

The bridge is where the agent earns its existence. Union is a document Q&A tool; bridge is the thing a person would otherwise do by hand for two days. It is also the pattern that justifies fine-grained Run chunking from §2 — fan-out over 400 vague chunks is noise, fan-out over 400 atomic requirements is a deliverable.

Bridge cost is `n_run_chunks × k`, so it needs its own budget and a cap. It is not a hot-path default.

---

## 7. Reproducibility — pin the pair

```
run_manifest: run_id → (core_kb_version, run_kb_hash)
```

Core KB is immutable per version and promoted, never mutated in place. A run pins a version at start. That pair **fully determines the evidence set**, so a run replays identically months later — which is the difference between an agent you can audit and one you can only re-run and hope.

`run_kb_hash` comes free from P6 content addressing. And P6 pays a second dividend here: **re-uploading the same document mid-session costs nothing**, which matters because iterating on one document is the dominant agent session shape.

---

## 8. Three runtimes

| Runtime | Trigger | Scale | Budget |
|---|---|---|---|
| **Core Builder** | document arrival → Service Bus | KEDA on queue depth, Container Apps job | generous, amortized |
| **Run Ingest** | agent request | inline or fast worker, latency-bound | tight, hard timeout |
| **Query** | agent turn | hot path, 3 call sites | per-query |

Separate deploys because they scale on different signals and fail differently. A Core build backlog must never slow a user's run; a burst of uploads must never starve the builder.

The Core builder is a **build**, not a job: staging version → eval gate (L0 ratio, degraded ratio, citation rejection on a golden set) → promote. Failing the gate leaves the live version untouched.

---

## 9. Build order — seven steps

The sequence is deliberately constraint-first. **Build the Run path before the Core path**, because the profile difference is only budget + trust + granularity: if you build Core first with an unlimited budget, you will make choices the Run profile cannot afford, and discover it late. Building constrained-first makes Core "the same code with the dial turned up" — trivially derived. The reverse is not.

**Step 0 — One document, no KB, one citation.**
Upload → blocks → L1 chunks → synthesize → verify → a citation that resolves to a page span. No Core KB, no L2/L3, no hydration, no bridge.
*Learn:* whether your contract actually holds end to end. If a citation cannot resolve to a page here, nothing built later fixes it.

**Step 1 — Introduce `kb_id` with two trivially small corpora.**
Core = 3 documents. Run = 1 upload. Retrieve from each independently under grant scope.
*Learn:* the separation is a field, not a fork. If you feel the urge to fork the code here, the profile abstraction is wrong.

**Step 2 — Build the bridge on 10 run chunks.**
Each run chunk as a query against Core.
*Learn:* whether your Run granularity is right. This is where §2 becomes concrete — you will *see* that passage-sized run chunks make mushy queries. Fix granularity here, before the index is large enough to hurt.

**Step 3 — Version and pin.**
`core:name@vN`, run manifest, replay an old run and get identical evidence.
*Learn:* reproducibility, and what breaks it.

**Step 4 — Split the runtimes.**
Move Core build to the KEDA worker with a promote step. Run ingest stays inline.
*Learn:* the failure modes are genuinely different — this is where the split stops being theoretical.

**Step 5 — Turn on the ladders, per profile.**
Core gets Stage 0 full, L2, L3, hydration, reference resolver. Run stays L1 + timeout.
*Learn:* what each ladder rung is actually worth, measured against the Step 0–3 baseline rather than assumed.

**Step 6 — Injection defence and eval gates.**
Run content tagged as data. Golden set. Gate promotion on it.

Steps 0 and 3 are the ones that get skipped under pressure. Step 0 skipped means you never find out your citations don't resolve until a user does. Step 3 skipped means you can never explain an answer the agent gave last month.

---

## 10. Open

1. **Bridge fan-out cost control** — `n × k` grows fast on a 200-page BRD. Needs either run-chunk clustering before fan-out, or a two-stage cheap-filter-then-rerank. Measure first; do not pre-optimise.
2. **Run KB reuse across turns in one session** — the TTL is session-scoped, but a multi-turn agent re-queries the same uploads. Cache the run index for the session lifetime, keyed by `run_kb_hash`.
3. **Promotion flow** — when a run document *should* become core knowledge, the human-gated path needs a real UI and an audit trail. Deferred, but do not let it get built accidentally.
