# Step 4 — Evidence Expansion: Market Intel Core, Eval Gate, BRIDGE, Live Data

## Directive

**`core_kb_available()` in `orchestration/section_runner.py` currently returns a hardcoded `False` — the
honest Step 2 answer, not a stub. This step's entire job is to earn the right to flip it to `True`, and to
do the same for the `bridge` retrieval mode that falls into the same `insufficient_evidence` branch today.**
Nothing in this step touches Brand Workspace, retrieval hardening, or the approval flow — those are proven.
This step only adds a second, separately-deployed evidence source and the fan-out logic to use it.

## Core Concepts

| Concept | Principle |
|---|---|
| Second pipeline, not a fork | Core builder reuses `ingestion/router.py` + `ingestion/validators.py` (C1–C8) unchanged — only the `ChunkConfig` profile differs (L0–L3 vs. Brand Workspace's L0/L1), per `dual-kb.md`'s "same code, different config" |
| Promotion is a human decision, not a passing test | The eval gate is necessary, not sufficient — a passing corpus still requires an explicit `/decide` call |
| Immutability | Promoted `kb_id`s are never mutated; a new version is a new `kb_id`, old runs replay against what they were pinned to |
| Bridge relation stated before code | Per `CLAUDE.md`'s own instruction: *"for each `<run unit>`, find the `<core unit>` that `<relation>`"* — write this sentence first for §6 and §9 separately, since they're different relations |
| Fan-out is bounded, not hoped-for | `dual-kb.md §10` names BRIDGE cost an open problem — Step 4 answers it with a fixed, measured cap, not an algorithm |
| Live fetch is a controlled tool | External HTTP calls get the same typed-interface treatment as everything else — never inline `httpx` calls scattered through ingestion code |

---

## 0. Gate — Ship Before Any Real Brand Touches This Step

**Gap analysis finding (read as an agency operator, not just an architect): `brand_id` today is free text
typed into a form, unauthenticated, unowned.** Everything this step adds — a shared Core corpus, live
competitor crawling, cross-brand benchmark matching — makes a real client's data more valuable to protect
and more automated in how it's touched. Building Market Intel Core on top of an open trust boundary means
the very first BRIDGE query is the first real exposure of one client's competitive data to whoever else
knows the brand slug. **This gate lands first, as its own small PR, before the rest of this step begins.**

It is deliberately a *minimal* version of Step 5 Part A's full Postgres RLS — the complete defense-in-depth
layer stays scheduled in Step 5. This is the app-layer check that closes the hole today without waiting six
steps:

```sql
CREATE TABLE brand (
    id TEXT PRIMARY KEY, owner_org_id TEXT NOT NULL, created_by TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE TABLE brand_grant (
    api_key_id TEXT NOT NULL, brand_id TEXT REFERENCES brand(id),
    PRIMARY KEY (api_key_id, brand_id)
);
```

```python
# api/deps.py — every brand-scoped route in this codebase adds this dependency now
async def resolve_brand_scope(brand_id: str = Path(...), api_key: str = Header(...)) -> str:
    grant = lookup_api_key_grant(api_key)
    if grant is None or not brand_grant_exists(api_key_id=grant.id, brand_id=brand_id):
        raise HTTPException(403, detail="not authorized for this brand")
    return f"run:{brand_id}"
```

Paired with a minimal real identity — the "Team Lead" persona this whole system is built to serve is
currently a hardcoded string, which means every `approval_gate`/`strategic_note` record produced by Steps
1–3 has no real author behind it:

```python
# domain/user.py
class User(BaseModel):
    id: str
    email: str
    role: Literal["team_lead", "smm", "graphic_designer", "admin"]

# api/routes.py — approver_id and note author now come from the session, never the request body
@app.post("/deliverables/{id}/approve")
async def approve(id: str, decision: Literal["approved", "rejected"],
                   note: str | None = None, user: User = Depends(current_user)):
    return apply_decision(id, approver_id=user.id, decision=decision, note=note)
```

**Frontend — `app/page.tsx`'s free-text brand field is replaced, not validated harder:**

```tsx
export default function Home() {
  const { data: myBrands } = useQuery({ queryKey: ['my-brands'], queryFn: () => api.get('/brands') });
  return <BrandList brands={myBrands} onCreateNew={openOnboardingFlow} />;
}
```

Once this gate merges, Step 4's Market Intel Core work below proceeds exactly as designed — it now
inherits a real trust boundary instead of building shared-evidence infrastructure on top of an open one.

---

## 1. Backend — Market Intel Core Builder

**New module `backend/app/domain/kb_version.py`:**

```python
from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class EvalGateResult(BaseModel):
    citation_rejection_rate: float
    degraded_ratio: float
    l0_ratio: float
    coverage_ok: bool
    passed: bool
    thresholds: dict[str, float]


class KBVersion(BaseModel):
    kb_id: str  # "core:market-intel@v1"
    version: int
    status: Literal["staging", "promoted", "rejected"]
    eval_gate_result: EvalGateResult | None = None
    promoted_at: datetime | None = None
    promoted_by: str | None = None
```

**Extend `ingestion/router.py`'s ladder to L0–L3 for Core profile** (Brand Workspace stays L0/L1 —
same function, a `ladder` parameter selects the ceiling):

