import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route

from app.api.middleware.rate_limit import RateLimitMiddleware
from app.domain.cost import CostBudget, CostBudgetExceeded, RunCostTracker
from app.infra.circuit_breaker import CircuitBreaker, CircuitOpenError
from app.infra.db import get_session
from app.main import app
from app.orchestration.graph import run_pipeline
from app.workers.ingest import ingest_file

# --- Cost budgets ------------------------------------------------------


def test_cost_tracker_raises_once_budget_exceeded():
    tracker = RunCostTracker(CostBudget(max_usd_per_run=0.01, max_tokens_per_run=1_000_000))
    with pytest.raises(CostBudgetExceeded):
        tracker.record(tokens=100, usd=0.02)


def test_cost_budget_stops_run_before_overspend(sample_file, monkeypatch):
    from app.domain.retrieval import RetrievalPlan

    def _fake_plan_over_budget(section, brand_id, cost_tracker=None):
        cost_tracker.record(tokens=1_000_000, usd=999.0)
        return RetrievalPlan(sub_queries=["brand overview"], k_per_query=8)

    ingest_file(brand_id="brand-cost", file_path=sample_file)
    monkeypatch.setattr("app.orchestration.llm.call_plan", _fake_plan_over_budget)

    result = run_pipeline(brand_id="brand-cost", budget=CostBudget(max_usd_per_run=0.01))

    assert result.deliverable.status == "insufficient_grounding"
    assert result.deliverable.reason == "cost_budget_exceeded"


# --- Circuit breaker -----------------------------------------------------


def test_circuit_breaker_opens_after_threshold():
    breaker = CircuitBreaker(failure_threshold=3, reset_after_s=30)

    def _boom():
        raise RuntimeError("provider down")

    for _ in range(3):
        with pytest.raises(RuntimeError):
            breaker.call(_boom)

    with pytest.raises(CircuitOpenError):
        breaker.call(_boom)


def test_circuit_open_routes_run_to_insufficient_grounding(sample_file, fake_plan, monkeypatch):
    ingest_file(brand_id="brand-circuit", file_path=sample_file)

    def _fake_synthesize_provider_down(section, context, cost_tracker=None):
        raise CircuitOpenError("LLM provider circuit open")

    monkeypatch.setattr("app.orchestration.llm.call_synthesize", _fake_synthesize_provider_down)

    result = run_pipeline(brand_id="brand-circuit")

    assert result.deliverable.status == "insufficient_grounding"
    assert result.deliverable.reason == "llm_provider_unavailable"


# --- API rate limit middleware -------------------------------------------


def test_rate_limit_returns_429_not_5xx():
    async def _ok(request):
        return PlainTextResponse("ok")

    test_app = Starlette(routes=[Route("/ping", _ok)])
    test_app.add_middleware(RateLimitMiddleware, limit=3, window_s=60)
    client = TestClient(test_app)
    api_key = f"test-{uuid.uuid4().hex[:8]}"

    statuses = [client.get("/ping", headers={"x-api-key": api_key}).status_code for _ in range(5)]

    assert 429 in statuses
    assert all(s in (200, 429) for s in statuses)


def test_rate_limit_scoped_per_caller():
    async def _ok(request):
        return PlainTextResponse("ok")

    test_app = Starlette(routes=[Route("/ping", _ok)])
    test_app.add_middleware(RateLimitMiddleware, limit=1, window_s=60)
    client = TestClient(test_app)
    key_a, key_b = f"a-{uuid.uuid4().hex[:8]}", f"b-{uuid.uuid4().hex[:8]}"

    assert client.get("/ping", headers={"x-api-key": key_a}).status_code == 200
    assert client.get("/ping", headers={"x-api-key": key_a}).status_code == 429
    assert client.get("/ping", headers={"x-api-key": key_b}).status_code == 200


# --- Health endpoints ------------------------------------------------------


def test_health_live_and_ready():
    client = TestClient(app)
    assert client.get("/health/live").json() == {"status": "alive"}
    assert client.get("/health/ready").json() == {"status": "ready"}


def test_health_data_sources_never_run_when_empty():
    client = TestClient(app)
    body = client.get("/health/data-sources").json()
    assert body["youtube"] == {
        "last_run": None,
        "staleness_hours": None,
        "status": "never_run",
        "error_rate_24h": 0.0,
        "items_collected_24h": 0,
    }


def test_health_data_sources_shows_staleness():
    with get_session() as session:
        session.execute(
            """INSERT INTO collection_job_status (brand_id, source, status, item_count, finished_at)
               VALUES ('brand-h', 'youtube', 'success', 5, :finished)""",
            {"finished": datetime.now(UTC) - timedelta(hours=12)},
        )
        session.commit()

    client = TestClient(app)
    body = client.get("/health/data-sources").json()
    assert body["youtube"]["status"] == "ok"
    assert body["youtube"]["staleness_hours"] >= 12

    with get_session() as session:
        session.execute(
            "UPDATE collection_job_status SET finished_at = :finished WHERE source = 'youtube'",
            {"finished": datetime.now(UTC) - timedelta(hours=48)},
        )
        session.commit()

    body = client.get("/health/data-sources").json()
    assert body["youtube"]["status"] == "stale"
