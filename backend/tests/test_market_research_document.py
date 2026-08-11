from fastapi.testclient import TestClient

from app.infra.db import get_session
from app.main import app
from app.workers.ingest import ingest_file

_ALL_SECTIONS = {
    "brand_overview", "business_goals", "target_audience", "customer_needs",
    "market_overview", "competitor_analysis", "swot", "positioning_usp",
    "platform_analysis", "trends_opportunities", "key_takeaways",
}
_CORE_GATED = {"market_overview", "competitor_analysis", "platform_analysis", "trends_opportunities"}


def test_full_document_run_produces_all_sections_and_is_approvable(
    sample_file, fake_full_document_pipeline
):
    ingest_file(brand_id="brand-full", file_path=sample_file)
    with get_session() as session:
        session.execute(
            """INSERT INTO team_input (brand_id, section, text)
               VALUES ('brand-full', 'business_goals', 'Grow DTC revenue 20% YoY.')"""
        )
        session.commit()

    client = TestClient(app)
    run_response = client.post("/brands/brand-full/research/run-all")
    assert run_response.status_code == 200
    document = run_response.json()

    assert set(document["sections"].keys()) == _ALL_SECTIONS
    assert document["status"] == "pending_approval"

    for section_id in ("brand_overview", "target_audience", "customer_needs"):
        assert document["sections"][section_id]["status"] == "verified"
        assert document["sections"][section_id]["claims"]

    assert document["sections"]["business_goals"]["status"] == "team_provided"

    for section_id in _CORE_GATED:
        assert document["sections"][section_id]["status"] == "insufficient_evidence"
        assert document["sections"][section_id]["claims"] == []

    # swot/positioning_usp synthesize from the fully-available brand-only
    # sections; key_takeaways synthesizes from swot+positioning_usp even
    # though platform_analysis/trends_opportunities are Core-gated (cascading
    # only on *total* unavailability, not on any single missing dep).
    for section_id in ("swot", "positioning_usp", "key_takeaways"):
        assert document["sections"][section_id]["status"] == "verified", section_id
        assert document["sections"][section_id]["claims"], section_id

    # Full round trip through GET, matching what the review page would fetch.
    get_response = client.get(f"/documents/{document['id']}")
    assert get_response.status_code == 200
    assert get_response.json()["sections"].keys() == document["sections"].keys()

    approve_response = client.post(
        f"/documents/{document['id']}/approve",
        json={"approver_id": "team_lead", "decision": "approved"},
    )
    assert approve_response.status_code == 200
    assert approve_response.json()["status"] == "approved"


def test_document_with_nothing_ingested_is_insufficient_grounding_and_unapprovable():
    client = TestClient(app)
    run_response = client.post("/brands/brand-empty/research/run-all")
    document = run_response.json()

    assert document["status"] == "insufficient_grounding"

    approve_response = client.post(
        f"/documents/{document['id']}/approve",
        json={"approver_id": "team_lead", "decision": "approved"},
    )
    assert approve_response.status_code == 409


def test_document_approve_rejects_unknown_id():
    client = TestClient(app)
    response = client.post(
        "/documents/does-not-exist/approve",
        json={"approver_id": "team_lead", "decision": "approved"},
    )
    assert response.status_code == 404
