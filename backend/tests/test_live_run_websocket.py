import hashlib
import json

from fastapi.testclient import TestClient

from app.infra.db import get_session
from app.infra.pubsub import publish_status
from app.infra.settings import auth_settings
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


def test_unauthorized_connection_is_closed():
    # Starlette's TestClient raises WebSocketDisconnect on __enter__ itself
    # once the server closes before ever accepting the handshake.
    import pytest
    from starlette.websockets import WebSocketDisconnect

    with pytest.raises(WebSocketDisconnect) as exc_info, client.websocket_connect(
        "/ws/live-run/brand-ws-1/status?api_key=nope"
    ):
        pass
    assert exc_info.value.code == 4003


def test_authorized_connection_receives_broadcast_status():
    _seed_user_brand_grant("u-ws", "brand-ws-2", "secret-ws")

    with client.websocket_connect("/ws/live-run/brand-ws-2/status?api_key=secret-ws") as ws:
        publish_status(
            "brand-ws-2",
            {"timestamp": "2026-01-01T00:00:00Z", "message": "Starting", "phase": "queued", "item_count": 0},
        )
        received = json.loads(ws.receive_text())

    assert received["phase"] == "queued"
    assert received["message"] == "Starting"


def test_broadcast_scoped_per_brand():
    _seed_user_brand_grant("u-ws-2", "brand-ws-3", "secret-ws-3")

    with client.websocket_connect("/ws/live-run/brand-ws-3/status?api_key=secret-ws-3") as ws:
        publish_status("brand-other", {"timestamp": "x", "message": "not for you", "phase": "queued"})
        publish_status("brand-ws-3", {"timestamp": "x", "message": "for you", "phase": "queued"})
        received = json.loads(ws.receive_text())

    assert received["message"] == "for you"


def test_dev_bypass_accepts_with_no_seeded_grant():
    auth_settings.dev_bypass = True
    try:
        with client.websocket_connect("/ws/live-run/never-seeded-brand/status?api_key=whatever") as ws:
            publish_status(
                "never-seeded-brand",
                {"timestamp": "x", "message": "bypassed", "phase": "queued"},
            )
            received = json.loads(ws.receive_text())
        assert received["message"] == "bypassed"
    finally:
        auth_settings.dev_bypass = False
