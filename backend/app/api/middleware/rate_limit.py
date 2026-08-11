import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.infra.rate_limit import get_client
from app.infra.settings import api_rate_limit_settings

# Probes must never be rate-limited into a false "unhealthy" reading -- a
# kubelet hitting /health/live every few seconds is not abuse.
_EXEMPT_PATHS = {"/health/live", "/health/ready"}


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Redis-backed so the budget holds across replicas (step6_production_
    operations.md Part A §2) -- an in-process counter would let a caller
    reset their budget just by hitting a different pod."""

    def __init__(self, app, limit: int | None = None, window_s: int | None = None):
        super().__init__(app)
        self._limit = limit or api_rate_limit_settings.requests_per_window
        self._window = window_s or api_rate_limit_settings.window_seconds

    async def dispatch(self, request: Request, call_next):
        if request.url.path in _EXEMPT_PATHS:
            return await call_next(request)

        caller = request.headers.get("x-api-key", f"anon:{request.client.host if request.client else 'unknown'}")
        bucket = int(time.time() // self._window)
        key = f"apiratelimit:{caller}:{bucket}"

        client = get_client()
        count = client.incr(key)
        if count == 1:
            client.expire(key, self._window)

        if count > self._limit:
            return JSONResponse(status_code=429, content={"detail": "rate limit exceeded"})
        return await call_next(request)
