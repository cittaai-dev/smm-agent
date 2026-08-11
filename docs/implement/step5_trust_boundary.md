# Step 5 — Trust Boundary: Multi-Tenant Isolation + Live Data Ingestion + Client Distribution

## Directive

**Every step so far ran one brand at a time under one operator's implicit trust. This step is where the
system meets three trust boundaries simultaneously:** isolation (brand ↔ brand), live data sources (market ↔
market), and distribution (internal ↔ client). All three are one problem: "who is this data allowed to
reach?" The `ClientView` projection is what confinement looks like for external audiences. Competitor
discovery and API authentication are what confinement looks like for *data*: an agent discovering YouTube
channels must never scrape outside its authorized market segment, and API credentials must never expose a
second brand's data through a failed rate-limit check. A fourth face joins here too: an agency's Team Lead
needs to trust that a rejection, approval, or share is a real, attributable, undiscardable event — decision
integrity applies equally to live data collection events (the `/live-run/:brand_id/status` feed) as to
approval checkpoints.

**Sequencing note:** Step 4 §0 already shipped the minimal app-layer version of tenant isolation
(`resolve_brand_scope`, `current_user`) before Market Intel Core work began — real client data was never
exposed to an open trust boundary in the interim. **Part A below is the defense-in-depth layer, not the
first closure** — Postgres RLS so that a bug in some future endpoint can't leak data even if that endpoint
forgets the app-layer check. Build Part A expecting `brand_grant`/`User` to already exist.

## Core Concepts

| Concept | Principle |
|---|---|
| Defense-in-depth, not the first line of defense | Confinement is DB-enforced *in addition to* application-filtered — Step 4 §0 closed the app layer; RLS here means one missed filter in future code still can't leak data |
| A URL parameter is not authorization | Was true through Step 4 §0's fix — Part A extends the same principle from "the API rejects it" to "the database physically cannot return it" |
| Data source auth is brand-scoped, never global | API credentials (Google Trends key, NewsAPI key, YouTube key) are per-brand, stored encrypted. A leaked key exposes only one brand's data collection, not all brands. Rate limits apply per key per source. |
| Competitor scope is explicit, not inferred | Competitor discovery (YouTube channels, news sites, Reddit communities) is confined to an explicit market segment whitelist per brand — never open-ended crawling. Crawler respects robots.txt and rate-limit headers. |
| A client link is not an operator credential | `DistributionLink` authorizes exactly one deliverable's read-only projection, nothing else in the system |
| Projection, not a second write path | `ClientView` is computed at request time from the approved `MarketResearchDocument` — it can never drift out of sync because there's only one source of truth |
| Data freshness is explicit, staleness is visible | Every collected datum carries `collected_at` and `valid_until` timestamps. Client-facing results show data age ("Instagram data: 2 hours old"). If Core KB data is >24h old, synthesis degrades with `reason="data_staleness"`, not silent hallucination. |
| Existence must not leak | 404, not 403, for anything a caller isn't authorized to know exists at all — applies to brands, client links, and competitor scopes alike |
| History is append-only, same discipline as claims | `approval_gate`/`distribution_record` overwriting by `document_id` violates the same P7 confidence-travels-with-the-artifact rule that claims and checkpoints already honor correctly — Part C brings decisions up to that standard. Data collection events (`collection_job_status`) follow the same append-only pattern. |

---

## Part A — Multi-Tenant Isolation

### 1. Postgres Row-Level Security

```sql
-- alembic/versions/0003_multitenant_rls.py
CREATE ROLE brand_workspace_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON chunk, document_registry, source_file TO brand_workspace_role;

ALTER TABLE chunk ENABLE ROW LEVEL SECURITY;
CREATE POLICY chunk_kb_isolation ON chunk
  USING (kb_id = current_setting('app.current_kb_id', true) OR kb_id LIKE 'core:%');

ALTER TABLE document_registry ENABLE ROW LEVEL SECURITY;
CREATE POLICY doc_registry_kb_isolation ON document_registry
  USING (kb_id = current_setting('app.current_kb_id', true) OR kb_id LIKE 'core:%');
```

```python
# infra/db.py — every session declares its scope before any query runs
from contextlib import contextmanager

@contextmanager
def get_session(kb_id: str | None = None):
    session = SessionLocal()
    try:
        if kb_id:
            session.execute("SET LOCAL app.current_kb_id = :kb", {"kb": kb_id})
        yield session
    finally:
        session.close()
```

