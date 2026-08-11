from collections import defaultdict
from collections.abc import Callable
from typing import TypeVar

from opentelemetry import trace
from prometheus_client import Counter, Gauge, Histogram
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

# step6_production_operations.md §8 -- the six pipeline.md §6 metrics, made
# visible. citation_rejection_rate/degraded_chunk_ratio are Gauges (a rolling
# rate a dashboard reads directly) fed by small in-process counters below,
# not derived from the raw Counters above at scrape time -- Prometheus rate()
# math belongs in Grafana for the Counters; these Gauges are the app's own
# rolling view, cheap enough to keep in memory per process.
citation_rejection_rate = Gauge("smm_citation_rejection_rate", "Rolling rejection rate", ["section"])
degraded_chunk_ratio = Gauge("smm_degraded_chunk_ratio", "Fraction ingested at L0 fallback", ["kb_id"])
call_site_total = Counter("smm_call_site_total", "LLM calls by site", ["site"])
run_duration_seconds = Histogram("smm_run_duration_seconds", "End-to-end run duration")
run_cost_usd = Histogram("smm_run_cost_usd", "Per-run cost")

# Step 6 Part B/C §9 -- data collection observability, one metric family per
# source so a single misbehaving connector doesn't hide in a blended average.
data_collection_chunks_total = Counter(
    "smm_data_collection_chunks_total", "Chunks collected by source", ["source"]
)
data_collection_error_rate = Gauge("smm_data_collection_error_rate", "Error rate per source", ["source"])
collection_job_duration_seconds = Histogram(
    "smm_collection_job_duration_seconds", "Collection job duration", ["source"]
)

_rejection_counts: dict[str, list[int]] = defaultdict(lambda: [0, 0])  # section -> [total, rejected]


def instrument_app(app) -> None:
    Instrumentator().instrument(app).expose(app)


def record_claim_verification(section: str, verified: bool) -> None:
    _claims_total.labels(section=section).inc()
    counts = _rejection_counts[section]
    counts[0] += 1
    if not verified:
        _claims_rejected.labels(section=section).inc()
        counts[1] += 1
    citation_rejection_rate.labels(section=section).set(counts[1] / counts[0])


def record_ingest_batch(kb_id: str, degraded_count: int, total_count: int) -> None:
    if total_count:
        degraded_chunk_ratio.labels(kb_id=kb_id).set(degraded_count / total_count)


def record_run(duration_s: float, usd_spent: float) -> None:
    run_duration_seconds.observe(duration_s)
    run_cost_usd.observe(usd_spent)


def traced_call_site(name: str) -> Callable[[F], F]:
    """Real OTel spans on the three call sites -- a different concern from
    orchestration/tracing.py's traced_llm_call, which enforces the P2
    call-count budget (raises if repair fires twice). Both decorators stack
    on the same functions: one is correctness enforcement, one is
    observability, neither replaces the other. Also increments
    smm_call_site_total -- pipeline.md §2's "exactly 3 call sites" is a
    production invariant here (a 4th distinct `site` label pages someone),
    not just a code-review checklist."""

    def decorator(fn: F) -> F:
        def wrapper(*args, **kwargs):
            call_site_total.labels(site=name).inc()
            with tracer.start_as_current_span(f"gen_ai.{name}"):
                return fn(*args, **kwargs)

        return wrapper  # type: ignore[return-value]

    return decorator
