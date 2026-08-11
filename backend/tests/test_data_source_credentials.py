import hashlib

from fastapi.testclient import TestClient

from app.infra.db import get_session
from app.main import app

client = TestClient(app)


def _seed_user_brand_grant(user_id: str, brand_id: str, api_key: str) -> None:
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    with get_session() as session:
        session.execute(
            "INSERT INTO app_user (id, email, role) VALUES (:id, :email, 'team_lead')",
            {"id": user_id, "email": f"{user_id}@example.com"},
        )
        session.execute(
            "INSERT INTO brand (id, owner_org_id, created_by) VALUES (:id, 'org-1', :creator)",
            {"id": brand_id, "creator": user_id},
        )
        session.execute(
            "INSERT INTO api_key (id, owner_user_id, key_hash) VALUES (:id, :user, :hash)",
            {"id": f"key-{api_key}", "user": user_id, "hash": key_hash},
        )
        session.execute(
            "INSERT INTO brand_grant (api_key_id, brand_id) VALUES (:key, :brand)",
            {"key": f"key-{api_key}", "brand": brand_id},
        )
        session.commit()


def test_credential_requires_brand_grant():
    resp = client.post(
        "/brands/brand-a/data-sources/credentials",
        json={"source": "newsapi", "api_key": "sk-secret"},
        headers={"api-key": "not-a-real-key"},
    )
    assert resp.status_code == 403


def test_credential_saved_encrypted_and_never_returned_plaintext():
    _seed_user_brand_grant("u1", "brand-a", "secret-a")

    resp = client.post(
        "/brands/brand-a/data-sources/credentials",
        json={"source": "newsapi", "api_key": "sk-secret-plaintext", "rate_limit_per_hour": 100},
        headers={"api-key": "secret-a"},
    )
    assert resp.status_code == 200

    listing = client.get("/brands/brand-a/data-sources/credentials", headers={"api-key": "secret-a"}).json()
    assert len(listing) == 1
    assert listing[0]["source"] == "newsapi"
    assert listing[0]["rate_limit_per_hour"] == 100
    assert "api_key" not in listing[0]
    assert "encrypted_api_key" not in listing[0]

    with get_session() as session:
        stored = session.execute(
            "SELECT encrypted_api_key FROM data_source_credential WHERE brand_id = 'brand-a'"
        ).scalar_one()
    assert stored != "sk-secret-plaintext"
    assert "sk-secret-plaintext" not in stored


def test_market_segment_round_trips_and_requires_grant():
    _seed_user_brand_grant("u2", "brand-b", "secret-b")

    put = client.put(
        "/brands/brand-b/market-segments",
        json={
            "segment_name": "fitness_wellness",
            "youtube_channel_keywords": ["vegan fitness"],
            "max_competitors_to_track": 5,
        },
        headers={"api-key": "secret-b"},
    )
    assert put.status_code == 200

    get = client.get("/brands/brand-b/market-segments", headers={"api-key": "secret-b"}).json()
    assert get["segment_name"] == "fitness_wellness"
    assert get["youtube_channel_keywords"] == ["vegan fitness"]
    assert get["max_competitors_to_track"] == 5

    unauthorized = client.get("/brands/brand-b/market-segments", headers={"api-key": "not-a-real-key"})
    assert unauthorized.status_code == 403
