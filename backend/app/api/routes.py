from pathlib import Path
from typing import Literal
from uuid import uuid4

from fastapi import FastAPI, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.requests import Request

from app.domain.deliverable import Deliverable
from app.infra.db import get_session
from app.infra.settings import api_settings
from app.orchestration.llm import LLMNotConfiguredError

app = FastAPI(title="smm-agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=api_settings.cors_origin_list,
    allow_methods=["*"],
    allow_headers=["*"],
)


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


@app.post("/brands/{brand_id}/sources")
async def upload_source(brand_id: str, file: UploadFile):
    _UPLOAD_DIR.mkdir(exist_ok=True)
    dest = _UPLOAD_DIR / f"{uuid4().hex}-{file.filename}"
    dest.write_bytes(await file.read())

    from app.workers.ingest import ingest_file

    ingest_file.delay(brand_id, str(dest))
    return {"status": "queued"}


@app.post("/brands/{brand_id}/research/run")
async def run_research(brand_id: str) -> Deliverable:
    from app.orchestration.graph import run_pipeline

    result = run_pipeline(brand_id=brand_id)
    _save_deliverable(result.deliverable)
    return result.deliverable


@app.get("/deliverables/{deliverable_id}")
async def get_deliverable(deliverable_id: str) -> Deliverable | None:
    return _load_deliverable(deliverable_id)


@app.post("/deliverables/{deliverable_id}/approve")
async def approve(deliverable_id: str, decision: ApprovalDecision) -> Deliverable:
    deliverable = _load_deliverable(deliverable_id)
    if deliverable is None:
        raise ValueError(f"no such deliverable: {deliverable_id}")
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
               ON CONFLICT (id) DO UPDATE SET status = EXCLUDED.status""",
            {
                "id": deliverable.id,
                "brand_id": deliverable.brand_id,
                "status": deliverable.status,
                "claims": json.dumps([c.model_dump() for c in deliverable.claims]),
                "trace": json.dumps(deliverable.call_site_trace),
            },
        )
        session.commit()