```python
# ingestion/router.py — signature grows, Step 2's callers pass ladder="L0-L1" explicitly
def route_and_chunk(doc_id: str, kb_id: str, blocks: list["Block"], ladder: str = "L0-L1",
                     force_l0: bool = False) -> list["Chunk"]:
    ceiling = {"L0-L1": 1, "L0-L3": 3}[ladder]
    ...  # existing per-block strategy selection, capped at `ceiling` instead of hardcoded L1
```

**New `backend/app/ingestion/core_builder.py`:**

```python
from app.ingestion.router import route_and_chunk
from app.ingestion.validators import validate_batch


def build_staging_batch(source_paths: list[str], target_version: int) -> list["Chunk"]:
    staging_kb_id = f"core:market-intel@v{target_version}:staging"
    chunks: list["Chunk"] = []
    for path in source_paths:
        blocks = parse_and_classify(path)  # doc-understanding call, cached -- ingest-time exempt (P2)
        batch = route_and_chunk(doc_id(path), staging_kb_id, blocks, ladder="L0-L3")
        if not all(r.passed for r in validate_batch(batch)):
            batch = route_and_chunk(doc_id(path), staging_kb_id, blocks, ladder="L0-L3", force_l0=True)  # C6
        chunks.extend(batch)
    return chunks
```

**New `backend/app/workers/core_ingest.py`** — separate Celery queue, deliberately not sharing
`workers/ingest.py`'s queue (Brand ingest is latency-bound; Core builds run for hours):

```python
from app.infra.celery_app import celery_app


@celery_app.task(name="app.workers.core_ingest.build_staging", queue="core")
def build_staging(source_paths: list[str], target_version: int) -> str:
    from app.ingestion.core_builder import build_staging_batch
    from app.infra.embeddings import embed
    from app.infra.db import get_session

    chunks = build_staging_batch(source_paths, target_version)
    with get_session() as session:
        for c in chunks:
            store_chunk(session, c, embed(c.text))
        session.execute(
            "INSERT INTO kb_version (kb_id, version, status) VALUES (:kb, :v, 'staging')",
            {"kb": f"core:market-intel@v{target_version}:staging", "v": target_version},
        )
        session.commit()
    return f"staged v{target_version}: {len(chunks)} chunks"
```

**New `backend/app/eval/gate.py`** — zero LLM calls, arithmetic over already-verified data:

```python
THRESHOLDS = {"max_citation_rejection_rate": 0.08, "max_degraded_ratio": 0.05, "max_l0_ratio": 0.15}


def evaluate_staging(staging_kb_id: str, golden_set: list["GoldenCase"]) -> "EvalGateResult":
    chunks = load_chunks(staging_kb_id)
    degraded_ratio = sum(c.degraded for c in chunks) / max(len(chunks), 1)
    l0_ratio = sum(c.strategy == "L0" for c in chunks) / max(len(chunks), 1)
    rejections, total = 0, 0
    for case in golden_set:
        result = run_synthesis_against(case, staging_kb_id)
        total += len(result.claims)
        rejections += sum(not c.verified for c in result.claims)
    citation_rejection_rate = rejections / max(total, 1)
    coverage_ok = _coverage_check(chunks, golden_set)
    passed = (
        citation_rejection_rate <= THRESHOLDS["max_citation_rejection_rate"]
        and degraded_ratio <= THRESHOLDS["max_degraded_ratio"]
        and l0_ratio <= THRESHOLDS["max_l0_ratio"]
        and coverage_ok
    )
    return EvalGateResult(citation_rejection_rate=citation_rejection_rate, degraded_ratio=degraded_ratio,
                           l0_ratio=l0_ratio, coverage_ok=coverage_ok, passed=passed, thresholds=THRESHOLDS)
```

**Gap analysis finding — verify the reranker before trusting what it gates.** `retrieval/rerank.py`'s
`BAAI/bge-reranker-base` integration is correctly architected (lazy load, disabled-by-default in tests, HF
cache volume) but was never exercised end-to-end as of Step 3. `citation_rejection_rate` above is computed
over reranked results — an eval gate resting on an unverified reranker is measuring the wrong thing, and
could pass a corpus it shouldn't. Run this once, deliberately, before the first real promotion request in
this step:

```python
# tests/retrieval/test_rerank.py
@pytest.mark.integration
@pytest.mark.slow
def test_rerank_with_real_model():
    """Pulls the real BAAI/bge-reranker-base, asserts real score ordering on a fixed
    fixture pair. Not part of per-commit CI (Step 6 schedules it nightly) -- but run
    at least once, manually, before this step's first promotion request."""
    pairs = search_hybrid("run:fixture-brand", fixture_plan)
    assert pairs[0].text == EXPECTED_TOP_MATCH  # a case where rerank order should differ from RRF alone
```

**`api/routes.py` additions** — promotion is a distinct endpoint from evaluation, and `/decide` is a
distinct endpoint from the promotion *request*, so "passed the gate" and "a human said yes" are never the
same HTTP call. `requested_by`/`reviewer` are no longer request fields — they come from the session identity
introduced in §0, the same fix that closes the `approver_id` gap on the deliverable side:

```python
@app.post("/core/staging/{version}/promotion-requests")
async def create_promotion_request(version: int, source_summary: str, user: User = Depends(current_user)):
    result = evaluate_staging(f"core:market-intel@v{version}:staging", load_golden_set())
    if not result.passed:
        raise HTTPException(422, detail={"reason": "eval_gate_failed", "result": result.model_dump()})
    return save_promotion_request(requested_by=user.id, source_summary=source_summary, ...)

@app.post("/core/promotion-requests/{id}/decide")
async def decide_promotion(id: str, decision: Literal["approved", "rejected"], user: User = Depends(current_user)):
    if decision == "rejected":
        return update_promotion_request(id, status="rejected", reviewed_by=user.id)
    with get_session() as session:  # atomic rename staging -> promoted; old promoted version untouched
        session.execute("UPDATE chunk SET kb_id = :new WHERE kb_id = :old", {...})
        session.execute("UPDATE kb_version SET status='promoted', promoted_by=:by WHERE kb_id=:old", {"by": user.id, ...})
        session.commit()
    return {"promoted": True}
```

---

## 2. Backend — BRIDGE + Live Tools

