# Step 1 — Foundation: One Brand, One Section, Proven Citation Contract

## Objective

Prove the pipeline contract end to end — upload → chunk → plan → retrieve → synthesize → verify → deliver → approve —
on **one brand, one uploaded document, one SOP-1 section** ("Brand overview," §1). No Market Intel Core,
no live crawl, no rerank, no hydration. This is `pipeline.md §8 Step 0` and `dual-kb.md §9 Step 0` applied literally.

**Definition of done:** a claim in the delivered §1 text traces `chunk_id → block_span → source file`,
verifiable by a human opening the original doc. If this doesn't hold here, nothing built later fixes it.

---

## 1. Repository Layout

```
smm-agent/
├── backend/
│   ├── app/
│   │   ├── api/            # FastAPI routers
│   │   ├── domain/         # Pydantic models — the phase contracts
│   │   ├── orchestration/  # LangGraph nodes + graph
│   │   ├── retrieval/      # typed retrieval interface
│   │   ├── infra/          # db session, celery app, settings
│   │   └── workers/        # Celery tasks
│   ├── alembic/
│   ├── tests/
│   └── pyproject.toml
├── frontend/
│   ├── app/                # Next.js App Router
│   ├── components/
│   ├── lib/                # generated OpenAPI types, SSE client
│   └── package.json
└── infra/
    ├── docker-compose.yml  # postgres+pgvector, redis
    └── alembic.ini
```

---

## 2. Domain Contracts (`backend/app/domain/`)

```python
# domain/chunk.py
from pydantic import BaseModel

class Chunk(BaseModel):
    chunk_id: str
    kb_id: str                  # "run:<brand_id>" only in Step 1
    doc_id: str
    block_span: tuple[int, int]
    text: str
    order_confidence: float = 1.0
    degraded: bool = False

# domain/retrieval.py
from typing import Literal

class RetrievalPlan(BaseModel):
    sub_queries: list[str]
    filters: dict[str, str] = {}
    topology: Literal["union"] = "union"   # bridge not available yet
    k_per_query: int = 8

class RetrievedContext(BaseModel):
    chunks: list[Chunk]
    plan: RetrievalPlan

# domain/claim.py
class ClaimDraft(BaseModel):
    section: Literal["brand_overview"]      # only §1 in Step 1
    text: str
    chunk_id: str | None

class VerifiedClaim(BaseModel):
    section: str
    text: str
    chunk_id: str
    block_span: tuple[int, int]
    verified: bool
    rejection_reason: Literal["missing_chunk", "no_citation", None] = None

# domain/deliverable.py
class Deliverable(BaseModel):
    id: str
    brand_id: str
    status: Literal["draft", "pending_approval", "approved", "rejected", "insufficient_grounding"]
    claims: list[VerifiedClaim]
    call_site_trace: dict[str, int]
```

**Decision:** one file per concern, frozen at Step 1, extended (never mutated in place) in later steps.
**Alternative rejected:** a single `models.py` — rejected because Step 2/3 additions would create merge noise on
a file every node imports.

---

## 3. Orchestration — LangGraph, 2 Real Call Sites

Step 1 uses Plan + Synthesize only. Repair is wired but untested until Step 3 (needs a rejection to fire against).

```python
# orchestration/graph.py
from langgraph.graph import StateGraph, END
from app.domain.retrieval import RetrievalPlan, RetrievedContext
from app.domain.claim import ClaimDraft, VerifiedClaim
from app.domain.deliverable import Deliverable
from pydantic import BaseModel

class RunState(BaseModel):
    brand_id: str
    kb_id: str
    plan: RetrievalPlan | None = None
    context: RetrievedContext | None = None
    claims: list[ClaimDraft] = []
    verified: list[VerifiedClaim] = []
    repair_attempted: bool = False
    deliverable: Deliverable | None = None

def plan_node(state: RunState) -> RunState:
    # call site ① — LLM emits RetrievalPlan, not prose
    from app.orchestration.llm import call_plan
    state.plan = call_plan(section="brand_overview", brand_id=state.brand_id)
    return state

def retrieve_node(state: RunState) -> RunState:
    from app.retrieval.dense import search_dense
    chunks = search_dense(kb_id=state.kb_id, plan=state.plan)
    state.context = RetrievedContext(chunks=chunks, plan=state.plan)
    return state

def synthesize_node(state: RunState) -> RunState:
    # call site ②
    from app.orchestration.llm import call_synthesize
    state.claims = call_synthesize(section="brand_overview", context=state.context)
    return state

def verify_node(state: RunState) -> RunState:
    from app.domain.verify import verify_claims
    state.verified = verify_claims(state.claims, state.context)
    return state

def repair_node(state: RunState) -> RunState:
    # call site ③ — fires once
    from app.orchestration.llm import call_repair
    state.claims = call_repair(state.claims, state.context)
    state.repair_attempted = True
    return state

def route_after_verify(state: RunState) -> str:
    all_ok = all(c.verified for c in state.verified)
    if all_ok:
        return "deliver"
    if state.repair_attempted:
        return "insufficient_grounding"
    return "repair"

def deliver_node(state: RunState) -> RunState:
    state.deliverable = Deliverable(
        id=f"del-{state.brand_id}-brand_overview",
        brand_id=state.brand_id,
        status="pending_approval",
        claims=state.verified,
        call_site_trace={"plan": 1, "synthesize": 1, "repair": int(state.repair_attempted)},
    )
    return state

def insufficient_node(state: RunState) -> RunState:
    state.deliverable = Deliverable(
        id=f"del-{state.brand_id}-brand_overview",
        brand_id=state.brand_id,
        status="insufficient_grounding",
        claims=state.verified,
        call_site_trace={"plan": 1, "synthesize": 1, "repair": 1},
    )
    return state

graph = StateGraph(RunState)
graph.add_node("plan", plan_node)
graph.add_node("retrieve", retrieve_node)
graph.add_node("synthesize", synthesize_node)
graph.add_node("verify", verify_node)
graph.add_node("repair", repair_node)
graph.add_node("deliver", deliver_node)
graph.add_node("insufficient_grounding", insufficient_node)

graph.set_entry_point("plan")
graph.add_edge("plan", "retrieve")
graph.add_edge("retrieve", "synthesize")
graph.add_edge("synthesize", "verify")
graph.add_conditional_edges("verify", route_after_verify, {
    "deliver": "deliver", "repair": "repair", "insufficient_grounding": "insufficient_grounding",
})
graph.add_edge("repair", "verify")
graph.add_edge("deliver", END)
graph.add_edge("insufficient_grounding", END)

app_graph = graph.compile()
```

