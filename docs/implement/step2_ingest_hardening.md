# Step 2 — Improve Phase 1 (Ingest): Multi-File, Full Chunk Ladder, All 11 SOP-1 Sections

## Objective

Step 1 proved the contract on one file, one section. Step 2 makes the **Ingest plane production-grade** for
Brand Workspace, and wires **all 11 SOP-1 sections** against it — still no Market Intel Core, still UNION-only
retrieval. Sections that need Core (§5, §6, §9, §10) will run in *degraded mode* (return "insufficient evidence,"
per P5) until Step 4. This is intentional — proves the degrade path, not a gap.

**Definition of done:** all brand-material file types from SOP-01's onboarding zones ingest correctly, C1–C8
validators gate every chunk, re-upload is a no-op, and §1/§2/§3/§4 (the brand-only sections) produce a complete,
approved Market Research document for a real brand.

---

## 1. What Changes From Step 1

| Step 1 | Step 2 |
|---|---|
| 1 file, PDF only | Brand materials (.pdf/.ppt/.doc/.png), analytics (.csv/.xlsx), optional competitor uploads |
| No validators | Full C1–C8 assembler/validator |
| L1 paragraph split only | Chunk router: L0 floor, L1 structural (default for Brand Workspace per `dual-kb.md §3`) |
| 1 section (§1) | All 11 sections, each with its own `Plan → Retrieve → Synthesize` sub-run |
| No degrade path exercised | §5/§6/§9/§10 hit "insufficient evidence" deterministically — proves P5 |

---

## 2. Domain — Section Registry (`domain/sop1.py`)

```python
from pydantic import BaseModel
from typing import Literal

SectionId = Literal[
    "brand_overview", "business_goals", "target_audience", "customer_needs",
    "market_overview", "competitor_analysis", "swot", "positioning_usp",
    "platform_analysis", "trends_opportunities", "key_takeaways",
]

class SectionSpec(BaseModel):
    id: SectionId
    requires_core: bool
    retrieval_mode: Literal["union", "core_only", "bridge", "synthesis_only", "direct_input"]
    depends_on: list[SectionId] = []

SOP1_SECTIONS: list[SectionSpec] = [
    SectionSpec(id="brand_overview", requires_core=False, retrieval_mode="union"),
    SectionSpec(id="business_goals", requires_core=False, retrieval_mode="direct_input"),
    SectionSpec(id="target_audience", requires_core=False, retrieval_mode="union"),
    SectionSpec(id="customer_needs", requires_core=False, retrieval_mode="union"),
    SectionSpec(id="market_overview", requires_core=True, retrieval_mode="core_only"),
    SectionSpec(id="competitor_analysis", requires_core=True, retrieval_mode="bridge"),
    SectionSpec(id="swot", requires_core=False, retrieval_mode="synthesis_only",
                depends_on=["brand_overview", "target_audience", "customer_needs",
                            "market_overview", "competitor_analysis"]),
    SectionSpec(id="positioning_usp", requires_core=False, retrieval_mode="synthesis_only",
                depends_on=["swot"]),
    SectionSpec(id="platform_analysis", requires_core=True, retrieval_mode="bridge"),
    SectionSpec(id="trends_opportunities", requires_core=True, retrieval_mode="core_only"),
    SectionSpec(id="key_takeaways", requires_core=False, retrieval_mode="synthesis_only",
                depends_on=["swot", "positioning_usp", "platform_analysis", "trends_opportunities"]),
]
```

**Decision:** the section registry is data, not branching code — the graph iterates it. **Alternative
rejected:** 11 hardcoded LangGraph subgraphs — rejected because SOP-02–06 will each need their own registry
later, and the pattern should already be reusable, not rebuilt.

---

## 3. Chunk Router — L0/L1 for Brand Workspace (`ingestion/router.py`)

```python
from app.domain.chunk import Chunk
import hashlib

def route_and_chunk(doc_id: str, kb_id: str, blocks: list["Block"]) -> list[Chunk]:
    """Brand Workspace profile: L1 structural default, L0 floor on failure. No L2/L3 (Core-only ladders)."""
    chunks = []
    for i, block in enumerate(blocks):
        strategy = "L1" if block.is_structural else "L0"
        span = (block.start, block.end)
        chunk_id = hashlib.sha256(f"{doc_id}:{span}:{kb_id}:v1".encode()).hexdigest()
        chunks.append(Chunk(
            chunk_id=chunk_id, kb_id=kb_id, doc_id=doc_id, block_span=span,
            text=block.text, order_confidence=block.confidence,
            degraded=(strategy == "L0"),
        ))
    return chunks
```

