# Step 3 — Improve Phase 2 (Retrieve/Generate): Hybrid Search, Quality Gate, Approval + Distribution

## Objective

Step 2 proved multi-file ingest and all 11 sections wired (7 live, 4 correctly degraded pending Core).
Step 3 hardens **Retrieve** and **Generate** for the sections that *do* have data — dense-only becomes
hybrid+reranked, Repair becomes exercised and tested (not just wired), and the SOP-1 human steps (12–13:
Team Lead review/annotate, approve, distribute) become real, gated features. Market Intel Core is still
Step 4 — this step makes the brand-only sections production-grade on their own terms.

**Definition of done:** retrieval quality is measured (not assumed), every SOP-1 quality checkpoint is a
deterministic gate blocking approval, and a Team Lead can annotate, approve, and distribute a real document
through the API — with the server enforcing the gate, not the UI.

---

## 1. What Changes From Step 2

| Step 2 | Step 3 |
|---|---|
| Dense-only retrieval | Hybrid: dense (pgvector) + sparse (`tsvector`/`ts_rank`) fused with RRF |
| No rerank | Cross-encoder rerank on fused top-k, cached by `(query, chunk_id)` |
| Repair wired, untested | Repair exercised against real rejection cases, single bounded retry proven |
| No quality gate | `QualityCheckpoint` — deterministic, blocks `approve` |
| Approve = final state | Approve → `StrategicNote` (annotate) is a distinct prior step; `DistributionRecord` follows approval |
| No metrics | OTel spans + the citation-rejection-rate metric, per section |

---

## 2. Hybrid Retrieval (`retrieval/hybrid.py`)

```python
from app.domain.chunk import Chunk

def search_hybrid(kb_id: str, plan: "RetrievalPlan") -> list[Chunk]:
    dense_results = _dense_search(kb_id, plan.sub_queries, k=plan.k_per_query)
    sparse_results = _sparse_search(kb_id, plan.sub_queries, k=plan.k_per_query)
    fused = _rrf_fuse(dense_results, sparse_results, k=60)
    return _rerank(fused, plan.sub_queries[0])[: plan.k_per_query]

def _dense_search(kb_id, queries, k):
    embeddings = [embed(q) for q in queries]
    return db_query("""
        SELECT chunk_id, kb_id, doc_id, block_span, text, order_confidence, degraded
        FROM chunk WHERE kb_id = :kb ORDER BY embedding <=> :qvec LIMIT :k
    """, kb=kb_id, qvec=embeddings[0], k=k)

def _sparse_search(kb_id, queries, k):
    return db_query("""
        SELECT chunk_id, kb_id, doc_id, block_span, text, order_confidence, degraded
        FROM chunk WHERE kb_id = :kb AND tsv @@ plainto_tsquery(:q)
        ORDER BY ts_rank(tsv, plainto_tsquery(:q)) DESC LIMIT :k
    """, kb=kb_id, q=queries[0], k=k)

def _rrf_fuse(dense, sparse, k=60):
    scores = {}
    for rank, c in enumerate(dense):
        scores[c.chunk_id] = scores.get(c.chunk_id, 0) + 1 / (k + rank)
    for rank, c in enumerate(sparse):
        scores[c.chunk_id] = scores.get(c.chunk_id, 0) + 1 / (k + rank)
    by_id = {c.chunk_id: c for c in [*dense, *sparse]}
    return [by_id[cid] for cid, _ in sorted(scores.items(), key=lambda x: -x[1])]
```

**Decision:** rank fusion (RRF), not score fusion. **Why:** dense cosine and sparse `ts_rank` are on
different, untuned scales — RRF needs no normalization and survives the two retrievers disagreeing about
scale (`pipeline.md §4.3`). **Alternative rejected:** weighted score sum — rejected because the weight
becomes a tunable hyperparameter with no principled default, exactly the kind of knob the pipeline avoids.

```python
# retrieval/rerank.py — deterministic, cacheable, NOT a call site
from sentence_transformers import CrossEncoder
from functools import lru_cache

_model = CrossEncoder("BAAI/bge-reranker-base")

@lru_cache(maxsize=10_000)
def _score(query: str, chunk_id: str, text: str) -> float:
    return float(_model.predict([(query, text)])[0])

def _rerank(chunks: list[Chunk], query: str) -> list[Chunk]:
    scored = [(c, _score(query, c.chunk_id, c.text)) for c in chunks]
    return [c for c, _ in sorted(scored, key=lambda x: -x[1])]
```

Self-hosted cross-encoder, not a vendor rerank API — keeps rerank cost-per-call at zero marginal cost and
avoids a third external dependency on the query path.

---

## 3. Repair — Exercised, Not Just Wired

