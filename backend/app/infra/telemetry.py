from collections.abc import Callable
from typing import TypeVar

from opentelemetry import trace
from prometheus_client import Counter
from prometheus_fastapi_instrumentator import Instrumentator

tracer = trace.get_tracer("smm-agent")

F = TypeVar("F", bound=Callable)

# Per-section, not global -- a global rate would hide that e.g. brand_overview
# (union, hybrid+reranked) and swot (synthesis_only, derived citations) can
# have very different baseline rejection rates for entirely legitimate
# reasons. This is also the metric that tells you, once Step 4's Core lands,
# whether BRIDGE retrieval is actually working rather than a guess.
_claims_total = Counter("smm_claims_total", "Claims passed through a verifier", ["section"])
_claims_rejected = Counter("smm_claims_rejected_total", "Claims rejected by a verifier", ["section"])


def instrument_app(app) -> None:
    Instrumentator().instrument(app).expose(app)


def record_claim_verification(section: str, verified: bool) -> None:
    _claims_total.labels(section=section).inc()
    if not verified:
        _claims_rejected.labels(section=section).inc()


def traced_call_site(name: str) -> Callable[[F], F]:
    """Real OTel spans on the three call sites -- a different concern from
    orchestration/tracing.py's traced_llm_call, which enforces the P2
    call-count budget (raises if repair fires twice). Both decorators stack
    on the same functions: one is correctness enforcement, one is
    observability, neither replaces the other."""

    def decorator(fn: F) -> F:
        def wrapper(*args, **kwargs):
            with tracer.start_as_current_span(f"gen_ai.{name}"):
                return fn(*args, **kwargs)

        return wrapper  # type: ignore[return-value]

    return decorator