---

## 4. Validators C1–C8 (`ingestion/validators.py`)

```python
from dataclasses import dataclass

@dataclass
class ValidationResult:
    code: str
    passed: bool
    detail: str = ""

def validate_batch(chunks: list["Chunk"]) -> list[ValidationResult]:
    results = []
    results.append(_c1_atomicity(chunks))
    results.append(_c2_heading_path(chunks))
    results.append(_c3_total_order(chunks))
    results.append(_c4_monotonic_escalation(chunks))
    results.append(_c5_determinism(chunks))
    results.append(_c6_degrade_not_fail(chunks))
    results.append(_c7_order_stamped(chunks))
    results.append(_c8_edge_confinement(chunks))
    return results

def _c1_atomicity(chunks):
    ok = all(len(c.text.strip()) > 0 for c in chunks)
    return ValidationResult("C1", ok, "empty chunk found" if not ok else "")

def _c3_total_order(chunks):
    spans = [c.block_span for c in chunks]
    ok = spans == sorted(spans)
    return ValidationResult("C3", ok, "spans not strictly ordered" if not ok else "")

def _c7_order_stamped(chunks):
    ok = all(c.order_confidence is not None for c in chunks)
    return ValidationResult("C7", ok)

def _c8_edge_confinement(chunks):
    # no edges exist yet in Step 2 (Brand Workspace only) — trivially passes; real check lands Step 4
    return ValidationResult("C8", True)

# C2, C4, C5, C6 similarly — each returns pass/fail + detail, never raises.
# A failing validator routes the BATCH back to route_and_chunk() with strategy forced to L0 (C6).
```

**Why C6 (degrade-not-fail) is load-bearing here:** in Step 2's real-world test, a scanned image-only PPTX
slide will fail C1 (no extractable text) — the batch routes to L0 fallback rather than aborting the whole
brand's ingest. This is tested explicitly (§8 below), not just documented.

---

## 5. Ingest Pipeline, Multi-File (`workers/ingest.py`)

```python
@shared_task(bind=True, max_retries=3)
def ingest_source(self, brand_id: str, file_path: str, source_kind: str):
    from app.ingestion.parse import parse_by_type
    from app.ingestion.router import route_and_chunk
    from app.ingestion.validators import validate_batch

    content_hash = hash_file(file_path)
    if already_ingested(content_hash):
        return "skipped-duplicate"

    try:
        blocks = parse_by_type(file_path, source_kind)   # pdf/ppt/doc/png/csv/xlsx dispatch
    except Exception as e:
        record_degraded_source(brand_id, file_path, reason=str(e))
        return "degraded"  # P5 — never fail the whole ingest

    doc_id = register_document(brand_id, file_path, content_hash)
    chunks = route_and_chunk(doc_id, f"run:{brand_id}", blocks)
    results = validate_batch(chunks)

    if not all(r.passed for r in results):
        chunks = route_and_chunk(doc_id, f"run:{brand_id}", blocks, force_l0=True)  # C6 fallback

    for c in chunks:
        c_with_embedding = embed_chunk(c)
        store_chunk(c_with_embedding)

    return "ingested"
```

---

## 6. Per-Section Orchestration (`orchestration/section_runner.py`)

```python
def run_section(brand_id: str, spec: "SectionSpec", prior_results: dict) -> "VerifiedSectionResult":
    if spec.retrieval_mode == "direct_input":
        return use_team_lead_input(brand_id, spec.id)

    if spec.retrieval_mode in ("core_only", "bridge") and not core_kb_available():
        return VerifiedSectionResult(
            section=spec.id, status="insufficient_evidence",
            reason="Market Intel Core not yet available — deferred to Step 4",
        )

    if spec.retrieval_mode == "synthesis_only":
        context = {dep: prior_results[dep] for dep in spec.depends_on}
        return synthesize_from_prior(spec.id, context)

    # union
    state = RunState(brand_id=brand_id, kb_id=f"run:{brand_id}", section=spec.id)
    return app_graph.invoke(state).deliverable_section

def run_all_sections(brand_id: str) -> "MarketResearchDocument":
    results = {}
    for spec in SOP1_SECTIONS:   # registry order already respects dependency order
        results[spec.id] = run_section(brand_id, spec, results)
    return assemble_document(brand_id, results)
```

