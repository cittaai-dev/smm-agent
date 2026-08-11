from app.infra.db import get_session
from app.workers import data_collection
from app.workers.data_collection import (
    DataCollectionError,
    collect_all_for_brand,
    collect_competitor_sites,
)


def test_collect_competitor_sites_without_segment_is_a_degradable_failure():
    try:
        collect_competitor_sites("brand-no-segment")
        raise AssertionError("expected DataCollectionError")
    except DataCollectionError as e:
        assert e.source == "competitor_sites"
        assert e.retriable is False


def test_collect_all_for_brand_continues_after_one_source_fails(monkeypatch):
    def _always_fails(brand_id: str) -> int:
        raise DataCollectionError("competitor_sites", "simulated failure", retriable=True)

    def _always_succeeds(brand_id: str) -> int:
        return 5

    monkeypatch.setitem(data_collection._COLLECTORS, "competitor_sites", _always_fails)
    monkeypatch.setitem(data_collection._COLLECTORS, "newsapi", _always_succeeds)

    result = collect_all_for_brand("brand-mixed")

    assert result["competitor_sites"]["status"] == "retrying"
    assert result["newsapi"]["status"] == "success"
    assert result["newsapi"]["item_count"] == 5


def test_collect_all_for_brand_logs_append_only_job_status(monkeypatch):
    def _fails(brand_id: str) -> int:
        raise DataCollectionError("youtube", "no credential configured", retriable=False)

    monkeypatch.setitem(data_collection._COLLECTORS, "youtube", _fails)

    collect_all_for_brand("brand-log")
    collect_all_for_brand("brand-log")

    with get_session() as session:
        rows = session.execute(
            "SELECT status, reason FROM collection_job_status WHERE brand_id = 'brand-log' AND source = 'youtube'"
        ).mappings().all()
    assert len(rows) == 2
    assert all(r["status"] == "failed" for r in rows)


def test_encrypted_credentials_never_appear_in_error_reason():
    from app.infra.crypto import encrypt_api_key

    with get_session() as session:
        session.execute(
            "INSERT INTO data_source_credential (brand_id, source, encrypted_api_key) "
            "VALUES ('brand-cred', 'youtube', :key)",
            {"key": encrypt_api_key("sk-super-secret")},
        )
        session.commit()

    try:
        from app.workers.data_collection import _unconfigured_source

        _unconfigured_source("youtube")("brand-cred")
        raise AssertionError("expected DataCollectionError")
    except DataCollectionError as e:
        assert "sk-super-secret" not in str(e)
        assert "sk-super-secret" not in e.reason