**Why LangGraph over a hand-rolled loop:** the conditional edge on `verify` is exactly the "repair fires once,
rejected twice → insufficient grounding" rule from `pipeline.md §5.3` — expressing it as a graph edge makes the
bounded-retry a structural property, not a variable someone can forget to check.

---

## 4. Deterministic Verifier — Zero LLM

```python
# domain/verify.py
def verify_claims(claims: list["ClaimDraft"], context: "RetrievedContext") -> list["VerifiedClaim"]:
    known = {c.chunk_id: c for c in context.chunks}
    out = []
    for claim in claims:
        if claim.chunk_id is None:
            out.append(VerifiedClaim(section=claim.section, text=claim.text, chunk_id="",
                                      block_span=(0, 0), verified=False, rejection_reason="no_citation"))
            continue
        chunk = known.get(claim.chunk_id)
        if chunk is None:
            out.append(VerifiedClaim(section=claim.section, text=claim.text, chunk_id=claim.chunk_id,
                                      block_span=(0, 0), verified=False, rejection_reason="missing_chunk"))
            continue
        out.append(VerifiedClaim(section=claim.section, text=claim.text, chunk_id=claim.chunk_id,
                                  block_span=chunk.block_span, verified=True))
    return out
```

This is a lookup against `context.chunks` — not a database call, not a model call. It is the whole
verification contract at Step 1: "does the tagged chunk_id exist in the assembled context."

---

## 5. Ingest — Single File, L1 Only

```python
# workers/ingest.py
from celery import shared_task
import hashlib

@shared_task
def ingest_file(brand_id: str, file_path: str) -> str:
    content = open(file_path, "rb").read()
    content_hash = hashlib.sha256(content).hexdigest()
    # idempotency: skip if doc with this hash already ingested for this brand
    from app.infra.db import get_session
    from app.domain.chunk import Chunk
    with get_session() as session:
        if session.execute(
            "SELECT 1 FROM document_registry WHERE content_hash=:h", {"h": content_hash}
        ).first():
            return "skipped-duplicate"
        doc_id = f"doc-{content_hash[:12]}"
        text = extract_text(file_path)          # pymupdf / python-docx per file type
        for i, para in enumerate(split_paragraphs(text)):   # L1: paragraph/structural
            chunk_id = hashlib.sha256(f"{doc_id}:{i}".encode()).hexdigest()
            embedding = embed(para)               # OpenAI embeddings call, cached by content hash
            session.execute(
                """INSERT INTO chunk (chunk_id, kb_id, doc_id, block_span, text, embedding)
                   VALUES (:cid, :kb, :doc, :span, :text, :emb)""",
                {"cid": chunk_id, "kb": f"run:{brand_id}", "doc": doc_id,
                 "span": (i, i), "text": para, "emb": embedding},
            )
        session.commit()
    return "ingested"
```

`content_hash` idempotency (P6) is present from line one — re-uploading the same file is a no-op, proven
in the Step 1 test suite, not deferred.

---