Every call site touched since Step 1 — `retrieval/dense.py`, `retrieval/hybrid.py`, `workers/ingest.py` —
now passes `kb_id` into `get_session`. This is a mechanical, repo-wide change; grep for `get_session()` with
no argument and that's the worklist.

**Decision:** RLS, not per-brand Postgres schemas. **Why:** `dual-kb.md §5` already ruled against a second
store; RLS gets the isolation guarantee without fragmenting the schema Step 1–4 built. **Alternative
rejected:** application-layer filtering alone — already in place since Step 1, demonstrably insufficient on
its own (it's exactly the class of bug the `content_hash` dedup issue turned out to be).

### 2. API-Layer Brand Scoping

```python
# api/deps.py
async def resolve_brand_scope(brand_id: str = Path(...), api_key: str = Header(...)) -> str:
    grant = lookup_api_key_grant(api_key)
    if grant is None or brand_id not in grant.authorized_brand_ids:
        raise HTTPException(403, detail="not authorized for this brand")
    return f"run:{brand_id}"

@app.post("/brands/{brand_id}/research/run")
async def run_research(kb_id: str = Depends(resolve_brand_scope)) -> Deliverable:
    return run_pipeline(kb_id=kb_id)
```

### 3. TTL Sweep

```python
# workers/ttl_sweep.py
@celery_app.task(name="app.workers.ttl_sweep.sweep_expired_run_data")
def sweep_expired_run_data() -> str:
    with get_session() as session:  # unscoped -- legitimately spans all brands
        expired = session.execute(
            "SELECT file_id FROM source_file WHERE ttl_expires_at < now() AND status != 'deleted'"
        ).mappings().all()
        for row in expired:
            session.execute("DELETE FROM chunk WHERE doc_id IN "
                             "(SELECT doc_id FROM document_registry WHERE source_uri = :uri)", row)
            session.execute("UPDATE source_file SET status='deleted' WHERE file_id=:file_id", row)
        session.commit()
    return f"swept {len(expired)}"

celery_app.conf.beat_schedule = {
    "ttl-sweep-nightly": {"task": "app.workers.ttl_sweep.sweep_expired_run_data",
                           "schedule": crontab(hour=3, minute=0)},
}
```

`core:*` is structurally exempt — `source_file` is populated only by Brand Workspace ingest (`workers/
ingest.py`); Core builder (Step 4) never writes to it. No `WHERE kb_id NOT LIKE` clause to forget.

### 4. Security Test Suite — This Half's Actual Deliverable

```python
# tests/security/test_cross_brand_isolation.py
def test_rls_blocks_explicit_cross_brand_query():
    ingest_and_promote("brand-a", "secret.pdf")
    with get_session(kb_id="run:brand-b") as session:
        assert session.execute("SELECT * FROM chunk WHERE kb_id LIKE 'run:brand-a%'").fetchall() == []

def test_api_rejects_unauthorized_brand():
    key = issue_test_key(["brand-a"])
    assert client.post("/brands/brand-b/research/run", headers={"api-key": key}).status_code == 403

def test_error_and_timing_do_not_leak_existence():
    r1 = client.get("/brands/nonexistent/deliverable", headers=auth_for("brand-a"))
    r2 = client.get("/brands/brand-b/deliverable", headers=auth_for("brand-a"))  # exists, unauthorized
    assert r1.json()["detail"] == r2.json()["detail"]

def test_ttl_sweep_never_touches_core():
    promote_version(1)
    before = count_chunks("core:market-intel@v1")
    expire_all_run_data(); sweep_expired_run_data()
    assert count_chunks("core:market-intel@v1") == before
```

---

## Part D — Live Data Ingestion Trust Boundary

### 4. Data Source Authentication (Per-Brand, Encrypted)

```python
# domain/data_source.py
class DataSourceCredential(BaseModel):
    brand_id: str
    source: Literal["google_trends", "newsapi", "youtube", "scrapy_competitor"]
    api_key: str  # encrypted at rest, via Fernet(ENCRYPTION_KEY)
    rate_limit_per_hour: int = 60
    created_at: datetime
    last_used_at: datetime | None = None

# api/deps.py — fetch and decrypt credentials scoped to authenticated brand
async def get_data_source_credential(brand_id: str, source: str) -> DataSourceCredential:
    grant = lookup_api_key_grant(api_key)
    if brand_id not in grant.authorized_brand_ids:
        raise HTTPException(403, detail="not authorized for this brand")
    cred = session.execute(
        "SELECT * FROM data_source_credential WHERE brand_id=:bid AND source=:src",
        {"bid": brand_id, "src": source}
    ).one_or_none()
    if cred is None:
        raise HTTPException(404, detail="data source not configured")
    return DataSourceCredential(**cred)
```

**Design:** Each brand supplies credentials once (via UI form), encrypted with AES-GCM, stored in Postgres.
Celery workers fetch credentials at task time, decrypt in-memory, use immediately, never persist decrypted
values. Rotating credentials is a one-click operation: new key, old key revoked, pending jobs retry with new
key.

### 5. Competitor Scope Confinement

```python
# domain/market_segment.py
class MarketSegment(BaseModel):
    brand_id: str
    segment_name: str
    # Explicit whitelist of where to look
    youtube_channel_keywords: list[str]    # e.g., ["vegan fitness", "plant-based wellness"]
    news_sources: list[str]                # e.g., ["techcrunch.com", "forbes.com"]
    reddit_communities: list[str]          # e.g., ["r/fitness", "r/vegan"]
    website_urls: list[str]                # e.g., ["competitor-a.com/blog", "competitor-b.com"]
    max_competitors_to_track: int = 10     # hard limit on discovery scope

# workers/discovery.py — constrained competitor search
@celery_app.task(name="app.workers.discovery.discover_competitors")
def discover_competitors(brand_id: str) -> dict:
    """Find new competitors only within the explicitly-approved segment."""
    segment = get_segment(brand_id)
    discovered = []
    
    # YouTube: search within keywords, cap at max_competitors
    for kw in segment.youtube_channel_keywords:
        channels = youtube_api.search_channels(kw, max_results=3)
        discovered.extend([{"source": "youtube", "channel_id": c["id"]} for c in channels])
    
    # News: only index from approved sources
    for source in segment.news_sources:
        articles = news_api.get_latest(domain=source, brand_name=brand_id)
        discovered.extend([{"source": "news", "url": a["url"]} for a in articles])
    
    # Enforce limit
    discovered = discovered[:segment.max_competitors_to_track]
    
    # Store as Competitor entities, linked to segment
    for item in discovered:
        save_competitor(brand_id, item["source"], item)
    
    return {"discovered_count": len(discovered), "segment": segment.segment_name}
```

**Design:** Market segment is set up by human (Team Lead) once per brand. Competitor discovery is confined
to that whitelist — no open-ended web crawling. If a competitor is found outside the segment, it's logged
but ignored.

### 6. Data Freshness TTL + Graceful Degradation

```python
# domain/chunk.py — extend existing Chunk model
class Chunk(BaseModel):
    # ... existing fields ...
    collected_at: datetime | None = None
    valid_until: datetime | None = None  # e.g., collected_at + 24 hours for live data
    data_source: str | None = None       # "native_api" | "data_provider" | "web_crawl" | "manual_upload"

# retrieval/hybrid.py — filter stale data, degrade gracefully
def retrieve_with_freshness_check(query: str, kb_id: str, max_staleness_hours: int = 24) -> RetrievalResult:
    chunks = retrieval.hybrid_search(query, kb_id)
    fresh_chunks, stale_chunks = [], []
    
    for chunk in chunks:
        if chunk.valid_until and chunk.valid_until < datetime.utcnow():
            stale_chunks.append(chunk)
        else:
            fresh_chunks.append(chunk)
    
    if len(fresh_chunks) < MIN_GROUNDING_CHUNKS and len(stale_chunks) > 0:
        # All we have is stale; log and use it, but mark for retry
        return RetrievalResult(
            chunks=stale_chunks,
            freshness_status="degraded_stale_data",
            recommendation="rerun_data_collection"
        )
    
    return RetrievalResult(chunks=fresh_chunks, freshness_status="fresh")

# orchestration/graph.py — route stale data to insufficient_grounding
def route_after_retrieve(result):
    if result.freshness_status == "degraded_stale_data":
        return "synthesize_with_warning"  # (still generates, but flags it)
    if result.chunks_count < MIN_GROUNDING_CHUNKS:
        return "insufficient_grounding"
    return "synthesize"
```

**Design:** Every piece of live-collected data carries timestamps. If synthesis would rely on data older than
24 hours, it degrades to `insufficient_grounding` with `reason="data_staleness"`, triggering an automatic
re-run of the data collection job, not hallucination.

### 7. Rate Limiting per Data Source

```python
# infra/rate_limit.py — extends Part A's existing RateLimitMiddleware
class DataSourceRateLimiter:
    """Per-brand, per-source rate limiting — prevents one brand's high-volume crawl from affecting another."""
    
    def __init__(self, redis_client):
        self._redis = redis_client
    
    def check(self, brand_id: str, source: str) -> bool:
        """Returns True if call is allowed, False if rate limit hit."""
        cred = get_data_source_credential(brand_id, source)
        key = f"ratelimit:{brand_id}:{source}:{int(time.time() // 3600)}"  # per-hour bucket
        count = self._redis.incr(key)
        self._redis.expire(key, 3600)
        return count <= cred.rate_limit_per_hour

# workers/data_collection.py — wrapped at task entry point
@celery_app.task(name="app.workers.data_collection.collect_youtube_data", bind=True)
def collect_youtube_data(self, brand_id: str, max_retries: int = 2):
    limiter = DataSourceRateLimiter(redis_client)
    if not limiter.check(brand_id, "youtube"):
        self.retry(countdown=60, max_retries=max_retries)  # back off 1 min, retry
        return
    
    cred = get_data_source_credential(brand_id, "youtube")
    # ... proceed with API calls using cred.api_key ...
```

**Design:** Rate limiting is per-brand per-source, stored in Redis with 1-hour buckets. If a limit is hit,
the task backs off exponentially and retries — never fails or skips collection.

### 8. Data Collection Error Handling + Logging

```python
# workers/data_collection.py
class DataCollectionError(Exception):
    def __init__(self, source: str, reason: str, retriable: bool = True):
        self.source, self.reason, self.retriable = source, reason, retriable

@celery_app.task(name="app.workers.data_collection.collect_all", bind=True)
def collect_all_for_brand(self, brand_id: str):
    """Orchestrates all data sources for a brand; degrades gracefully if any fail."""
    results = {}
    
    for source in ["youtube", "google_trends", "newsapi", "competitor_sites"]:
        try:
            if source == "youtube":
                results[source] = collect_youtube_data(brand_id)
            elif source == "google_trends":
                results[source] = collect_google_trends(brand_id)
            elif source == "newsapi":
                results[source] = collect_news_mentions(brand_id)
            elif source == "competitor_sites":
                results[source] = crawl_competitor_sites(brand_id)
        except DataCollectionError as e:
            results[source] = {
                "status": "failed" if not e.retriable else "retrying",
                "reason": e.reason,
                "retriable": e.retriable
            }
            # Log but continue — P5 degrade, never fail
            log_data_collection_error(brand_id, source, e.reason, e.retriable)
    
    save_collection_job_result(brand_id, results)
    return results
```

**Design:** If YouTube API fails, continue with news/trends. If all sources fail, log as `insufficient_data`
but don't fail the pipeline. Next synthesis attempt will either use cached data or degrade to
`insufficient_grounding`. No cascading failures.

---

## Part B — Client Distribution

### 9. `ClientView` — Projection, Never a Second Write Path

```python
# domain/client_view.py
class ClientClaim(BaseModel):
    text: str

class ClientMarketResearchView(BaseModel):
    brand_name: str
    prepared_date: str
    sections: dict[str, list[ClientClaim]]
    personas: list["ClientPersona"]
    # deliberately absent: chunk_id, block_span, call_site_trace, rejection_reason, approver_id

def project_for_client(doc: "MarketResearchDocument") -> ClientMarketResearchView:
    return ClientMarketResearchView(
        brand_name=doc.brand_id,
        prepared_date=doc.created_at.date().isoformat(),
        sections={sid: [ClientClaim(text=c.text) for c in s.claims if c.verified]
                  for sid, s in doc.sections.items() if s.status in ("verified", "team_provided")},
        personas=[ClientPersona(**p.model_dump(exclude={"occupation_income"})) for p in doc.personas],
    )
```

### 10. Distribution Links — Scoped, Revocable

```python
# domain/distribution.py
class DistributionLink(BaseModel):
    id: str
    deliverable_id: str
    token: str
    created_by: str
    expires_at: datetime
    revoked: bool = False

# api/routes_client.py
@app.post("/deliverables/{id}/distribution-links")
async def create_link(id: str, created_by: str, ttl_days: int = 30):
    doc = get_deliverable(id)
    if doc.status != "approved":
        raise HTTPException(422, detail="cannot distribute before approval")
    link = DistributionLink(id=uuid4().hex, deliverable_id=id, token=secrets.token_urlsafe(32),
                             created_by=created_by, expires_at=datetime.utcnow() + timedelta(days=ttl_days))
    save_link(link)
    return {"url": f"{settings.CLIENT_BASE_URL}/view/{link.token}"}

@app.get("/client/view/{token}")
async def client_view(token: str) -> ClientMarketResearchView:
    link = load_link_by_token(token)
    if link is None or link.revoked or link.expires_at < datetime.utcnow():
        raise HTTPException(404)  # never 403 -- don't confirm a token ever existed
    return project_for_client(get_deliverable(link.deliverable_id))

@app.post("/distribution-links/{id}/revoke")
async def revoke_link(id: str, revoked_by: str):
    return update_link(id, revoked=True)
```

A client token cannot reach `/brands/*`, `/core/*`, or any other brand's data — it is scoped to exactly one
`deliverable_id`'s read projection, structurally, not by an if-check that could be forgotten.

**Gap analysis finding — the existing internal/client toggle is named ahead of what it does.** Before this
step ships, the repo's current "Distribute" button writes two booleans to a table and nothing else — no
email, no client portal, no webhook. That's correctly in scope for this step's `DistributionLink`, but the
button text shouldn't claim automated delivery it doesn't perform yet. Relabel it in the same PR that adds
`DistributionLink` below, so the UI never overstates the system's own capability, in either its old or new
form: "Mark as shared" / "Create client link" with a one-line caption, not "Distribute."

---

## 11. Frontend — Two Route Groups, One Repo

```
frontend/app/
├── (operator)/            # existing wizard/review/approve/core-kb console -- authenticated, unchanged
│   └── brands/[id]/...
└── (client)/               # new -- token-based, no operator auth, minimal chrome
    └── view/[token]/page.tsx
```

```tsx
// app/(client)/view/[token]/page.tsx
export default async function ClientReport({ params }: { params: { token: string } }) {
  const res = await fetch(`${API_BASE}/client/view/${params.token}`);
  if (!res.ok) return <ExpiredOrInvalidLink />;
  const doc: ClientMarketResearchView = await res.json();
  return (
    <div className="max-w-3xl mx-auto py-12">
      <h1 className="text-2xl font-bold">{doc.brand_name} — Market Research</h1>
      {Object.entries(doc.sections).map(([id, claims]) => (
        <section key={id} className="mb-8">
          <h2 className="text-lg font-semibold mb-3">{SECTION_LABELS[id]}</h2>
          {claims.map((c, i) => <p key={i} className="mb-2">{c.text}</p>)}
        </section>
      ))}
    </div>
  );
}
```

No `ClaimCard`, no `SectionStatusBadge`, no `ApproveButton` import anywhere in `(client)/` — the App
Router's route-group split means there's no code path where an operator component accidentally renders on
the client surface, unlike a conditionally-hidden prop that a future edit could flip by mistake.

```tsx
// (operator) — new: distribution management, alongside the existing ApproveButton flow
// components/DistributionPanel.tsx — created_by comes from the authenticated session
// (Step 4 §0's current_user), never a hardcoded string or a client-supplied field
export function DistributionPanel({ deliverableId, status }: { deliverableId: string; status: string }) {
  const createLink = useMutation({ mutationFn: () => api.post(`/deliverables/${deliverableId}/distribution-links`, {}) });
  return (
    <div>
      <button onClick={() => createLink.mutate()} disabled={status !== 'approved'}>Create client link</button>
      <p className="text-xs text-gray-400">Records that this was shared — email/portal delivery isn't automated yet.</p>
      {createLink.data && <code>{createLink.data.url}</code>}
    </div>
  );
}
```

---

## Part C — Decision Integrity

### 12. Append-Only Approval and Distribution History

**SMM persona framing: a Team Lead's "no, not yet" is part of the brand's record, not a discarded draft.**
When a Team Lead rejects a section for missing evidence, then approves it a week later once the brand
uploads better material, an agency needs to be able to show *both* moments happened — to the client, to a
new team member picking up the account, to their own future selves debugging why a document looks the way
it does. The current schema can't do that.

**Gap analysis finding:** `approval_gate` and `distribution_record` are both `ON CONFLICT DO UPDATE` on
`document_id` — a reject-then-reapprove sequence, or multiple distribution events, silently loses the
earlier record. This is the exact provenance-dropping pattern P7 exists to prevent, one layer above where
claims and checkpoints already handle it correctly.

```sql
CREATE TABLE approval_event (
    id SERIAL PRIMARY KEY, document_id TEXT NOT NULL,
    decision TEXT NOT NULL,          -- approved | rejected | resubmitted
    approver_id TEXT NOT NULL, note TEXT, decided_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE distribution_event (
    id SERIAL PRIMARY KEY, document_id TEXT NOT NULL,
    channel TEXT NOT NULL,           -- internal | client
    distributed_by TEXT NOT NULL, distributed_at TIMESTAMPTZ DEFAULT now()
);
```

```python
# domain/approval.py — current status is a query, not a column
def current_approval_status(document_id: str) -> "ApprovalEvent | None":
    return db_query(
        "SELECT * FROM approval_event WHERE document_id=:id ORDER BY decided_at DESC LIMIT 1", id=document_id
    )

def approval_history(document_id: str) -> list["ApprovalEvent"]:
    return db_query("SELECT * FROM approval_event WHERE document_id=:id ORDER BY decided_at ASC", id=document_id)
```

**Migration:** backfill existing `approval_gate`/`distribution_record` rows as each document's first event,
repoint every read path at `current_approval_status`/latest-`distribution_event`, keep the old tables
read-only for one release before dropping.

```tsx
// components/DecisionHistoryStrip.tsx — free once the data model stops discarding it
export function DecisionHistoryStrip({ events }: { events: ApprovalEvent[] }) {
  return (
    <div className="text-xs text-gray-500 space-y-1">
      {events.map(e => (
        <div key={e.id}>{e.decision} by {e.approver_id} — {formatDate(e.decided_at)}{e.note && `: ${e.note}`}</div>
      ))}
    </div>
  );
}
```

### 13. Rejected → Resubmit, Not a Dead End

**Gap analysis finding:** once `document.status` becomes `"rejected"`, nothing transitions it back to
`pending_approval` — no re-run, no resubmit. SOP-1's real workflow (Team Lead rejects → brand/agency fixes
something → resubmits) has no corresponding feature.

