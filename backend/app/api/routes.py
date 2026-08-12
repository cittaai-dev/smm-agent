import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal
from uuid import uuid4

from fastapi import Depends, FastAPI, Form, HTTPException, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.requests import Request

from app.api.deps import current_user, resolve_brand_scope
from app.api.middleware.rate_limit import RateLimitMiddleware
from app.api.routes_health import health_router
from app.api.websocket import ws_router
from app.domain.approval import ApprovalEvent
from app.domain.client_view import ClientMarketResearchView, project_for_client
from app.domain.data_source import DataSourceKind
from app.domain.deliverable import Deliverable
from app.domain.distribution import DistributionEvent, DistributionLink
from app.domain.kb_version import GoldenCase, KBVersion
from app.domain.market_research_document import MarketResearchDocument
from app.domain.market_segment import MarketSegment
from app.domain.quality import QualityCheckpoint, evaluate_checkpoint
from app.domain.review import ApprovalGateRecord, DistributionRecord, StrategicNote
from app.domain.sop1 import SECTIONS_BY_ID
from app.domain.source_file import SourceFile
from app.domain.user import User
from app.export.docx_builder import build_docx
from app.infra.crypto import encrypt_api_key
from app.infra.db import get_session
from app.infra.settings import api_settings
from app.infra.telemetry import instrument_app
from app.orchestration.llm import LLMNotConfiguredError

app = FastAPI(title="smm-agent")

# Registration order matters: Starlette wraps middleware outside-in in
# reverse-add order, so RateLimitMiddleware (added first, thus innermost)
# runs after CORSMiddleware -- a 429 response still carries CORS headers,
# so the frontend can read the rejection instead of seeing a failed fetch.
app.add_middleware(RateLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=api_settings.cors_origin_list,
    allow_methods=["*"],
    allow_headers=["*"],
)

instrument_app(app)  # exposes /metrics (Prometheus) and OTel spans on the 3 call sites
app.include_router(health_router)
app.include_router(ws_router)


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


class StagingBuildPayload(BaseModel):
    source_paths: list[str]
    target_version: int


class PromotionRequestPayload(BaseModel):
    source_summary: str


class PromotionDecisionPayload(BaseModel):
    decision: Literal["approved", "rejected"]


class ResubmitPayload(BaseModel):
    approver_id: str
    note: str


class DistributionLinkPayload(BaseModel):
    created_by: str
    ttl_days: int = 30


class DataSourceCredentialPayload(BaseModel):
    source: DataSourceKind
    api_key: str
    rate_limit_per_hour: int = 60


class MarketSegmentPayload(BaseModel):
    segment_name: str
    youtube_channel_keywords: list[str] = []
    news_sources: list[str] = []
    reddit_communities: list[str] = []
    website_urls: list[str] = []
    max_competitors_to_track: int = 10


@app.post("/brands/{brand_id}/data-sources/credentials")
async def set_data_source_credential(
    brand_id: str, payload: DataSourceCredentialPayload, kb_id: str = Depends(resolve_brand_scope)
) -> dict:
    with get_session() as session:
        session.execute(
            """INSERT INTO data_source_credential (brand_id, source, encrypted_api_key, rate_limit_per_hour)
               VALUES (:brand, :source, :key, :limit)
               ON CONFLICT (brand_id, source) DO UPDATE SET
                   encrypted_api_key = EXCLUDED.encrypted_api_key,
                   rate_limit_per_hour = EXCLUDED.rate_limit_per_hour""",
            {
                "brand": brand_id,
                "source": payload.source,
                "key": encrypt_api_key(payload.api_key),
                "limit": payload.rate_limit_per_hour,
            },
        )
        session.commit()
    return {"status": "saved", "source": payload.source}


@app.get("/brands/{brand_id}/data-sources/credentials")
async def list_data_source_credentials(brand_id: str, kb_id: str = Depends(resolve_brand_scope)) -> list[dict]:
    # Never returns api_key or encrypted_api_key -- confirming a credential
    # exists is fine, its value never leaves storage once written.
    with get_session() as session:
        rows = session.execute(
            "SELECT source, rate_limit_per_hour, created_at, last_used_at "
            "FROM data_source_credential WHERE brand_id = :brand",
            {"brand": brand_id},
        ).mappings().all()
    return [dict(row) for row in rows]


