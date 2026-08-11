import asyncio
import time
from collections.abc import Callable
from datetime import UTC, datetime

from celery.schedules import crontab

from app.infra.celery_app import celery_app
from app.infra.crypto import decrypt_api_key
from app.infra.db import get_session
from app.infra.pubsub import publish_status
from app.infra.rate_limit import DataSourceRateLimiter
from app.infra.settings import rate_limit_settings
from app.infra.telemetry import (
    collection_job_duration_seconds,
    data_collection_chunks_total,
    data_collection_error_rate,
)
from app.tools.web import get_web_tool


class DataCollectionError(Exception):
    def __init__(self, source: str, reason: str, retriable: bool = True):
        self.source = source
        self.reason = reason
        self.retriable = retriable
        super().__init__(reason)


CollectorFn = Callable[[str], int]  # brand_id -> item_count; raises DataCollectionError on failure


def _get_credential(brand_id: str, source: str) -> str | None:
    with get_session() as session:
        row = (
            session.execute(
                "SELECT encrypted_api_key FROM data_source_credential WHERE brand_id = :b AND source = :s",
                {"b": brand_id, "s": source},
            )
            .mappings()
            .first()
        )
    return decrypt_api_key(row["encrypted_api_key"]) if row else None


def _get_segment(brand_id: str) -> dict | None:
    with get_session() as session:
        row = (
            session.execute(
                "SELECT website_urls, max_competitors_to_track FROM market_segment WHERE brand_id = :b",
                {"b": brand_id},
            )
            .mappings()
            .first()
        )
    return dict(row) if row else None


def collect_competitor_sites(brand_id: str) -> int:
    """The one real, working connector in this pass -- crawls the brand's own
    market_segment.website_urls whitelist via WebTool (no API key needed,
    step5_trust_boundary.md Part D §5's confined-scope crawl). youtube/
    google_trends/newsapi below are pluggable stubs: wiring a real vendor
    client is mechanical (DATA_COLLECTION_QUICK_START.md's own Step 7
    migration note) but writing one against a key nobody has configured would
    be fictional, so it isn't done here (dev_guidelines.md: don't build the
    general case before the concrete need forces it)."""
    segment = _get_segment(brand_id)
    if not segment or not segment["website_urls"]:
        raise DataCollectionError("competitor_sites", "no market segment configured", retriable=False)

    limiter = DataSourceRateLimiter()
    if not limiter.check(brand_id, "competitor_sites", rate_limit_settings.default_per_hour):
        raise DataCollectionError("competitor_sites", "rate limit exceeded", retriable=True)

    web_tool = get_web_tool()
    urls = segment["website_urls"][: segment["max_competitors_to_track"]]

    async def _fetch_all() -> list:
        return [await web_tool.fetch(url) for url in urls]

    results = asyncio.run(_fetch_all())
    ok = [r for r in results if r.status == 200 and r.text]
    if not ok:
        raise DataCollectionError("competitor_sites", "all fetches failed", retriable=True)
    return len(ok)


def _unconfigured_source(source: str) -> CollectorFn:
    def _collector(brand_id: str) -> int:
        if _get_credential(brand_id, source) is None:
            raise DataCollectionError(source, "no credential configured", retriable=False)
        raise DataCollectionError(source, "connector not yet implemented", retriable=False)

    return _collector


_COLLECTORS: dict[str, CollectorFn] = {
    "competitor_sites": collect_competitor_sites,
    "youtube": _unconfigured_source("youtube"),
    "google_trends": _unconfigured_source("google_trends"),
    "newsapi": _unconfigured_source("newsapi"),
}


def _log_job_status(brand_id: str, source: str, status: str, reason: str | None, item_count: int) -> None:
    with get_session() as session:
        session.execute(
            """INSERT INTO collection_job_status (brand_id, source, status, reason, item_count, finished_at)
               VALUES (:b, :s, :status, :reason, :count, now())""",
            {"b": brand_id, "s": source, "status": status, "reason": reason, "count": item_count},
        )
        session.commit()


def _broadcast(brand_id: str, message: str, phase: str, item_count: int = 0) -> None:
    publish_status(
        brand_id,
        {
            "timestamp": datetime.now(UTC).isoformat(),
            "message": message,
            "phase": phase,
            "item_count": item_count,
        },
    )


@celery_app.task(name="app.workers.data_collection.collect_all_for_brand")
def collect_all_for_brand(brand_id: str) -> dict:
    """Orchestrates all data sources for a brand; degrades gracefully if any
    fail (P5) -- one source's failure never cascades to the others, and
    synthesis (Step 3) uses whatever data did come through. Broadcasts each
    phase transition over Redis pub/sub (api/websocket.py's live-run
    endpoint) so an operator watching the UI sees real progress, not silence
    until the whole job finishes."""
    _broadcast(brand_id, "Starting data collection", phase="queued")
    results: dict[str, dict] = {}
    total_items = 0
    for source, collector in _COLLECTORS.items():
        _broadcast(brand_id, f"Collecting {source}...", phase=source)
        started = time.monotonic()
        try:
            count = collector(brand_id)
            results[source] = {"status": "success", "item_count": count}
            _log_job_status(brand_id, source, "success", None, count)
            data_collection_chunks_total.labels(source=source).inc(count)
            data_collection_error_rate.labels(source=source).set(0.0)
            total_items += count
            _broadcast(brand_id, f"✓ {source}: {count} items", phase=source, item_count=count)
        except DataCollectionError as e:
            status = "retrying" if e.retriable else "failed"
            results[source] = {"status": status, "reason": e.reason, "retriable": e.retriable}
            _log_job_status(brand_id, source, status, e.reason, 0)
            data_collection_error_rate.labels(source=source).set(1.0)
            _broadcast(brand_id, f"✗ {source}: {e.reason}", phase=source)
        finally:
            collection_job_duration_seconds.labels(source=source).observe(time.monotonic() - started)
    _broadcast(brand_id, f"Collection complete -- {total_items} items", phase="completed", item_count=total_items)
    return results


@celery_app.task(name="app.workers.data_collection.collect_all_for_brand_batch")
def collect_all_for_brand_batch() -> list[str]:
    """Beat-scheduled fan-out (step6_production_operations.md §11's daily-5am
    entry) -- one collect_all_for_brand task per brand, queued independently
    so one brand's slow/rate-limited run never delays another's."""
    with get_session() as session:
        brand_ids = [row["id"] for row in session.execute("SELECT id FROM brand").mappings().all()]
    for brand_id in brand_ids:
        collect_all_for_brand.delay(brand_id)
    return brand_ids


celery_app.conf.beat_schedule = {
    **(celery_app.conf.beat_schedule or {}),
    "daily-data-collection-5am": {
        "task": "app.workers.data_collection.collect_all_for_brand_batch",
        "schedule": crontab(hour=5, minute=0),
    },
}