```python
# api/routes.py — two distinct paths, since "fix something" means different things
@app.post("/deliverables/{id}/rerun")
async def rerun(id: str, user: User = Depends(current_user)):
    """New brand material was uploaded to address the rejection -- re-runs
    ingest/retrieval/synthesis from scratch, producing a new pending_approval deliverable."""
    doc = get_deliverable(id)
    if doc.status != "rejected":
        raise HTTPException(409, detail=f"cannot rerun from {doc.status}")
    return run_pipeline(doc.brand_id)

@app.post("/deliverables/{id}/resubmit")
async def resubmit(id: str, note: str, user: User = Depends(current_user)):
    """The rejection was about the write-up, not the evidence -- a strategic_note
    already addressed it. Re-enters review without regenerating."""
    doc = get_deliverable(id)
    if doc.status != "rejected":
        raise HTTPException(409, detail=f"cannot resubmit from {doc.status}")
    save_approval_event(document_id=id, decision="resubmitted", approver_id=user.id, note=note)
    return update_document_status(id, "pending_approval")
```

Both write to `approval_event` above — the full lifecycle (`draft → pending_approval → rejected →
pending_approval (resubmit) → approved`) reads as one coherent history, not a final status field that
erased how it got there.

```tsx
// the rejected-state review page shows both actions distinctly, so the Team Lead
// isn't guessing which one matches what they actually fixed
<RejectedStateActions>
  <button onClick={rerun}>Re-run agent (new evidence uploaded)</button>
  <button onClick={() => resubmit(note)}>Resubmit for review (addressed via notes)</button>
</RejectedStateActions>
```

