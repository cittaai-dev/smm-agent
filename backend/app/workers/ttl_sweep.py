from celery.schedules import crontab

from app.infra.celery_app import celery_app
from app.infra.db import get_session


@celery_app.task(name="app.workers.ttl_sweep.sweep_expired_run_data")
def sweep_expired_run_data() -> str:
    """Nightly. Deliberately unscoped (no kb_id) -- this legitimately spans
    every brand, unlike every other call site in this codebase. `core:*` is
    structurally exempt: source_file is populated only by Brand Workspace
    ingest (workers/ingest.py); Core builder (Step 4) never writes to it, so
    there's no `WHERE kb_id NOT LIKE` clause to forget."""
    with get_session() as session:
        expired = (
            session.execute(
                "SELECT file_id, brand_id FROM source_file "
                "WHERE ttl_expires_at < now() AND status != 'deleted'"
            )
            .mappings()
            .all()
        )
        for row in expired:
            kb_id = f"run:{row['brand_id']}"
            session.execute(
                "DELETE FROM chunk WHERE doc_id IN "
                "(SELECT doc_id FROM document_registry WHERE kb_id = :kb)",
                {"kb": kb_id},
            )
            session.execute("DELETE FROM document_registry WHERE kb_id = :kb", {"kb": kb_id})
            session.execute(
                "UPDATE source_file SET status = 'deleted' WHERE file_id = :fid",
                {"fid": row["file_id"]},
            )
        session.commit()
    return f"swept {len(expired)}"


celery_app.conf.beat_schedule = {
    **(celery_app.conf.beat_schedule or {}),
    "ttl-sweep-nightly": {
        "task": "app.workers.ttl_sweep.sweep_expired_run_data",
        "schedule": crontab(hour=3, minute=0),
    },
}
