from fastapi.testclient import TestClient

from app.infra.db import get_session
from app.orchestration.graph import run_pipeline
from app.workers.ingest import ingest_file


def _chunk_count(brand_id: str) -> int:
    with get_session() as session:
        row = session.execute(
            "SELECT count(*) AS n FROM chunk WHERE kb_id = :kb", {"kb": f"run:{brand_id}"}
        ).mappings().first()
    return row["n"]


def test_citation_resolves(sample_file, fake_synthesize_grounded):
    ingest_file(brand_id="test-brand", file_path=sample_file)

    result = run_pipeline(brand_id="test-brand")

    assert result.deliverable.status == "pending_approval"
    assert result.deliverable.claims
    for claim in result.deliverable.claims:
        assert claim.verified
        with get_session() as session:
            row = session.execute(
                "SELECT lower(block_span) AS lo, upper(block_span) - 1 AS hi FROM chunk WHERE chunk_id = :cid",
                {"cid": claim.chunk_id},
            ).mappings().first()
        assert row is not None
        assert (row["lo"], row["hi"]) == claim.block_span


def test_fabricated_citation_rejected(sample_file, fake_synthesize_fabricated):
    ingest_file(brand_id="test-brand", file_path=sample_file)

    result = run_pipeline(brand_id="test-brand")

    # repair fired exactly once and fixed the citation -> nothing left rejected
    assert result.deliverable.call_site_trace["repair"] == 1
    assert all(c.verified for c in result.deliverable.claims)
    assert result.deliverable.status == "pending_approval"


def test_idempotent_reupload(sample_file):
    ingest_file(brand_id="test-brand", file_path=sample_file)
    count_1 = _chunk_count("test-brand")

    ingest_file(brand_id="test-brand", file_path=sample_file)
    count_2 = _chunk_count("test-brand")

    assert count_1 == count_2
    assert count_1 > 0


def test_ingest_is_not_deduped_across_brands(sample_file):
    # two different brands uploading byte-identical content must both ingest --
    # content_hash dedup is scoped to (kb_id, content_hash), not global.
    ingest_file(brand_id="brand-a", file_path=sample_file)
    ingest_file(brand_id="brand-b", file_path=sample_file)

    assert _chunk_count("brand-a") > 0
    assert _chunk_count("brand-b") > 0


def test_empty_synthesis_is_insufficient_grounding_not_pending_approval(
    sample_file, fake_synthesize_empty
):
    # zero claims must never read as "everything verified" (all() on an empty
    # list is vacuously True) -- this is the bug behind claims=[] + status
    # ending up approvable.
    ingest_file(brand_id="test-brand", file_path=sample_file)

    result = run_pipeline(brand_id="test-brand")

    assert result.deliverable.claims == []
    assert result.deliverable.status == "insufficient_grounding"
    # repair is pointless on an empty claim list (nothing to re-tag) -- must
    # not have burned a call site on it.
    assert result.deliverable.call_site_trace["repair"] == 0


def test_approve_rejects_zero_claim_deliverable():
    # The pipeline itself can no longer reach pending_approval with zero
    # claims (route_after_verify routes that to insufficient_grounding), so
    # this exercises the endpoint's own defensive check directly -- it's
    # belt-and-suspenders (P4/P5), not dead code: a deliverable's invariants
    # shouldn't depend solely on which code path produced the row.
    from app.main import app

    with get_session() as session:
        session.execute(
            """INSERT INTO deliverable (id, brand_id, status, claims, call_site_trace)
               VALUES ('del-x', 'test-brand', 'pending_approval', '[]'::jsonb, '{}'::jsonb)"""
        )
        session.commit()

    client = TestClient(app)
    approve_response = client.post(
        "/deliverables/del-x/approve",
        json={"approver_id": "team_lead", "decision": "approved"},
    )

    assert approve_response.status_code == 422


def test_approve_rejects_already_decided_deliverable(sample_file, fake_synthesize_grounded):
    ingest_file(brand_id="test-brand", file_path=sample_file)
    from app.main import app

    client = TestClient(app)
    run_response = client.post("/brands/test-brand/research/run")
    deliverable_id = run_response.json()["id"]

    first = client.post(
        f"/deliverables/{deliverable_id}/approve",
        json={"approver_id": "team_lead", "decision": "approved"},
    )
    assert first.status_code == 200

    second = client.post(
        f"/deliverables/{deliverable_id}/approve",
        json={"approver_id": "team_lead", "decision": "approved"},
    )
    assert second.status_code == 409


def test_cors_allows_configured_frontend_origin():
    from app.main import app

    client = TestClient(app)
    response = client.options(
        "/brands/acme/sources",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_run_research_without_llm_key_returns_clear_503(monkeypatch, sample_file):
    from app.infra.settings import llm_settings
    from app.main import app

    monkeypatch.setattr(llm_settings, "openai_api_key", "")
    ingest_file(brand_id="test-brand", file_path=sample_file)

    client = TestClient(app)
    response = client.post("/brands/test-brand/research/run")

    assert response.status_code == 503
    assert "SMM_LLM_OPENAI_API_KEY" in response.json()["detail"]


def test_approval_gate_blocks_default(sample_file, fake_synthesize_grounded):
    ingest_file(brand_id="test-brand", file_path=sample_file)

    from app.main import app

    client = TestClient(app)
    response = client.post("/brands/test-brand/research/run")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "pending_approval"
    assert body["status"] != "approved"