---

## 14. Infra

```yaml
# infra/docker-compose.yml additions
  beat:
    build: ./backend
    command: celery -A app.workers beat --loglevel=info
    depends_on: [redis]
```

```sql
-- run once per environment, not per deploy
\i infra/sql/grants.sql
```

```env
# .env additions
CLIENT_BASE_URL=https://smm-agent.example.com/view
```

---

## 15. Acceptance Tests

Part A's suite (§4) plus Part D's data ingestion tests (§8) plus:

```python
def test_client_view_excludes_internal_fields():
    link = create_distribution_link(approved_deliverable_id)
    body = client.get(f"/client/view/{link.token}").text
    assert "chunk_id" not in body and "call_site_trace" not in body and "rejection_reason" not in body

def test_client_view_only_verified_sections():
    doc = deliverable_with_mixed_section_statuses()
    view = project_for_client(doc)
    assert all(len(claims) > 0 or sid not in doc.sections for sid, claims in view.sections.items())

def test_expired_and_revoked_links_both_404():
    expired = create_distribution_link(deliverable_id, ttl_days=-1)
    assert client.get(f"/client/view/{expired.token}").status_code == 404
    live = create_distribution_link(deliverable_id)
    revoke_link(live.id, revoked_by="team_lead")
    assert client.get(f"/client/view/{live.token}").status_code == 404

def test_client_token_cannot_reach_operator_endpoints():
    link = create_distribution_link(deliverable_id)
    resp = client.post("/brands/brand-x/research/run", headers={"x-client-token": link.token})
    assert resp.status_code in (401, 403)

def test_distribution_still_blocked_before_approval():
    resp = client.post(f"/deliverables/{pending_document().id}/distribution-links", headers=auth_for("brand-x"))
    assert resp.status_code == 422
```

