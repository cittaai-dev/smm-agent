import time

import redis

from app.infra.settings import db_settings

_client: redis.Redis | None = None


def get_client() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.Redis.from_url(db_settings.redis_url, decode_responses=True)
    return _client


class DataSourceRateLimiter:
    """Per-brand, per-source rate limiting -- prevents one brand's high-volume
    crawl from affecting another (step5_trust_boundary.md Part D §7). Redis,
    1-hour fixed buckets, same infra this project already depends on for
    Celery's broker -- no new operational dependency."""

    def __init__(self, client: redis.Redis | None = None):
        self._client = client or get_client()

    def check(self, brand_id: str, source: str, limit_per_hour: int) -> bool:
        """Returns True if the call is allowed under the current hour's
        budget, incrementing the counter either way (a blocked call still
        counts, so a caller that ignores a False return can't silently keep
        retrying past the limit)."""
        bucket = int(time.time() // 3600)
        key = f"ratelimit:{brand_id}:{source}:{bucket}"
        count = self._client.incr(key)
        if count == 1:
            self._client.expire(key, 3600)
        return count <= limit_per_hour
