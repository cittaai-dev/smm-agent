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
    assert response.json()["file_id"].startswith("file-")


def test_upload_source_returns_same_file_id_ingest_file_will_use(tmp_path, monkeypatch):
    # The route computes file_id independently of the celery task (it dispatches
    # async and can't wait on the task's result) -- this proves both derive the
    # same id from the same content, so a client polling by file_id actually
    # finds the row ingest_file eventually writes.
    class _FakeDelay:
        def delay(self, brand_id, file_path, source_kind):
            pass

    monkeypatch.setattr("app.workers.ingest.ingest_file", _FakeDelay())

    client = TestClient(app)
    path = tmp_path / "brand.txt"
    path.write_bytes(b"some brand material")
    with open(path, "rb") as f:
        response = client.post(
            "/brands/brand-y/sources",
            files={"file": ("brand.txt", f, "text/plain")},
        )

    import hashlib

    from app.workers.ingest import compute_file_id

    expected = compute_file_id("run:brand-y", hashlib.sha256(b"some brand material").hexdigest())
    assert response.json()["file_id"] == expected
