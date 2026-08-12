from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.api.deps import _lookup_api_key
from app.infra.db import get_session
from app.infra.pubsub import channel_for, get_async_client
from app.infra.settings import auth_settings

ws_router = APIRouter()


def _is_authorized_for_brand(api_key: str | None, brand_id: str) -> bool:
    """Same api-key -> brand_grant check as resolve_brand_scope (api/deps.py),
    adapted for a query param instead of a header -- browsers can't set
    custom headers on the WebSocket handshake."""
    if auth_settings.dev_bypass:
        return True
    if not api_key:
        return False
    resolved = _lookup_api_key(api_key)
    if resolved is None:
        return False
    api_key_id, _owner_user_id = resolved
    with get_session() as session:
        grant = session.execute(
            "SELECT 1 FROM brand_grant WHERE api_key_id = :k AND brand_id = :b",
            {"k": api_key_id, "b": brand_id},
        ).first()
    return grant is not None


@ws_router.websocket("/ws/live-run/{brand_id}/status")
async def live_run_status(websocket: WebSocket, brand_id: str) -> None:
    """Streams workers/data_collection.py's per-source status as it runs --
    push-based via Redis pub/sub (step6_production_operations.md Part B §4),
    not polling. Late joiners don't get history from this socket; GET
    /health/data-sources (backed by collection_job_status) is the
    already-persisted view for that."""
    api_key = websocket.query_params.get("api_key")
    if not _is_authorized_for_brand(api_key, brand_id):
        await websocket.close(code=4003)
        return

    client = get_async_client()
    pubsub = client.pubsub()
    # Subscribe before accepting -- a client observing the handshake complete
    # must be guaranteed the subscription is already live, or a status
    # published in the gap between accept() and subscribe() would be lost
    # (Redis pub/sub has no backlog for a subscriber that wasn't listening yet).
    await pubsub.subscribe(channel_for(brand_id))
    await websocket.accept()
    try:
        async for message in pubsub.listen():
            if message["type"] != "message":
                continue
            await websocket.send_text(message["data"])
    except WebSocketDisconnect:
        pass
    finally:
        await pubsub.unsubscribe(channel_for(brand_id))
        await pubsub.aclose()
        await client.aclose()
