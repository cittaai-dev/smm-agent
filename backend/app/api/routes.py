from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
from uuid import uuid4

from fastapi import FastAPI, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.requests import Request

from app.domain.deliverable import Deliverable
from app.domain.market_research_document import MarketResearchDocument
from app.domain.quality import QualityCheckpoint, evaluate_checkpoint
from app.domain.review import ApprovalGateRecord, DistributionRecord, StrategicNote
from app.domain.sop1 import SECTIONS_BY_ID
from app.domain.source_file import SourceFile
from app.infra.db import get_session
from app.infra.settings import api_settings
from app.infra.telemetry import instrument_app
from app.orchestration.llm import LLMNotConfiguredError

app = FastAPI(title="smm-agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=api_settings.cors_origin_list,
    allow_methods=["*"],
    allow_headers=["*"],
)

instrument_app(app)  # exposes /metrics (Prometheus) and OTel spans on the 3 call sites


@app.exception_handler(LLMNotConfiguredError)
async def llm_not_configured_handler(request: Request, exc: LLMNotConfiguredError) -> JSONResponse:
    # 503, not 500: this is a missing-config problem the operator can fix,
    # not a bug in the request -- and CORSMiddleware still adds the
    # Access-Control-Allow-Origin header to error responses, so the frontend
    # can read the message instead of just seeing a failed fetch.
    return JSONResponse(status_code=503, content={"detail": str(exc)})

_UPLOAD_DIR = Path("uploads")


class ApprovalDecision(BaseModel):
    approver_id: str
    decision: Literal["approved", "rejected"]
    note: str | None = None


class TeamInputPayload(BaseModel):
    text: str
    author: str | None = None


class StrategicNotePayload(BaseModel):
    section: str
    text: str
    author: str


class DistributionPayload(BaseModel):
    internal: bool
    client: bool


@app.get("/brands/{brand_id}/sections/{section_id}/team-input")
async def get_team_input(brand_id: str, section_id: str) -> dict | None:
    with get_session() as session:
        row = session.execute(
            "SELECT text, author FROM team_input WHERE brand_id = :b AND section = :s",
            {"b": brand_id, "s": section_id},
        ).mappings().first()
    return dict(row) if row else None


@app.put("/brands/{brand_id}/sections/{section_id}/team-input")
async def set_team_input(brand_id: str, section_id: str, payload: TeamInputPayload) -> dict:
    spec = SECTIONS_BY_ID.get(section_id)
    if spec is None or spec.retrieval_mode != "direct_input":
        # Server-enforced, not a frontend-only restriction: storing text against
        # a section nothing will ever read it from is a silent data-loss bug
        # waiting to happen, not a valid request.
        raise HTTPException(422, detail=f"'{section_id}' does not accept direct team input")
    if not payload.text.strip():
        raise HTTPException(422, detail="text must not be empty")

    with get_session() as session:
        session.execute(
            """INSERT INTO team_input (brand_id, section, text, author)
               VALUES (:brand_id, :section, :text, :author)
               ON CONFLICT (brand_id, section) DO UPDATE SET
                   text = EXCLUDED.text, author = EXCLUDED.author, updated_at = now()""",
            {"brand_id": brand_id, "section": section_id, "text": payload.text, "author": payload.author},
        )
        session.commit()
    return {"status": "saved"}


@app.post("/brands/{brand_id}/sources")
async def upload_source(brand_id: str, file: UploadFile, source_kind: str | None = Form(None)):
    _UPLOAD_DIR.mkdir(exist_ok=True)
    dest = _UPLOAD_DIR / f"{uuid4().hex}-{file.filename}"
    dest.write_bytes(await file.read())

    from app.workers.ingest import ingest_file

    ingest_file.delay(brand_id, str(dest), source_kind)
    return {"status": "queued"}


@app.get("/brands/{brand_id}/sources")
async def list_sources(brand_id: str) -> list[SourceFile]:
    with get_session() as session:
        rows = session.execute(
            "SELECT file_id, brand_id, filename, source_kind, status, degraded_reason, created_at "
            "FROM source_file WHERE brand_id = :b ORDER BY created_at",
            {"b": brand_id},
        ).mappings().all()
    return [SourceFile(**row) for row in rows]


@app.post("/brands/{brand_id}/research/run")
async def run_research(brand_id: str) -> Deliverable:
    from app.orchestration.graph import run_pipeline

    result = run_pipeline(brand_id=brand_id)
    _save_deliverable(result.deliverable)
    return result.deliverable


@app.post("/brands/{brand_id}/research/run-all")
async def run_all_research(brand_id: str) -> MarketResearchDocument:
    from app.orchestration.section_runner import assemble_document, run_all_sections

    results = run_all_sections(brand_id)
    document = assemble_document(brand_id, results)
    _save_document(document)
    return document


@app.get("/documents/{document_id}")
async def get_document(document_id: str) -> MarketResearchDocument | None:
    return _load_document(document_id)


