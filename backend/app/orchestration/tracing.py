from collections.abc import Callable
from typing import Literal, TypeVar

CallSite = Literal["plan", "synthesize", "repair"]

_call_counts: dict[str, int] = {"plan": 0, "synthesize": 0, "repair": 0}

F = TypeVar("F", bound=Callable)


def reset_call_counts() -> None:
    for k in _call_counts:
        _call_counts[k] = 0


def call_counts() -> dict[str, int]:
    return dict(_call_counts)


def traced_llm_call(site: CallSite) -> Callable[[F], F]:
    """Enforces the 3-call-site query-path budget (P2): repair fires at most once
    per run. A future 4th call site anywhere on the query path should fail a test,
    not pass review — see docs/implement/dev_guidelines.md §7."""

    def decorator(fn: F) -> F:
        def wrapper(*args, **kwargs):
            _call_counts[site] += 1
            if site == "repair" and _call_counts[site] > 1:
                raise RuntimeError(
                    "repair budget exceeded — this is a bug, not a retry opportunity"
                )
            return fn(*args, **kwargs)

        return wrapper  # type: ignore[return-value]

    return decorator
