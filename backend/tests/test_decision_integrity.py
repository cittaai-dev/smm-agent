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


def test_reject_then_resubmit_then_reapprove_preserves_all_events(sample_file, fake_full_document_pipeline):
    ingest_file(brand_id="brand-decisions", file_path=sample_file)
    client = TestClient(app)
    document = _run_full_document("brand-decisions", client)
    document_id = document["id"]

    reject = client.post(
        f"/documents/{document_id}/approve",
        json={"approver_id": "u1", "decision": "rejected", "note": "missing evidence"},
    )
    assert reject.status_code == 200

    resubmit = client.post(
        f"/documents/{document_id}/resubmit",
        json={"approver_id": "u2", "note": "brand uploaded updated deck"},
    )
    assert resubmit.status_code == 200
    assert resubmit.json()["status"] == "pending_approval"

    approve = client.post(
        f"/documents/{document_id}/approve",
        json={"approver_id": "u2", "decision": "approved"},
    )
    assert approve.status_code == 200

    history = client.get(f"/documents/{document_id}/approval-history").json()
    assert [e["decision"] for e in history] == ["rejected", "resubmitted", "approved"]
    assert [e["approver_id"] for e in history] == ["u1", "u2", "u2"]


def test_rerun_requires_rejected_status(sample_file, fake_full_document_pipeline):
    ingest_file(brand_id="brand-approved", file_path=sample_file)
    client = TestClient(app)
    document = _run_full_document("brand-approved", client)
    document_id = document["id"]
    client.post(f"/documents/{document_id}/approve", json={"approver_id": "u1", "decision": "approved"})

    resp = client.post(f"/documents/{document_id}/rerun")
    assert resp.status_code == 409


def test_resubmit_requires_rejected_status(sample_file, fake_full_document_pipeline):
    ingest_file(brand_id="brand-pending", file_path=sample_file)
    client = TestClient(app)
    document = _run_full_document("brand-pending", client)
    document_id = document["id"]

    resp = client.post(f"/documents/{document_id}/resubmit", json={"approver_id": "u1", "note": "fixed"})
    assert resp.status_code == 409


def test_rerun_reenters_pending_approval(sample_file, fake_full_document_pipeline):
    ingest_file(brand_id="brand-rerun", file_path=sample_file)
    client = TestClient(app)
    document = _run_full_document("brand-rerun", client)
    document_id = document["id"]
    client.post(f"/documents/{document_id}/approve", json={"approver_id": "u1", "decision": "rejected"})

    resp = client.post(f"/documents/{document_id}/rerun")
    assert resp.status_code == 200
    assert resp.json()["status"] == "pending_approval"
    assert resp.json()["id"] == document_id