@app.get("/documents/{document_id}/checkpoint")
async def get_checkpoint(document_id: str) -> QualityCheckpoint:
    # Live preview of the exact gate /approve will enforce -- same
    # evaluate_checkpoint call, so the FE never re-implements this logic in
    # TS and risks it drifting from the server-enforced version.
    document = _load_document(document_id)
    if document is None:
        raise HTTPException(404, detail=f"no such document: {document_id}")
    return evaluate_checkpoint(document)


@app.post("/documents/{document_id}/notes")
async def add_note(document_id: str, payload: StrategicNotePayload) -> StrategicNote:
    if _load_document(document_id) is None:
        raise HTTPException(404, detail=f"no such document: {document_id}")
    if SECTIONS_BY_ID.get(payload.section) is None:
        raise HTTPException(422, detail=f"'{payload.section}' is not a known section")
    note = StrategicNote(
        id=f"note-{uuid4().hex[:12]}",
        document_id=document_id,
        section=payload.section,
        text=payload.text,
        author=payload.author,
        created_at=datetime.now(UTC),
    )
    _save_note(note)
    return note


@app.get("/documents/{document_id}/notes")
async def list_notes(document_id: str) -> list[StrategicNote]:
    return _load_notes(document_id)


@app.post("/documents/{document_id}/approve")
async def approve_document(document_id: str, decision: ApprovalDecision) -> MarketResearchDocument:
    document = _load_document(document_id)
    if document is None:
        raise HTTPException(404, detail=f"no such document: {document_id}")
    if document.status != "pending_approval":
        raise HTTPException(409, detail=f"cannot transition from {document.status}")

    checkpoint = evaluate_checkpoint(document)
    has_any_claims = any(s.claims for s in document.sections.values())
    if decision.decision == "approved":
        if not has_any_claims:
            # Belt-and-suspenders like the deliverable gate above: assemble_document
            # already routes an all-empty run to insufficient_grounding, never
            # pending_approval, but a document's approvability shouldn't depend
            # solely on which code path produced the row.
            raise HTTPException(422, detail="cannot approve a document with zero claims across all sections")
        if not checkpoint.passed:
            # The server-side gate, not the frontend's disabled button --
            # matches this project's approve endpoints throughout.
            raise HTTPException(
                422, detail={"reason": "quality_checkpoint_failed", "checkpoint": checkpoint.model_dump()}
            )

    document.status = decision.decision
    _save_document(document)
    _save_approval_gate(document_id, decision, checkpoint)
    return document


@app.post("/documents/{document_id}/distribute")
async def distribute_document(document_id: str, payload: DistributionPayload) -> DistributionRecord:
    document = _load_document(document_id)
    if document is None:
        raise HTTPException(404, detail=f"no such document: {document_id}")
    if document.status != "approved":
        raise HTTPException(422, detail="cannot distribute before approval")
    record = DistributionRecord(
        document_id=document_id,
        internal=payload.internal,
        client=payload.client,
        distributed_at=datetime.now(UTC),
    )
    _save_distribution(record)
    return record


@app.get("/documents/{document_id}/distribution")
async def get_distribution(document_id: str) -> DistributionRecord | None:
    return _load_distribution(document_id)


@app.get("/documents/{document_id}/approval-gate")
async def get_approval_gate(document_id: str) -> ApprovalGateRecord | None:
    # Provenance (P7): the checkpoint as it stood *at decision time*, plus who
    # decided and when -- distinct from the live /checkpoint preview above and
    # from document.status, neither of which carries who or when.
    return _load_approval_gate(document_id)


@app.get("/deliverables/{deliverable_id}")
async def get_deliverable(deliverable_id: str) -> Deliverable | None:
    return _load_deliverable(deliverable_id)


@app.post("/deliverables/{deliverable_id}/approve")
async def approve(deliverable_id: str, decision: ApprovalDecision) -> Deliverable:
    deliverable = _load_deliverable(deliverable_id)
    if deliverable is None:
        raise HTTPException(404, detail=f"no such deliverable: {deliverable_id}")
    if deliverable.status != "pending_approval":
        raise HTTPException(409, detail=f"cannot transition from {deliverable.status}")
    if decision.decision == "approved" and len(deliverable.claims) == 0:
        # Step 3 formalizes this as QualityCheckpoint; this is its minimum
        # viable form landing early -- an empty deliverable (e.g. retrieval
        # found nothing) must never be silently approvable.
        raise HTTPException(422, detail="cannot approve a deliverable with zero claims")
    deliverable.status = decision.decision
    _save_deliverable(deliverable)
    return deliverable


def _load_deliverable(deliverable_id: str) -> Deliverable | None:
    with get_session() as session:
        row = session.execute(
            "SELECT id, brand_id, status, claims, call_site_trace FROM deliverable WHERE id = :id",
            {"id": deliverable_id},
        ).mappings().first()
    if row is None:
        return None
    return Deliverable(
        id=row["id"],
        brand_id=row["brand_id"],
        status=row["status"],
        claims=row["claims"],
        call_site_trace=row["call_site_trace"],
    )


