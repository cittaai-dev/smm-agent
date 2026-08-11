import hashlib

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.api.deps import current_user, resolve_brand_scope
from app.infra.db import get_session


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


@pytest.fixture
def scoped_app() -> FastAPI:
    """Minimal harness app exercising the two deps directly -- api/routes.py
    doesn't wire them into any route yet (that's a follow-up PR), so this is
    what proves the deps themselves behave correctly."""
    app = FastAPI()

    @app.get("/brands/{brand_id}/probe")
    async def probe(kb_id: str = Depends(resolve_brand_scope)):
        return {"kb_id": kb_id}

    @app.get("/whoami")
    async def whoami(user=Depends(current_user)):
        return user.model_dump()

    return app


def test_granted_api_key_resolves_brand_scope(scoped_app):
    _seed_user_brand_grant("user-1", "brand-a", "secret-a")
    client = TestClient(scoped_app)
    resp = client.get("/brands/brand-a/probe", headers={"api-key": "secret-a"})
    assert resp.status_code == 200
    assert resp.json() == {"kb_id": "run:brand-a"}


def test_ungranted_brand_is_rejected(scoped_app):
    _seed_user_brand_grant("user-1", "brand-a", "secret-a")
    client = TestClient(scoped_app)
    resp = client.get("/brands/brand-b/probe", headers={"api-key": "secret-a"})
    assert resp.status_code == 403


def test_unknown_api_key_is_rejected(scoped_app):
    client = TestClient(scoped_app)
    resp = client.get("/brands/brand-a/probe", headers={"api-key": "not-a-real-key"})
    assert resp.status_code == 403


def test_current_user_resolves_real_identity(scoped_app):
    _seed_user_brand_grant("user-1", "brand-a", "secret-a")
    client = TestClient(scoped_app)
    resp = client.get("/whoami", headers={"api-key": "secret-a"})
    assert resp.status_code == 200
    assert resp.json()["id"] == "user-1"
    assert resp.json()["email"] == "user-1@example.com"