**Call-site budget check:** 11 sections × ≤2 generative calls (Plan+Synthesize, Repair conditional) is bounded
and traceable — `call_site_trace` aggregates per-section counts, so a review can see "44 calls this run" and
know exactly why, rather than an opaque total.

---

## 7. Postgres — Additions Only

```sql
ALTER TABLE chunk ADD COLUMN heading_path TEXT[];
ALTER TABLE document_registry ADD COLUMN source_kind TEXT;   -- brand_material|analytics|competitor_upload

CREATE TABLE source_file (
    file_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    filename TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    mime_type TEXT,
    size_bytes INT,
    status TEXT NOT NULL,           -- uploading|ingested|degraded
    ttl_expires_at TIMESTAMPTZ
);

CREATE TABLE market_research_document (
    id TEXT PRIMARY KEY,
    brand_id TEXT NOT NULL,
    sections JSONB NOT NULL,        -- MarketResearchDocument serialized
    status TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);
```

No new database, no new store — additive columns and two new tables in the same schema (`dual-kb.md §5`
still holds).

---

## 8. Frontend — Full Onboarding Wizard + Section Outline

```
app/brands/[id]/
├── onboard/page.tsx           # 3 upload zones: brand / analytics / competitor(optional)
├── plan/page.tsx              # 11-row outline, source pills per section (matches original mockup)
└── review/page.tsx            # per-section claim viewer, degraded sections shown distinctly
```

```tsx
// components/SectionRow.tsx
export function SectionRow({ section }: { section: SectionResult }) {
  const badge = section.status === 'insufficient_evidence'
    ? <Badge variant="warning">Awaiting Market Intel Core</Badge>
    : <Badge variant="success">{section.claims.length} claims verified</Badge>;
  return (
    <div className="border rounded-lg p-4 flex justify-between items-center">
      <span>{SECTION_LABELS[section.id]}</span>
      {badge}
    </div>
  );
}
```

**Honest degraded state in the UI, not hidden:** §5/§6/§9/§10 show "Awaiting Market Intel Core" rather than
an empty or fabricated section — this is the P5 degrade contract made visible to the operator.

---

## 9. Infra — Additions

```yaml
  worker-ingest:
    build: ./backend
    command: celery -A app.workers worker -Q ingest --loglevel=info --concurrency=4
    depends_on: [postgres, redis]
```

Separate queue (`-Q ingest`) from the generation worker — ingest is throughput-bound (many files), generation
is latency-bound (user waiting on SSE) per `dual-kb.md §8`'s "separate deploys" principle, introduced early so
Step 4's Core builder split isn't a rewrite.

---

## 10. Step 2 Acceptance Tests

```python
def test_all_file_types_ingest():
    for f in ["brand_deck.pptx", "guidelines.pdf", "insights.csv", "analytics.xlsx"]:
        assert ingest_source("brand-x", f, source_kind=infer_kind(f)) in ("ingested", "degraded")

def test_scanned_image_degrades_not_fails():
    result = ingest_source("brand-x", "scanned_no_text.pptx", source_kind="brand_material")
    assert result == "degraded"
    assert brand_ingest_status("brand-x") != "failed"

def test_core_dependent_sections_degrade_cleanly():
    doc = run_all_sections("brand-x")
    for sid in ("market_overview", "competitor_analysis", "platform_analysis", "trends_opportunities"):
        assert doc.sections[sid].status == "insufficient_evidence"

def test_brand_only_sections_complete():
    doc = run_all_sections("brand-x")
    for sid in ("brand_overview", "target_audience", "customer_needs"):
        assert doc.sections[sid].status == "verified"
        assert all(c.verified for c in doc.sections[sid].claims)

def test_reupload_across_file_types_is_noop():
    ingest_source("brand-x", "guidelines.pdf", "brand_material")
    n1 = count_chunks("brand-x")
    ingest_source("brand-x", "guidelines.pdf", "brand_material")
    assert count_chunks("brand-x") == n1
```