def _save_deliverable(deliverable: Deliverable) -> None:
    import json

    with get_session() as session:
        session.execute(
            """INSERT INTO deliverable (id, brand_id, status, claims, call_site_trace)
               VALUES (:id, :brand_id, :status, (:claims)::jsonb, (:trace)::jsonb)
               ON CONFLICT (id) DO UPDATE SET
                   status = EXCLUDED.status,
                   claims = EXCLUDED.claims,
                   call_site_trace = EXCLUDED.call_site_trace""",
            {
                "id": deliverable.id,
                "brand_id": deliverable.brand_id,
                "status": deliverable.status,
                "claims": json.dumps([c.model_dump() for c in deliverable.claims]),
                "trace": json.dumps(deliverable.call_site_trace),
            },
        )
        session.commit()


def _load_document(document_id: str) -> MarketResearchDocument | None:
    with get_session() as session:
        row = session.execute(
            "SELECT id, brand_id, status, sections, call_site_trace FROM market_research_document "
            "WHERE id = :id",
            {"id": document_id},
        ).mappings().first()
    if row is None:
        return None
    return MarketResearchDocument(
        id=row["id"],
        brand_id=row["brand_id"],
        status=row["status"],
        sections=row["sections"],
        call_site_trace=row["call_site_trace"],
    )


def _save_document(document: MarketResearchDocument) -> None:
    import json

    with get_session() as session:
        session.execute(
            """INSERT INTO market_research_document (id, brand_id, status, sections, call_site_trace)
               VALUES (:id, :brand_id, :status, (:sections)::jsonb, (:trace)::jsonb)
               ON CONFLICT (id) DO UPDATE SET
                   status = EXCLUDED.status,
                   sections = EXCLUDED.sections,
                   call_site_trace = EXCLUDED.call_site_trace""",
            {
                "id": document.id,
                "brand_id": document.brand_id,
                "status": document.status,
                "sections": json.dumps({k: v.model_dump() for k, v in document.sections.items()}),
                "trace": json.dumps(document.call_site_trace),
            },
        )
        session.commit()


def _save_note(note: StrategicNote) -> None:
    with get_session() as session:
        session.execute(
            """INSERT INTO strategic_note (id, document_id, section, text, author, created_at)
               VALUES (:id, :document_id, :section, :text, :author, :created_at)""",
            note.model_dump(),
        )
        session.commit()


def _load_notes(document_id: str) -> list[StrategicNote]:
    with get_session() as session:
        rows = session.execute(
            "SELECT id, document_id, section, text, author, created_at FROM strategic_note "
            "WHERE document_id = :id ORDER BY created_at",
            {"id": document_id},
        ).mappings().all()
    return [StrategicNote(**row) for row in rows]


def _save_approval_gate(document_id: str, decision: ApprovalDecision, checkpoint: QualityCheckpoint) -> None:
    import json

    with get_session() as session:
        session.execute(
            """INSERT INTO approval_gate (document_id, approver_id, decision, note, checkpoint, decided_at)
               VALUES (:document_id, :approver_id, :decision, :note, (:checkpoint)::jsonb, now())
               ON CONFLICT (document_id) DO UPDATE SET
                   approver_id = EXCLUDED.approver_id,
                   decision = EXCLUDED.decision,
                   note = EXCLUDED.note,
                   checkpoint = EXCLUDED.checkpoint,
                   decided_at = EXCLUDED.decided_at""",
            {
                "document_id": document_id,
                "approver_id": decision.approver_id,
                "decision": decision.decision,
                "note": decision.note,
                "checkpoint": json.dumps(checkpoint.model_dump()),
            },
        )
        session.commit()


def _load_approval_gate(document_id: str) -> ApprovalGateRecord | None:
    with get_session() as session:
        row = session.execute(
            "SELECT document_id, approver_id, decision, note, checkpoint, decided_at FROM approval_gate "
            "WHERE document_id = :id",
            {"id": document_id},
        ).mappings().first()
    return ApprovalGateRecord(**row) if row else None


def _save_distribution(record: DistributionRecord) -> None:
    with get_session() as session:
        session.execute(
            """INSERT INTO distribution_record (document_id, internal, client, distributed_at)
               VALUES (:document_id, :internal, :client, :distributed_at)
               ON CONFLICT (document_id) DO UPDATE SET
                   internal = EXCLUDED.internal,
                   client = EXCLUDED.client,
                   distributed_at = EXCLUDED.distributed_at""",
            record.model_dump(),
        )
        session.commit()


def _load_distribution(document_id: str) -> DistributionRecord | None:
    with get_session() as session:
        row = session.execute(
            "SELECT document_id, internal, client, distributed_at FROM distribution_record "
            "WHERE document_id = :id",
            {"id": document_id},
        ).mappings().first()
    return DistributionRecord(**row) if row else None
