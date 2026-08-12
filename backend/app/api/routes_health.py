import os
from datetime import UTC, datetime

from fastapi import APIRouter

from app.infra.db import get_session
from app.infra.rate_limit import get_client

health_router = APIRouter()

# Baked into the image at `docker build --build-arg GIT_SHA=$(git rev-parse
# --short HEAD)` (see Makefile) -- "unknown" outside Docker (bare `uvicorn`,
# pytest). Answers "is this container actually running the code I just
# merged" without SSHing in and diffing files -- a container rebuilt from a
# stale cached image is otherwise indistinguishable from a fresh one.
_GIT_SHA = os.environ.get("GIT_SHA", "unknown")

# The one real connector today (workers/data_collection.py's _COLLECTORS) plus
# the pluggable stubs -- reported here even while unconfigured so the
# dashboard shows "never_run", not silently omitting them (dev_guidelines.md:
# don't build the general case before the concrete need forces it, but do
# make the gap visible).
_SOURCES = ["competitor_sites", "youtube", "google_trends", "newsapi"]

_STALE_AFTER_HOURS = 24


@health_router.get("/health/live")
async def live() -> dict:
    return {"status": "alive", "git_sha": _GIT_SHA}


@health_router.get("/health/ready")
async def ready() -> dict:
    with get_session() as session:
        session.execute("SELECT 1")
    get_client().ping()
    return {"status": "ready"}


@health_router.get("/health/data-sources")
async def data_sources_health() -> dict:
    """Operational visibility over collection_job_status (migration 0008) --
    aggregated across brands, not scoped to one kb_id: this is an operator
    dashboard, not a tenant-facing endpoint."""
    status: dict[str, dict] = {}
    with get_session() as session:
        for source in _SOURCES:
            last = (
                session.execute(
                    """SELECT status, finished_at FROM collection_job_status
                       WHERE source = :s AND finished_at IS NOT NULL
                       ORDER BY finished_at DESC LIMIT 1""",
                    {"s": source},
                )
                .mappings()
                .first()
            )
            window = session.execute(
                """SELECT count(*) FILTER (WHERE status = 'success') AS ok,
                          count(*) AS total,
                          coalesce(sum(item_count), 0) AS items
                   FROM collection_job_status
                   WHERE source = :s AND started_at > now() - interval '24 hours'""",
                {"s": source},
            ).mappings().first()

            if last is None:
                status[source] = {
                    "last_run": None,
                    "staleness_hours": None,
                    "status": "never_run",
                    "error_rate_24h": 0.0,
                    "items_collected_24h": 0,
                }
                continue

            staleness_hours = (datetime.now(UTC) - last["finished_at"]).total_seconds() / 3600
            total = window["total"] or 0
            error_rate = 1 - (window["ok"] / total) if total else 0.0
            status[source] = {
                "last_run": last["finished_at"].isoformat(),
                "staleness_hours": round(staleness_hours, 2),
                "status": "stale" if staleness_hours > _STALE_AFTER_HOURS else "ok",
                "error_rate_24h": round(error_rate, 4),
                "items_collected_24h": window["items"],
            }
    return status