@app.put("/brands/{brand_id}/market-segments")
async def set_market_segment(
    brand_id: str, payload: MarketSegmentPayload, kb_id: str = Depends(resolve_brand_scope)
) -> MarketSegment:
    segment = MarketSegment(brand_id=brand_id, **payload.model_dump())
    with get_session() as session:
        session.execute(
            """INSERT INTO market_segment (brand_id, segment_name, youtube_channel_keywords,
                                            news_sources, reddit_communities, website_urls,
                                            max_competitors_to_track)
               VALUES (:brand, :name, :yt, :news, :reddit, :sites, :max)
               ON CONFLICT (brand_id) DO UPDATE SET
                   segment_name = EXCLUDED.segment_name,
                   youtube_channel_keywords = EXCLUDED.youtube_channel_keywords,
                   news_sources = EXCLUDED.news_sources,
                   reddit_communities = EXCLUDED.reddit_communities,
                   website_urls = EXCLUDED.website_urls,
                   max_competitors_to_track = EXCLUDED.max_competitors_to_track""",
            {
                "brand": brand_id,
                "name": segment.segment_name,
                "yt": segment.youtube_channel_keywords,
                "news": segment.news_sources,
                "reddit": segment.reddit_communities,
                "sites": segment.website_urls,
                "max": segment.max_competitors_to_track,
            },
        )
        session.commit()
    return segment


@app.get("/brands/{brand_id}/market-segments")
async def get_market_segment(brand_id: str, kb_id: str = Depends(resolve_brand_scope)) -> MarketSegment | None:
    with get_session() as session:
        row = session.execute(
            "SELECT brand_id, segment_name, youtube_channel_keywords, news_sources, "
            "reddit_communities, website_urls, max_competitors_to_track "
            "FROM market_segment WHERE brand_id = :brand",
            {"brand": brand_id},
        ).mappings().first()
    return MarketSegment(**row) if row else None


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
    content = await file.read()
    dest.write_bytes(content)

    from app.workers.ingest import compute_file_id, ingest_file

    ingest_file.delay(brand_id, str(dest), source_kind)
    # file_id is content-addressed (compute_file_id), so the caller gets a
    # correlation id to poll GET .../sources with, without waiting on the
    # celery task to run and without the route writing to source_file itself
    # (that write stays ingest_file's job -- one write path, per client_view.py's
    # same discipline elsewhere in this codebase).
    content_hash = hashlib.sha256(content).hexdigest()
    file_id = compute_file_id(f"run:{brand_id}", content_hash)
    return {"status": "queued", "file_id": file_id}


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


@app.post("/brands/{brand_id}/collect-now")
async def collect_now(brand_id: str) -> dict:
    """Manual trigger for workers/data_collection.py's collect_all_for_brand
    (DATA_COLLECTION_QUICK_START.md §7's on-demand path) -- same task the
    nightly beat schedule (infra/celery_app.py) would otherwise queue."""
    from app.workers.data_collection import collect_all_for_brand

    task = collect_all_for_brand.delay(brand_id)
    return {"status": "queued", "task_id": task.id}


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