**Bridge relation, stated first (per `CLAUDE.md`'s own rule):**

- §6 Competitor analysis: *for each **run chunk describing a brand-observed competitor signal**, find the
  **core chunk** that **benchmarks the same metric for the same or comparable competitor.***
- §9 Platform analysis: *for each **run chunk reporting the brand's own platform performance**, find the
  **core chunk** that **states category-norm cadence/engagement for that platform.***

**New `backend/app/tools/web.py`** — the first controlled external-world tool:

```python
from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, wait_exponential
import httpx


class FetchResult(BaseModel):
    url: str
    status: int
    text: str | None
    failed_reason: str | None = None


class WebTool:
    def __init__(self, timeout: float = 10.0):
        self._client = httpx.AsyncClient(timeout=timeout)

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(min=1, max=4))
    async def fetch(self, url: str) -> FetchResult:
        try:
            resp = await self._client.get(url, headers={"User-Agent": "smm-agent-research/1.0"})
            return FetchResult(url=url, status=resp.status_code, text=resp.text)
        except httpx.HTTPError as e:
            return FetchResult(url=url, status=0, text=None, failed_reason=str(e))  # degrade, never raise (P5)
```

**New `backend/app/retrieval/bridge.py`:**

```python
from pydantic import BaseModel


class BridgeBudget(BaseModel):
    max_run_chunks: int = 20
    max_core_matches_per_chunk: int = 3
    max_total_pairs: int = 60  # dual-kb.md §10's "measure first" answer -- fixed, instrumented, not open-ended


class BridgePair(BaseModel):
    run_chunk: "Chunk"
    core_chunk: "Chunk"


def search_bridge(brand_kb_id: str, core_kb_id: str, plan: "RetrievalPlan",
                   budget: BridgeBudget = BridgeBudget()) -> list[BridgePair]:
    run_chunks = search_dense(brand_kb_id, plan)[: budget.max_run_chunks]
    pairs: list[BridgePair] = []
    for rc in run_chunks:
        for cm in search_dense(core_kb_id, RetrievalPlan(sub_queries=[rc.text],
                                                          k_per_query=budget.max_core_matches_per_chunk)):
            pairs.append(BridgePair(run_chunk=rc, core_chunk=cm))
        if len(pairs) >= budget.max_total_pairs:
            break
    with tracer.start_as_current_span("bridge.fanout") as span:
        span.set_attribute("pair_count", len(pairs))
    return pairs
```

`domain/claim.py`'s `ClaimDraft` gains `supporting_chunk_id: str | None = None` for the Core half of a
bridge pair; `domain/verify.py` extends to require both IDs resolve when it's set.

**`orchestration/section_runner.py` — the actual integration point:**

```python
def core_kb_available() -> bool:
    return get_active_core_version() is not None  # was: hardcoded False


def run_section(brand_id: str, spec: SectionSpec, prior: dict[str, SectionResult]) -> SectionResult:
    ...  # direct_input, requires_core-and-unavailable branches unchanged
    if spec.retrieval_mode == "core_only":
        from app.orchestration.core_only import run_core_only
        return run_core_only(brand_id, spec)
    if spec.retrieval_mode == "bridge":
        from app.orchestration.bridge_runner import run_bridge
        return run_bridge(brand_id, spec)
    ...  # synthesis_only, union unchanged
```

No other file in Step 1–3's proven path changes — §1/§3/§4 and the synthesis-only sections don't know or
care that Core now exists.

---

## 3. Frontend — Core Console (distinct app surface from the brand wizard)

```
frontend/app/core-kb/
├── page.tsx                    # version list, staging/promoted/rejected, eval scores
├── build/page.tsx              # trigger a build against curated source files
└── promotion/[id]/page.tsx     # EvalGatePanel + approve/reject
```

```tsx
// components/EvalGatePanel.tsx
export function EvalGatePanel({ result }: { result: EvalGateResult }) {
  const rows = [
    ['Citation rejection', result.citation_rejection_rate, result.thresholds.max_citation_rejection_rate],
    ['Degraded ratio', result.degraded_ratio, result.thresholds.max_degraded_ratio],
    ['L0 fallback ratio', result.l0_ratio, result.thresholds.max_l0_ratio],
  ] as const;
  return (
    <div className="border rounded-lg p-4">
      {rows.map(([label, v, t]) => (
        <div key={label} className="flex justify-between py-1">
          <span>{label}</span>
          <span className={v <= t ? 'text-green-600' : 'text-red-600'}>{(v * 100).toFixed(1)}%</span>
        </div>
      ))}
      <div className="mt-2 font-bold">{result.passed ? 'Eligible for promotion' : 'Blocked'}</div>
    </div>
  );
}
```

```tsx
// components/BridgePairCard.tsx — extends the existing ClaimCard family for two-source claims
export function BridgePairCard({ pair, claim }: { pair: BridgePair; claim?: VerifiedClaim }) {
  return (
    <div className="border rounded-lg p-4">
      <p className="text-xs text-gray-400">Observed (brand data)</p>
      <p className="mb-3">{pair.run_chunk.text}</p>
      <p className="text-xs text-gray-400">Market Intel Core benchmark</p>
      <p className="mb-3">{pair.core_chunk.text}</p>
      {claim && <ClaimCard claim={claim} />}
    </div>
  );
}
```

`SectionRow.tsx` (already built in Step 2) needs no change — it already renders whatever `SectionStatusBadge`
the API returns; `insufficient_evidence` → `verified` for §5/§6/§9/§10 is a data change, not a UI change.

---

## 4. Infra

```yaml
# infra/docker-compose.yml additions
  worker-core:
    build: ./backend
    command: celery -A app.workers worker -Q core --loglevel=info --concurrency=2 --time-limit=3600
    depends_on: [postgres, redis]
  worker-crawl:
    build: ./backend
    command: celery -A app.workers worker -Q crawl --loglevel=info --concurrency=8
    depends_on: [postgres, redis]
    environment: { CRAWL_RATE_LIMIT_PER_HOST: "5" }
```

```sql
-- alembic/versions/0002_market_intel_core.py
CREATE TABLE kb_version (
    kb_id TEXT PRIMARY KEY, version INT NOT NULL, status TEXT NOT NULL,
    eval_gate_result JSONB, promoted_at TIMESTAMPTZ, promoted_by TEXT
);
CREATE TABLE promotion_request (
    id TEXT PRIMARY KEY, kb_id TEXT NOT NULL, source_summary TEXT, requested_by TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending', reviewed_by TEXT, reviewed_at TIMESTAMPTZ
);
CREATE TABLE golden_case (
    id TEXT PRIMARY KEY, topic TEXT NOT NULL, section TEXT NOT NULL, fixture_chunks JSONB NOT NULL
);
CREATE TABLE core_competitor_registry (
    competitor_id TEXT PRIMARY KEY, industry_tag TEXT NOT NULL, name TEXT NOT NULL, homepage_url TEXT NOT NULL
);
ALTER TABLE chunk ADD COLUMN strategy TEXT DEFAULT 'L1';
ALTER TABLE claim ADD COLUMN supporting_chunk_id TEXT;
```

---

## 5. Acceptance Tests

**§0's gate is tested first, and blocks the rest of this suite conceptually even though pytest runs them
in file order** — a promotion or bridge test running against an unscoped `brand_id` would be validating the
wrong system.

```python
def test_promotion_requires_authenticated_scoped_user():
    resp = client.post("/core/staging/1/promotion-requests", json={"source_summary": "..."})  # no api-key
    assert resp.status_code in (401, 403)

def test_eval_gate_blocks_bad_corpus():
    stage_corpus_with_known_bad_ocr_pages()
    assert not evaluate_staging("core:market-intel@v1:staging", golden_set()).passed

def test_promotion_is_atomic_and_immutable():
    promote_version(1)
    before = count_chunks("core:market-intel@v1")
    stage_and_promote_version(2)
    assert count_chunks("core:market-intel@v1") == before

def test_pinned_run_replays_against_old_version():
    run = run_pipeline("brand-x")
    promote_version(2)
    assert replay_pipeline(run.run_manifest).deliverable.claims == run.deliverable.claims

def test_core_only_and_bridge_sections_go_live_after_promotion():
    promote_version(1)
    doc = run_all_sections("brand-x")
    for sid in ("market_overview", "trends_opportunities", "competitor_analysis", "platform_analysis"):
        assert doc[sid].status == "verified"

def test_bridge_fanout_respects_budget():
    pairs = search_bridge("run:brand-x", "core:market-intel@v1", plan, BridgeBudget(max_total_pairs=10))
    assert len(pairs) <= 10

def test_failed_competitor_fetch_degrades_not_fails():
    mock_one_competitor_site_unreachable()
    result = run_all_sections("brand-x")
    assert result["competitor_analysis"].status in ("verified", "insufficient_evidence")
```
