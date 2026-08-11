import time
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")


class CircuitOpenError(RuntimeError):
    pass


class CircuitBreaker:
    """Wraps the OpenAI client call inside orchestration/llm.py -- an outage
    opens the circuit after `failure_threshold` consecutive failures, failing
    the next `reset_after_s` seconds fast instead of every concurrent Celery
    task separately timing out and piling up worker time."""

    def __init__(self, failure_threshold: int = 5, reset_after_s: int = 30):
        self._failures = 0
        self._threshold = failure_threshold
        self._reset_after = reset_after_s
        self._opened_at: float | None = None

    def call(self, fn: Callable[..., T], *args, **kwargs) -> T:
        if self._opened_at is not None and (time.monotonic() - self._opened_at) < self._reset_after:
            raise CircuitOpenError("LLM provider circuit open")
        try:
            result = fn(*args, **kwargs)
        except Exception:
            self._failures += 1
            if self._failures >= self._threshold:
                self._opened_at = time.monotonic()
            raise
        else:
            self._failures = 0
            self._opened_at = None
            return result

    def reset(self) -> None:
        """Test/ops escape hatch -- not called from production code paths."""
        self._failures = 0
        self._opened_at = None
