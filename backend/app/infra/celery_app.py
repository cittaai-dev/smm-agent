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
celery_app.conf.task_routes = {
    "app.workers.ingest.*": {"queue": "ingest"},
    "app.workers.core_ingest.*": {"queue": "core"},
    "app.workers.ttl_sweep.*": {"queue": "ingest"},
    "app.workers.data_collection.*": {"queue": "ingest"},
}
