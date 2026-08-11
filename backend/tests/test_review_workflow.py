from fastapi.testclient import TestClient

from app.infra.db import get_session
from app.main import app
from app.workers.ingest import ingest_file

_ALL_SECTIONS = {
    "brand_overview", "business_goals", "target_audience", "customer_needs",
    "market_overview", "competitor_analysis", "swot", "positioning_usp",
    "platform_analysis", "trends_opportunities", "key_takeaways",
}


def _run_full_document(brand_id: str, client: TestClient, fake_full_document_pipeline) -> dict:
    with get_session() as session:
        session.execute(
            "INSERT INTO team_input (brand_id, section, text) VALUES (:b, 'business_goals', 'Grow.')",
            {"b": brand_id},
        )
        session.commit()
    return client.post(f"/brands/{brand_id}/research/run-all").json()


def test_approve_blocked_by_failed_checkpoint_even_with_claims(sample_file, fake_synthesize_grounded):
    # brand_overview alone has claims (passes the zero-claims gate) but the
    # document is nowhere near checkpoint-complete (missing target_audience
    # personas, competitor data, key_takeaways linkage) -- the checkpoint gate
    # must catch what the older zero-claims gate alone would miss.
    ingest_file(brand_id="brand-partial", file_path=sample_file)
    client = TestClient(app)
    run = client.post("/brands/brand-partial/research/run-all")
    document = run.json()
    assert document["sections"]["brand_overview"]["claims"]  # sanity: not zero-claims

    response = client.post(
        f"/documents/{document['id']}/approve",
        json={"approver_id": "team_lead", "decision": "approved"},
    )

    assert response.status_code == 422
    assert response.json()["detail"]["reason"] == "quality_checkpoint_failed"
    assert response.json()["detail"]["checkpoint"]["all_sections_filled"] is True


def test_approve_succeeds_and_records_approval_gate_when_checkpoint_passes(
    sample_file, fake_full_document_pipeline
):
    ingest_file(brand_id="brand-full", file_path=sample_file)
    client = TestClient(app)
    document = _run_full_document("brand-full", client, fake_full_document_pipeline)

    response = client.post(
        f"/documents/{document['id']}/approve",
        json={"approver_id": "team_lead", "decision": "approved"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "approved"

    with get_session() as session:
        row = session.execute(
            "SELECT approver_id, decision, checkpoint FROM approval_gate WHERE document_id = :id",
            {"id": document["id"]},
        ).mappings().first()
    assert row["approver_id"] == "team_lead"
    assert row["decision"] == "approved"
    assert row["checkpoint"]["all_sections_filled"] is True


def test_distribute_blocked_before_approval(sample_file, fake_synthesize_grounded):
    ingest_file(brand_id="brand-partial", file_path=sample_file)
    client = TestClient(app)
    document = client.post("/brands/brand-partial/research/run-all").json()

    response = client.post(
        f"/documents/{document['id']}/distribute",
        json={"internal": True, "client": False},
    )

    assert response.status_code == 422


def test_distribute_succeeds_after_approval(sample_file, fake_full_document_pipeline):
    ingest_file(brand_id="brand-full", file_path=sample_file)
    client = TestClient(app)
    document = _run_full_document("brand-full", client, fake_full_document_pipeline)
    client.post(
        f"/documents/{document['id']}/approve",
        json={"approver_id": "team_lead", "decision": "approved"},
    )

    response = client.post(
        f"/documents/{document['id']}/distribute",
        json={"internal": True, "client": False},
    )

    assert response.status_code == 200
    assert response.json()["internal"] is True
    assert response.json()["client"] is False

    get_response = client.get(f"/documents/{document['id']}/distribution")
    assert get_response.json()["internal"] is True


def test_add_note_round_trips_via_api(sample_file, fake_synthesize_grounded):
    ingest_file(brand_id="brand-partial", file_path=sample_file)
    client = TestClient(app)
    document = client.post("/brands/brand-partial/research/run-all").json()

    response = client.post(
        f"/documents/{document['id']}/notes",
        json={"section": "brand_overview", "text": "Double-check founding year.", "author": "jane@agency.com"},
    )
    assert response.status_code == 200

    list_response = client.get(f"/documents/{document['id']}/notes")
    [note] = list_response.json()
    assert note["text"] == "Double-check founding year."
    assert note["section"] == "brand_overview"


def test_add_note_rejects_unknown_section(sample_file, fake_synthesize_grounded):
    ingest_file(brand_id="brand-partial", file_path=sample_file)
    client = TestClient(app)
    document = client.post("/brands/brand-partial/research/run-all").json()

    response = client.post(
        f"/documents/{document['id']}/notes",
        json={"section": "not-a-real-section", "text": "x", "author": "jane@agency.com"},
    )

    assert response.status_code == 422


def test_add_note_rejects_unknown_document():
    client = TestClient(app)
    response = client.post(
        "/documents/does-not-exist/notes",
        json={"section": "brand_overview", "text": "x", "author": "jane@agency.com"},
    )
    assert response.status_code == 404


def test_checkpoint_preview_matches_what_approve_would_enforce(sample_file, fake_synthesize_grounded):
    ingest_file(brand_id="brand-partial", file_path=sample_file)
    client = TestClient(app)
    document = client.post("/brands/brand-partial/research/run-all").json()

    preview = client.get(f"/documents/{document['id']}/checkpoint")
    assert preview.status_code == 200
    assert preview.json()["all_sections_filled"] is True
    assert preview.json()["personas_grounded"] is False  # no persona extraction wired for this fixture

    approve = client.post(
        f"/documents/{document['id']}/approve",
        json={"approver_id": "team_lead", "decision": "approved"},
    )
    assert approve.json()["detail"]["checkpoint"] == preview.json()


def test_checkpoint_preview_rejects_unknown_document():
    client = TestClient(app)
    response = client.get("/documents/does-not-exist/checkpoint")
    assert response.status_code == 404


def test_approval_gate_round_trips_decision_provenance(sample_file, fake_full_document_pipeline):
    ingest_file(brand_id="brand-full", file_path=sample_file)
    client = TestClient(app)
    document = _run_full_document("brand-full", client, fake_full_document_pipeline)

    before = client.get(f"/documents/{document['id']}/approval-gate")
    assert before.status_code == 200
    assert before.json() is None  # no decision yet

    client.post(
        f"/documents/{document['id']}/approve",
        json={"approver_id": "team_lead", "decision": "approved", "note": "Looks solid."},
    )

    after = client.get(f"/documents/{document['id']}/approval-gate").json()
    assert after["approver_id"] == "team_lead"
    assert after["decision"] == "approved"
    assert after["note"] == "Looks solid."
    assert after["checkpoint"]["all_sections_filled"] is True
    assert after["decided_at"] is not None
