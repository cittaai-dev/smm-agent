from fastapi.testclient import TestClient

from app.infra.db import get_session
from app.main import app
from app.workers.ingest import ingest_file


def _run_full_document(brand_id: str, client: TestClient) -> dict:
    with get_session() as session:
        session.execute(
            "INSERT INTO team_input (brand_id, section, text) VALUES (:b, 'business_goals', 'Grow.')",
            {"b": brand_id},
        )
        session.commit()
    return client.post(f"/brands/{brand_id}/research/run-all").json()


def _approved_document(brand_id: str, sample_file: str, client: TestClient) -> dict:
    ingest_file(brand_id=brand_id, file_path=sample_file)
    document = _run_full_document(brand_id, client)
    client.post(f"/documents/{document['id']}/approve", json={"approver_id": "u1", "decision": "approved"})
    return document


def test_distribution_blocked_before_approval(sample_file, fake_full_document_pipeline):
    ingest_file(brand_id="brand-unapproved", file_path=sample_file)
    client = TestClient(app)
    document = _run_full_document("brand-unapproved", client)

    resp = client.post(
        f"/documents/{document['id']}/distribution-links", json={"created_by": "u1"}
    )
    assert resp.status_code == 422


def test_client_view_excludes_internal_fields(sample_file, fake_full_document_pipeline):
    client = TestClient(app)
    document = _approved_document("brand-client-a", sample_file, client)

    link = client.post(
        f"/documents/{document['id']}/distribution-links", json={"created_by": "u1"}
    ).json()

    body = client.get(f"/client/view/{link['token']}").text
    assert "chunk_id" not in body
    assert "call_site_trace" not in body
    assert "rejection_reason" not in body
    assert "approver_id" not in body


def test_client_view_only_verified_or_team_provided_sections(sample_file, fake_full_document_pipeline):
    client = TestClient(app)
    document = _approved_document("brand-client-b", sample_file, client)

    link = client.post(
        f"/documents/{document['id']}/distribution-links", json={"created_by": "u1"}
    ).json()
    view = client.get(f"/client/view/{link['token']}").json()

    doc_sections = document["sections"]
    for section_id, claims in view["sections"].items():
        assert doc_sections[section_id]["status"] in ("verified", "team_provided")
        assert len(claims) > 0


def test_expired_and_revoked_links_both_404(sample_file, fake_full_document_pipeline):
    client = TestClient(app)
    document = _approved_document("brand-client-c", sample_file, client)

    expired = client.post(
        f"/documents/{document['id']}/distribution-links",
        json={"created_by": "u1", "ttl_days": -1},
    ).json()
    assert client.get(f"/client/view/{expired['token']}").status_code == 404

    live = client.post(
        f"/documents/{document['id']}/distribution-links", json={"created_by": "u1"}
    ).json()
    revoke = client.post(f"/distribution-links/{live['id']}/revoke")
    assert revoke.status_code == 200
    assert client.get(f"/client/view/{live['token']}").status_code == 404


def test_unknown_token_404s_same_as_expired():
    client = TestClient(app)
    resp = client.get("/client/view/not-a-real-token")
    assert resp.status_code == 404
