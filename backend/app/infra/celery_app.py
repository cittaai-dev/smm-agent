from celery import Celery

from app.infra.settings import db_settings

celery_app = Celery(
    "smm_agent",
    broker=db_settings.redis_url,
    backend=db_settings.redis_url,
    include=[
        "app.workers.ingest",
        "app.workers.core_ingest",
        "app.workers.ttl_sweep",
        "app.workers.data_collection",
    ],
)
celery_app.conf.task_default_queue = "default"
# Ingest is throughput-bound (many files, batchable); generation (once it has
# its own async call sites, e.g. Step 3's SSE-driven Plan/Synthesize) is
# latency-bound (a user waiting on a response) -- separate queues so scaling
# one doesn't starve the other (dual-kb.md's "separate deploys" principle).
# core is its own queue too: staging builds run for hours against dozens of
# curated sources, a very different profile from a single brand file upload,
# and must never be starved behind (or starve) the brand ingest queue.
# data_collection gets its own queue too (step6_production_operations.md
# Part B §3): outbound calls to third-party sources (rate-limited, retried,
# minutes-long) are a different latency profile from a single file upload,
# and a slow/rate-limited connector must never delay a Team Lead's own
# document upload sitting in the same queue.
celery_app.conf.task_routes = {
    "app.workers.ingest.*": {"queue": "ingest"},
    "app.workers.core_ingest.*": {"queue": "core"},
    "app.workers.ttl_sweep.*": {"queue": "ingest"},
    "app.workers.data_collection.*": {"queue": "data_collection"},
}