```python
# orchestration/llm.py
def call_repair(claims: list["ClaimDraft"], context: "RetrievedContext") -> list["ClaimDraft"]:
    rejected = [c for c in claims if c.chunk_id is None or c.chunk_id not in
                {ch.chunk_id for ch in context.chunks}]
    if not rejected:
        return claims
    # single bounded call — same evidence, corrected tags only
    repaired = llm_client.generate_structured(
        system=REPAIR_PROMPT,
        input={"rejected_claims": rejected, "available_chunks": context.chunks},
        response_model=list[ClaimDraft],
    )
    fixed_by_text = {c.text: c for c in repaired}
    return [fixed_by_text.get(c.text, c) for c in claims]
```

**Step 3 test requirement:** deliberately inject a fabricated `chunk_id` in a fixture run, confirm Repair
fires exactly once, confirm a second injected failure returns `insufficient_grounding` rather than a
second repair attempt (bounded, per `pipeline.md §5.3`).

---

## 4. Quality Checkpoint — Deterministic Gate

```python
# domain/quality.py
class QualityCheckpoint(BaseModel):
    all_sections_filled: bool
    competitor_count_ok: bool
    personas_grounded: bool
    findings_lead_to_recommendations: bool

    @property
    def passed(self) -> bool:
        return all([self.all_sections_filled, self.competitor_count_ok,
                    self.personas_grounded, self.findings_lead_to_recommendations])

def evaluate_checkpoint(doc: "MarketResearchDocument") -> QualityCheckpoint:
    filled = all(s.status in ("verified", "insufficient_evidence") for s in doc.sections.values())
    competitors_ok = len(doc.sections.get("competitor_analysis").claims or []) >= 3 \
        if doc.sections.get("competitor_analysis").status == "verified" else False
    personas_ok = all(p.pain_points and p.interests for p in doc.personas) if doc.personas else False
    takeaway_chunk_ids = {c.chunk_id for c in doc.sections["key_takeaways"].claims}
    prior_chunk_ids = {c.chunk_id for sid in doc.sections if sid != "key_takeaways"
                        for c in doc.sections[sid].claims}
    findings_ok = bool(takeaway_chunk_ids & prior_chunk_ids)
    return QualityCheckpoint(
        all_sections_filled=filled, competitor_count_ok=competitors_ok,
        personas_grounded=personas_ok, findings_lead_to_recommendations=findings_ok,
    )
```

This operationalizes SOP-1's own checkpoints (§ "Quality checkpoints" in `SOP_1_Market_Research.txt`) as
code — **no LLM judges "findings lead to recommendations,"** it's a set-intersection over `chunk_id`s
already resolved by Verify. Competitor-count and section-fill are deferred honestly if Core-dependent
sections aren't live yet — `competitor_count_ok` only applies once §6 is `verified`, not `insufficient_evidence`.

---

## 5. Annotate → Approve → Distribute (SOP steps 12–13)

```python
# domain/review.py
class StrategicNote(BaseModel):
    deliverable_id: str
    section: str
    text: str
    author: Literal["team_lead"]
    created_at: datetime

class ApprovalDecision(BaseModel):
    deliverable_id: str
    approver_id: str
    decision: Literal["approved", "rejected"]
    note: str | None = None

class DistributionRecord(BaseModel):
    deliverable_id: str
    internal: bool
    client: bool
    distributed_at: datetime
```

```python
# api/routes.py additions
@app.post("/deliverables/{id}/notes")
async def add_note(id: str, note: StrategicNote):
    return save_note(note)

@app.post("/deliverables/{id}/approve")
async def approve(id: str, decision: ApprovalDecision):
    doc = get_deliverable(id)
    checkpoint = evaluate_checkpoint(doc)
    if decision.decision == "approved" and not checkpoint.passed:
        raise HTTPException(422, detail={"reason": "quality_checkpoint_failed", "checkpoint": checkpoint})
    return apply_decision(id, decision)   # server-side gate — cannot be bypassed by the UI

@app.post("/deliverables/{id}/distribute")
async def distribute(id: str, record: DistributionRecord):
    doc = get_deliverable(id)
    if doc.status != "approved":
        raise HTTPException(422, detail="cannot distribute before approval")
    return save_distribution(record)
```

**The gate is enforced in the endpoint, not the frontend** — the 422 on a failed checkpoint is the actual
control; the FE's disabled button is UX convenience, not the security boundary.

---

## 6. Postgres — Additions

