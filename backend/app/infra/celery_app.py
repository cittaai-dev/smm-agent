from celery import Celery

from app.infra.settings import db_settings

celery_app = Celery(
    "smm_agent",
    broker=db_settings.redis_url,
    backend=db_settings.redis_url,
    include=["app.workers.ingest"],
)
celery_app.conf.task_default_queue = "default"