## 6. Postgres Schema (`alembic/versions/0001_foundation.py`)

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE document_registry (
    doc_id TEXT PRIMARY KEY,
    kb_id TEXT NOT NULL,
    content_hash TEXT UNIQUE NOT NULL,
    source_uri TEXT,
    ingested_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE chunk (
    chunk_id TEXT PRIMARY KEY,
    kb_id TEXT NOT NULL,
    doc_id TEXT REFERENCES document_registry(doc_id),
    block_span INT4RANGE,
    text TEXT NOT NULL,
    embedding VECTOR(1536),
    order_confidence FLOAT DEFAULT 1.0,
    degraded BOOLEAN DEFAULT FALSE
);
CREATE INDEX chunk_kb_id_idx ON chunk (kb_id);
CREATE INDEX chunk_embedding_idx ON chunk USING ivfflat (embedding vector_cosine_ops);

CREATE TABLE deliverable (
    id TEXT PRIMARY KEY,
    brand_id TEXT NOT NULL,
    status TEXT NOT NULL,
    claims JSONB NOT NULL,
    call_site_trace JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);
```

Only three tables. Everything else (edges, versions, promotion) is deliberately absent — Step 1 has no
Core KB to version and no graph to traverse.

---

## 7. API (`api/routes.py`)

```python
from fastapi import FastAPI
from sse_starlette.sse import EventSourceResponse

app = FastAPI()

@app.post("/brands/{brand_id}/sources")
async def upload_source(brand_id: str, file: UploadFile):
    path = save_upload(file)
    ingest_file.delay(brand_id, path)
    return {"status": "queued"}

@app.post("/brands/{brand_id}/research/run")
async def run_research(brand_id: str):
    from app.orchestration.graph import app_graph, RunState
    result = app_graph.invoke(RunState(brand_id=brand_id, kb_id=f"run:{brand_id}"))
    return result.deliverable

@app.get("/brands/{brand_id}/research/stream")
async def stream_progress(brand_id: str):
    async def event_gen():
        async for trace in subscribe_phase_trace(brand_id):     # redis pub/sub
            yield {"event": "phase", "data": trace.model_dump_json()}
    return EventSourceResponse(event_gen())

@app.post("/deliverables/{deliverable_id}/approve")
async def approve(deliverable_id: str, decision: ApprovalDecision):
    return apply_approval(deliverable_id, decision)   # server-enforced state transition
```

---

## 8. Frontend — Minimal Wizard (Next.js)

```
app/
├── brands/[id]/
│   ├── upload/page.tsx        # single upload zone
│   ├── run/page.tsx           # trigger + SSE progress
│   └── review/page.tsx        # claim list + approve button
```

```tsx
// app/brands/[id]/review/page.tsx
'use client';
import { useQuery, useMutation } from '@tanstack/react-query';

export default function Review({ params }: { params: { id: string } }) {
  const { data: deliverable } = useQuery({
    queryKey: ['deliverable', params.id],
    queryFn: () => fetch(`/api/brands/${params.id}/research/run`, { method: 'POST' }).then(r => r.json()),
  });

  const approve = useMutation({
    mutationFn: () => fetch(`/api/deliverables/${deliverable.id}/approve`, {
      method: 'POST', body: JSON.stringify({ approver_id: 'team_lead', decision: 'approved' }),
    }),
  });

  return (
    <div>
      {deliverable?.claims.map((c: any) => (
        <div key={c.chunk_id} className={c.verified ? 'border-green-500' : 'border-red-500'}>
          <p>{c.text}</p>
          <code>{c.chunk_id}</code>
        </div>
      ))}
      <button onClick={() => approve.mutate()} disabled={deliverable?.status !== 'pending_approval'}>
        Approve
      </button>
    </div>
  );
}
```

**FE↔BE contract sync:** run `openapi-typescript http://localhost:8000/openapi.json -o lib/api-types.ts`
as a pre-build step — the FE never hand-writes a type that duplicates a Pydantic model.

---

## 9. Infra (`docker-compose.yml`)

```yaml
services:
  postgres:
    image: pgvector/pgvector:pg16
    environment: { POSTGRES_DB: smm, POSTGRES_PASSWORD: dev }
    ports: ["5432:5432"]
  redis:
    image: redis:7
    ports: ["6379:6379"]
  backend:
    build: ./backend
    depends_on: [postgres, redis]
    environment: { DATABASE_URL: postgresql+psycopg://postgres:dev@postgres/smm, REDIS_URL: redis://redis }
  worker:
    build: ./backend
    command: celery -A app.workers worker --loglevel=info
    depends_on: [postgres, redis]
  frontend:
    build: ./frontend
    ports: ["3000:3000"]
```

---

## 10. Step 1 Acceptance Tests

```python
# tests/test_foundation.py
def test_citation_resolves():
    result = run_pipeline(brand_id="test-brand")
    for claim in result.deliverable.claims:
        assert claim.verified
        chunk = get_chunk(claim.chunk_id)
        assert chunk.block_span == claim.block_span

def test_fabricated_citation_rejected():
    inject_bad_chunk_id()
    result = run_pipeline(brand_id="test-brand")
    assert any(c.rejection_reason == "missing_chunk" for c in result.deliverable.claims) is False  # repaired

def test_idempotent_reupload():
    ingest_file("test-brand", "sample.pdf")
    count_1 = count_chunks("test-brand")
    ingest_file("test-brand", "sample.pdf")
    count_2 = count_chunks("test-brand")
    assert count_1 == count_2

def test_approval_gate_blocks_default():
    result = run_pipeline(brand_id="test-brand")
    assert result.deliverable.status == "pending_approval"
    assert result.deliverable.status != "approved"
```

**If these four pass, Step 1 is done.** Everything in Steps 2+ is additive on top of a proven contract.