@app.get("/documents/{document_id}/export.docx")
async def export_document_docx(document_id: str) -> Response:
    # Ungated like every other document-review endpoint above (get_document,
    # approve, ...) -- a pre-existing, already-flagged gap (no session/login
    # layer yet, api-key scoping only covers the Step 4/5 KB/data-source
    # surfaces), not a new inconsistency introduced by adding this one.
    document = _load_document(document_id)
    if document is None:
        raise HTTPException(404, detail=f"no such document: {document_id}")
    buffer = build_docx(document)
    filename = f"{document.brand_id}-market-research.docx"
    return Response(
        content=buffer.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


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
    _save_approval_event(document_id, decision.decision, decision.approver_id, decision.note, checkpoint)
    return document


@app.get("/documents/{document_id}/approval-history")
async def get_approval_history(document_id: str) -> list[ApprovalEvent]:
    # current_approval_status is a query over this list, never a column a
    # reject-then-reapprove sequence could overwrite (step5_trust_boundary.md
    # Part C) -- /approval-gate above is the pre-Step-5 single-row view, kept
    # read-only for backward compat until every caller is repointed here.
    return _load_approval_history(document_id)


@app.post("/documents/{document_id}/rerun")
async def rerun_document(document_id: str) -> MarketResearchDocument:
    """New brand material was uploaded to address the rejection -- re-runs
    ingest/retrieval/synthesis from scratch, producing a new pending_approval
    document."""
    document = _load_document(document_id)
    if document is None:
        raise HTTPException(404, detail=f"no such document: {document_id}")
    if document.status != "rejected":
        raise HTTPException(409, detail=f"cannot rerun from {document.status}")

    from app.orchestration.section_runner import assemble_document, run_all_sections

    results = run_all_sections(document.brand_id)
    new_document = assemble_document(document.brand_id, results)
    _save_document(new_document)
    return new_document


@app.post("/documents/{document_id}/resubmit")
async def resubmit_document(document_id: str, payload: ResubmitPayload) -> MarketResearchDocument:
    """The rejection was about the write-up, not the evidence -- addressed via
    a strategic_note. Re-enters review without regenerating."""
    document = _load_document(document_id)
    if document is None:
        raise HTTPException(404, detail=f"no such document: {document_id}")
    if document.status != "rejected":
        raise HTTPException(409, detail=f"cannot resubmit from {document.status}")

    _save_approval_event(document_id, "resubmitted", payload.approver_id, payload.note, None)
    document.status = "pending_approval"
    _save_document(document)
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


@app.get("/documents/{document_id}/distribution-history")
async def get_distribution_history(document_id: str) -> list[DistributionEvent]:
    with get_session() as session:
        rows = session.execute(
            "SELECT id, document_id, channel, distributed_by, distributed_at "
            "FROM distribution_event WHERE document_id = :id ORDER BY distributed_at ASC",
            {"id": document_id},
        ).mappings().all()
    return [DistributionEvent(**row) for row in rows]


@app.post("/documents/{document_id}/distribution-links")
async def create_distribution_link(document_id: str, payload: DistributionLinkPayload) -> dict:
    # A client link is not an operator credential -- it authorizes exactly
    # this one document's read-only ClientMarketResearchView projection,
    # structurally, not by an if-check a future endpoint could forget.
    document = _load_document(document_id)
    if document is None:
        raise HTTPException(404, detail=f"no such document: {document_id}")
    if document.status != "approved":
        raise HTTPException(422, detail="cannot distribute before approval")

    link_id = f"link-{uuid4().hex[:12]}"
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    expires_at = datetime.now(UTC) + timedelta(days=payload.ttl_days)
    with get_session() as session:
        session.execute(
            """INSERT INTO distribution_link (id, document_id, token_hash, created_by, expires_at)
               VALUES (:id, :doc, :hash, :created_by, :expires)""",
            {
                "id": link_id,
                "doc": document_id,
                "hash": token_hash,
                "created_by": payload.created_by,
                "expires": expires_at,
            },
        )
        session.commit()
    _save_distribution_event(document_id, "client", payload.created_by)
    return {"id": link_id, "token": token, "expires_at": expires_at.isoformat()}


@app.get("/documents/{document_id}/distribution-links")
async def list_distribution_links(document_id: str) -> list[DistributionLink]:
    # Metadata only -- the token itself was never persisted (only its hash),
    # so there is no response shape that could leak it after creation.
    with get_session() as session:
        rows = session.execute(
            "SELECT id, document_id, created_by, expires_at, revoked, created_at "
            "FROM distribution_link WHERE document_id = :id ORDER BY created_at DESC",
            {"id": document_id},
        ).mappings().all()
    return [DistributionLink(**row) for row in rows]


@app.post("/distribution-links/{link_id}/revoke")
async def revoke_distribution_link(link_id: str) -> dict:
    with get_session() as session:
        result = session.execute(
            "UPDATE distribution_link SET revoked = TRUE WHERE id = :id", {"id": link_id}
        )
        session.commit()
    if result.rowcount == 0:
        raise HTTPException(404, detail=f"no such distribution link: {link_id}")
    return {"id": link_id, "revoked": True}


@app.get("/client/view/{token}")
async def client_view(token: str) -> ClientMarketResearchView:
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    with get_session() as session:
        row = session.execute(
            "SELECT document_id, revoked, expires_at FROM distribution_link WHERE token_hash = :h",
            {"h": token_hash},
        ).mappings().first()
    # 404, not 403, for anything a caller isn't authorized to know exists at
    # all -- never confirm a token ever existed (step5_trust_boundary.md
    # "existence must not leak").
    if row is None or row["revoked"] or row["expires_at"] < datetime.now(UTC):
        raise HTTPException(404)
    document = _load_document(row["document_id"])
    if document is None:
        raise HTTPException(404)
    return project_for_client(document)


@app.post("/core/staging/build")
async def trigger_staging_build(
    payload: StagingBuildPayload, user: User = Depends(current_user)  # noqa: B008 -- FastAPI DI idiom
) -> dict:
    from app.workers.core_ingest import build_staging

    build_staging.delay(payload.source_paths, payload.target_version)
    return {"status": "queued", "target_version": payload.target_version}


@app.get("/core/versions")
async def list_core_versions() -> list[KBVersion]:
    with get_session() as session:
        rows = session.execute(
            "SELECT kb_id, version, status, eval_gate_result, promoted_at, promoted_by "
            "FROM kb_version ORDER BY version DESC"
        ).mappings().all()
    return [KBVersion(**row) for row in rows]


@app.post("/core/staging/{version}/promotion-requests")
async def create_promotion_request(
    version: int,
    payload: PromotionRequestPayload,
    user: User = Depends(current_user),  # noqa: B008 -- FastAPI DI idiom
) -> dict:
    from app.eval.gate import evaluate_staging
    from app.eval.golden_runner import default_synthesis_runner

    staging_kb_id = f"core:market-intel@v{version}:staging"
    with get_session() as session:
        exists = session.execute(
            "SELECT 1 FROM kb_version WHERE kb_id = :kb", {"kb": staging_kb_id}
        ).first()
    if exists is None:
        raise HTTPException(404, detail=f"no staging build found for version {version}")

    golden_set = _load_golden_set()
    result = evaluate_staging(staging_kb_id, golden_set, run_synthesis_against=default_synthesis_runner)

    with get_session() as session:
        session.execute(
            "UPDATE kb_version SET eval_gate_result = (:r)::jsonb WHERE kb_id = :kb",
            {"r": result.model_dump_json(), "kb": staging_kb_id},
        )
        session.commit()

    if not result.passed:
        # Eval gate necessary, not sufficient (dev_guidelines.md): a failing
        # corpus is blocked here, before a human ever sees a /decide prompt.
        raise HTTPException(422, detail={"reason": "eval_gate_failed", "result": result.model_dump()})

    request_id = f"pr-v{version}-{uuid4().hex[:12]}"
    with get_session() as session:
        session.execute(
            """INSERT INTO promotion_request (id, kb_id, source_summary, requested_by, status)
               VALUES (:id, :kb, :summary, :user, 'pending')""",
            {"id": request_id, "kb": staging_kb_id, "summary": payload.source_summary, "user": user.id},
        )
        session.commit()

    return {
        "request_id": request_id,
        "kb_id": staging_kb_id,
        "status": "pending",
        "eval_result": result.model_dump(),
    }


@app.post("/core/promotion-requests/{request_id}/decide")
async def decide_promotion(
    request_id: str,
    payload: PromotionDecisionPayload,
    user: User = Depends(current_user),  # noqa: B008 -- FastAPI DI idiom
) -> dict:
    with get_session() as session:
        row = session.execute(
            "SELECT id, kb_id, status FROM promotion_request WHERE id = :id", {"id": request_id}
        ).mappings().first()
    if row is None:
        raise HTTPException(404, detail=f"no such promotion request: {request_id}")
    if row["status"] != "pending":
        raise HTTPException(409, detail=f"cannot decide a request already {row['status']}")

    if payload.decision == "rejected":
        with get_session() as session:
            session.execute(
                "UPDATE promotion_request SET status = 'rejected', reviewed_by = :user, reviewed_at = now() "
                "WHERE id = :id",
                {"user": user.id, "id": request_id},
            )
            session.execute(
                "UPDATE kb_version SET status = 'rejected' WHERE kb_id = :kb", {"kb": row["kb_id"]}
            )
            session.commit()
        return {"request_id": request_id, "decision": "rejected"}

    staging_kb_id = row["kb_id"]
    promoted_kb_id = staging_kb_id.removesuffix(":staging")
    # Atomic rename staging -> promoted: every chunk's kb_id flips in the same
    # transaction as the kb_version row, so no reader can observe a half-moved
    # corpus (P6: idempotent, all-or-nothing). kb_version.kb_id is the FK's
    # referenced side (ON UPDATE CASCADE, migration 0007) so renaming it here
    # automatically carries promotion_request.kb_id along -- update that row's
    # status separately, by id, since its kb_id will already have moved.
    with get_session() as session:
        session.execute(
            "UPDATE chunk SET kb_id = :new WHERE kb_id = :old", {"new": promoted_kb_id, "old": staging_kb_id}
        )
        session.execute(
            "UPDATE document_registry SET kb_id = :new WHERE kb_id = :old",
            {"new": promoted_kb_id, "old": staging_kb_id},
        )
        session.execute(
            """UPDATE kb_version SET kb_id = :new, status = 'promoted', promoted_by = :user, promoted_at = now()
               WHERE kb_id = :old""",
            {"new": promoted_kb_id, "user": user.id, "old": staging_kb_id},
        )
        session.execute(
            "UPDATE promotion_request SET status = 'approved', reviewed_by = :user, reviewed_at = now() "
            "WHERE id = :id",
            {"user": user.id, "id": request_id},
        )
        session.commit()

    return {"request_id": request_id, "decision": "approved", "kb_id": promoted_kb_id}


def _load_golden_set() -> list[GoldenCase]:
    with get_session() as session:
        rows = session.execute("SELECT id, topic, section, fixture_chunks FROM golden_case").mappings().all()
    return [GoldenCase(**row) for row in rows]


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


def _save_approval_event(
    document_id: str,
    decision: str,
    approver_id: str,
    note: str | None,
    checkpoint: QualityCheckpoint | None,
) -> None:
    import json

    with get_session() as session:
        session.execute(
            """INSERT INTO approval_event (document_id, decision, approver_id, note, checkpoint)
               VALUES (:document_id, :decision, :approver_id, :note, (:checkpoint)::jsonb)""",
            {
                "document_id": document_id,
                "decision": decision,
                "approver_id": approver_id,
                "note": note,
                "checkpoint": json.dumps(checkpoint.model_dump()) if checkpoint else None,
            },
        )
        session.commit()


def _load_approval_history(document_id: str) -> list[ApprovalEvent]:
    with get_session() as session:
        rows = session.execute(
            "SELECT id, document_id, decision, approver_id, note, checkpoint, decided_at "
            "FROM approval_event WHERE document_id = :id ORDER BY decided_at ASC",
            {"id": document_id},
        ).mappings().all()
    return [ApprovalEvent(**row) for row in rows]


def _save_distribution_event(document_id: str, channel: str, distributed_by: str) -> None:
    with get_session() as session:
        session.execute(
            """INSERT INTO distribution_event (document_id, channel, distributed_by)
               VALUES (:document_id, :channel, :distributed_by)""",
            {"document_id": document_id, "channel": channel, "distributed_by": distributed_by},
        )
        session.commit()


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