**Part C:**

```python
def test_reject_then_reapprove_preserves_both_events():
    deliverable_id = pending_document().id
    apply_decision(deliverable_id, approver_id="u1", decision="rejected", note="missing evidence")
    resubmit(deliverable_id, note="brand uploaded updated deck", user=user("u2"))
    apply_decision(deliverable_id, approver_id="u2", decision="approved")
    history = approval_history(deliverable_id)
    assert [e.decision for e in history] == ["rejected", "resubmitted", "approved"]

def test_rerun_requires_rejected_status():
    doc = approved_document()
    resp = client.post(f"/deliverables/{doc.id}/rerun", headers=auth_for(doc.brand_id))
    assert resp.status_code == 409

def test_resubmit_reenters_pending_approval():
    doc = rejected_document()
    resp = client.post(f"/deliverables/{doc.id}/resubmit", json={"note": "fixed"}, headers=auth_for(doc.brand_id))
    assert resp.status_code == 200
    assert get_deliverable(doc.id).status == "pending_approval"
```

**Part D (data ingestion):**

```python
def test_competitor_discovery_respects_segment_whitelist():
    segment = create_segment("brand-x", youtube_keywords=["fitness"], max_competitors=3)
    discovered = discover_competitors("brand-x")
    assert len(discovered) <= 3
    assert all(c.source in ["youtube", "news", "reddit"] for c in discovered)

def test_rate_limit_blocks_and_retries():
    limiter = DataSourceRateLimiter(redis_client)
    set_rate_limit("brand-x", "youtube", 2)
    assert limiter.check("brand-x", "youtube") == True
    assert limiter.check("brand-x", "youtube") == True
    assert limiter.check("brand-x", "youtube") == False  # third call blocked
    
def test_stale_data_degrades_to_insufficient_grounding():
    old_chunk = Chunk(text="...", collected_at=datetime.utcnow() - timedelta(hours=48), valid_until=datetime.utcnow() - timedelta(hours=24))
    ingest_chunk("brand-x", old_chunk)
    result = run_pipeline("brand-x")
    assert result.deliverable.status == "insufficient_grounding"
    assert result.deliverable.status_reason == "data_staleness"

def test_data_collection_error_does_not_fail_pipeline():
    simulate_youtube_api_failure("brand-x")
    simulate_newsapi_success("brand-x", articles_count=5)
    result = collect_all_for_brand("brand-x")
    assert result["youtube"]["status"] in ("failed", "retrying")
    assert result["newsapi"]["status"] == "success"
    # Pipeline continues, uses news data + cached YouTube data

def test_encrypted_credentials_never_logged():
    setup_credential("brand-x", "youtube", api_key="sk-xyz")
    with capture_logs():
        collect_youtube_data("brand-x")
    assert "sk-xyz" not in captured_logs
```
