from celery import Celery

from app.infra.settings import db_settings

celery_app = Celery(
    "smm_agent",
    broker=db_settings.redis_url,
    backend=db_settings.redis_url,
    include=["app.workers.ingest"],
)
celery_app.conf.task_default_queue = "default"
# Ingest is throughput-bound (many files, batchable); generation (once it has
# its own async call sites, e.g. Step 3's SSE-driven Plan/Synthesize) is
# latency-bound (a user waiting on a response) -- separate queues so scaling
# one doesn't starve the other (dual-kb.md's "separate deploys" principle).
celery_app.conf.task_routes = {"app.workers.ingest.*": {"queue": "ingest"}}