```sql
CREATE TABLE strategic_note (
    id TEXT PRIMARY KEY, deliverable_id TEXT NOT NULL, section TEXT NOT NULL,
    text TEXT NOT NULL, author TEXT NOT NULL, created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE approval_gate (
    deliverable_id TEXT PRIMARY KEY, approver_id TEXT, decision TEXT,
    note TEXT, checkpoint JSONB NOT NULL, decided_at TIMESTAMPTZ
);

CREATE TABLE distribution_record (
    deliverable_id TEXT PRIMARY KEY, internal BOOLEAN, client BOOLEAN, distributed_at TIMESTAMPTZ
);

-- rerank cache table (avoids re-scoring identical query/chunk pairs across runs)
CREATE TABLE rerank_cache (
    query_hash TEXT, chunk_id TEXT, score FLOAT, PRIMARY KEY (query_hash, chunk_id)
);
```

---

## 7. Frontend — Review, Annotate, Approve, Distribute

```
app/deliverables/[id]/
├── page.tsx              # per-section claims, verified/rejected badges, quality checkpoint panel
├── annotate/page.tsx     # Team Lead inline notes per section
└── distribute/page.tsx   # internal/client toggle, only enabled post-approval
```

```tsx
// components/QualityCheckpointPanel.tsx
export function QualityCheckpointPanel({ checkpoint }: { checkpoint: QualityCheckpoint }) {
  const rows = [
    ['All sections filled', checkpoint.all_sections_filled],
    ['At least 3 competitors analysed', checkpoint.competitor_count_ok],
    ['Personas grounded in real signals', checkpoint.personas_grounded],
    ['Findings lead to recommendations', checkpoint.findings_lead_to_recommendations],
  ] as const;
  return (
    <div className="border rounded-lg p-4">
      {rows.map(([label, ok]) => (
        <div key={label} className="flex justify-between py-1">
          <span>{label}</span><span>{ok ? '✓' : '—'}</span>
        </div>
      ))}
      <ApproveButton disabled={!checkpoint.passed} />
    </div>
  );
}
```

The panel mirrors SOP-1's printed quality checkpoints verbatim — a Team Lead reviewing the document sees
the same checklist the SOP already asks them to apply manually, now computed rather than eyeballed.

---

## 8. Infra — Observability Introduced

```python
# infra/telemetry.py
from opentelemetry import trace
from prometheus_fastapi_instrumentator import Instrumentator

tracer = trace.get_tracer("smm-agent")
Instrumentator().instrument(app).expose(app)

def traced_call_site(name: str):
    def decorator(fn):
        def wrapper(*a, **kw):
            with tracer.start_as_current_span(f"gen_ai.{name}"):
                return fn(*a, **kw)
        return wrapper
    return decorator
```

Applied to `call_plan`, `call_synthesize`, `call_repair` — the three call sites now emit real spans.
The one metric worth tracking from Step 3 onward: **citation rejection rate, per section** — §1/§3/§4
(brand-only, hybrid+reranked) becomes the baseline; when Core-backed sections go live in Step 4, this
metric is what tells you whether BRIDGE retrieval is actually working, not a guess.

---

## 9. Step 3 Acceptance Tests

```python
def test_hybrid_beats_dense_only_on_recall():
    dense_only = search_dense("run:brand-x", plan)
    hybrid = search_hybrid("run:brand-x", plan)
    assert recall_at_k(hybrid, golden_set) >= recall_at_k(dense_only, golden_set)

def test_repair_fires_exactly_once_then_stops():
    inject_two_consecutive_fabrications()
    result = run_pipeline("brand-x")
    assert result.deliverable.call_site_trace["repair"] == 1
    assert result.deliverable.status == "insufficient_grounding"

def test_approval_blocked_by_failed_checkpoint():
    doc = incomplete_document()  # < 3 competitors
    resp = client.post(f"/deliverables/{doc.id}/approve", json={"decision": "approved", ...})
    assert resp.status_code == 422

def test_distribution_blocked_before_approval():
    doc = pending_document()
    resp = client.post(f"/deliverables/{doc.id}/distribute", json={"internal": True, "client": False})
    assert resp.status_code == 422

def test_rerank_cache_hit_avoids_recompute(monkeypatch):
    search_hybrid("run:brand-x", plan)
    calls_before = count_rerank_model_calls()
    search_hybrid("run:brand-x", plan)  # same query
    assert count_rerank_model_calls() == calls_before  # cache hit, no new inference
```

---

## Remaining Roadmap (Steps 4–9, not yet built)

| Step | Scope |
|---|---|
| 4 | Market Intel Core builder — curated corpus, eval gate, promotion workflow; unblocks §5/§6/§9/§10 |
| 5 | BRIDGE topology + live competitor/site crawl tools (`httpx` async fetchers) |
| 6 | Multi-tenant grant enforcement (Postgres role-scoped), TTL sweep, second brand onboarded |
| 7 | Client-facing reduced-projection view, distribution to client channel |
| 8 | Load testing, cost budgets per call site, rate limiting, security review (prompt-injection defense on brand uploads) |
| 9 | CI/CD, staged deploy, production monitoring dashboards on the six `pipeline.md §6` metrics |
