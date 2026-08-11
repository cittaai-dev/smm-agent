import json

import redis
import redis.asyncio as aioredis

from app.infra.settings import db_settings

_sync_client: redis.Redis | None = None


def _get_sync_client() -> redis.Redis:
    global _sync_client
    if _sync_client is None:
        _sync_client = redis.Redis.from_url(db_settings.redis_url, decode_responses=True)
    return _sync_client


def channel_for(brand_id: str) -> str:
    return f"live-run:{brand_id}:status"


def publish_status(brand_id: str, payload: dict) -> None:
    """Called from Celery workers (sync context, workers/data_collection.py) --
    publishes to the channel api/websocket.py's endpoint (a separate process)
    subscribes to. Redis, not an in-process dict, because worker and API never
    share memory (step6_production_operations.md Part B §4)."""
    _get_sync_client().publish(channel_for(brand_id), json.dumps(payload))


def get_async_client() -> aioredis.Redis:
    """A fresh async client per websocket connection -- FastAPI's event loop
    would block on the sync client's `listen()`, which defeats the point of
    an async endpoint serving many concurrent viewers."""
    return aioredis.from_url(db_settings.redis_url, decode_responses=True)
