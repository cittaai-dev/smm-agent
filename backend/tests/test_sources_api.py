from fastapi.testclient import TestClient

from app.main import app
from app.workers.ingest import ingest_file


def test_list_sources_reflects_ingestion_status(sample_file):
    ingest_file(brand_id="brand-x", file_path=sample_file)

    client = TestClient(app)
    response = client.get("/brands/brand-x/sources")

    assert response.status_code == 200
    [source] = response.json()
    assert source["status"] == "ingested"
    assert source["source_kind"] == "brand_material"


def test_list_sources_empty_for_unknown_brand():
    client = TestClient(app)
    response = client.get("/brands/brand-nothing/sources")
    assert response.json() == []


def test_team_input_get_returns_null_before_any_submission():
    client = TestClient(app)
    response = client.get("/brands/brand-x/sections/business_goals/team-input")
    assert response.status_code == 200
    assert response.json() is None


def test_team_input_get_round_trips_after_put():
    client = TestClient(app)
    client.put(
        "/brands/brand-x/sections/business_goals/team-input",
        json={"text": "Grow DTC revenue 20% YoY.", "author": "jane@agency.com"},
    )

    response = client.get("/brands/brand-x/sections/business_goals/team-input")

    assert response.status_code == 200
    assert response.json() == {"text": "Grow DTC revenue 20% YoY.", "author": "jane@agency.com"}


def test_upload_source_accepts_explicit_source_kind(tmp_path, monkeypatch):
    captured = {}

    class _FakeDelay:
        def delay(self, brand_id, file_path, source_kind):
            captured["source_kind"] = source_kind

    monkeypatch.setattr("app.workers.ingest.ingest_file", _FakeDelay())

    client = TestClient(app)
    path = tmp_path / "competitor.pdf"
    path.write_bytes(b"%PDF-1.4 fake")
    with open(path, "rb") as f:
        response = client.post(
            "/brands/brand-x/sources",
            files={"file": ("competitor.pdf", f, "application/pdf")},
            data={"source_kind": "competitor_upload"},
        )

    assert response.status_code == 200
    assert captured["source_kind"] == "competitor_upload"
