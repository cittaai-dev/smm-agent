from app.infra.celery_app import celery_app
from app.infra.db import get_session
from app.infra.embeddings import embed, embedding_to_sql
from app.ingestion.core_builder import build_staging_batch


@celery_app.task(name="app.workers.core_ingest.build_staging")
def build_staging(source_paths: list[str], target_version: int) -> str:
    """Ingest-time, off the query path (P2 exempt): builds and embeds a
    staging Market Intel Core version. Mirrors workers/ingest.py's own
    parse -> route_and_chunk -> validate -> embed -> store shape, just against
    the L0-L3 ladder and a distinct kb_id namespace (...@vN:staging)."""
    staging_kb_id = f"core:market-intel@v{target_version}:staging"
    chunks = build_staging_batch(source_paths, target_version)
    if not chunks:
        return "staged-empty"

    with get_session() as session:
        session.execute(
            "INSERT INTO kb_version (kb_id, version, status) VALUES (:kb, :v, 'staging') "
            "ON CONFLICT (kb_id) DO NOTHING",
            {"kb": staging_kb_id, "v": target_version},
        )
        for c in chunks:
            session.execute(
                """INSERT INTO document_registry (doc_id, kb_id, content_hash, source_uri)
                   VALUES (:doc, :kb, :doc, :doc) ON CONFLICT (kb_id, content_hash) DO NOTHING""",
                {"doc": c.doc_id, "kb": staging_kb_id},
            )
            embedding = embed(c.text)
            session.execute(
                """INSERT INTO chunk (chunk_id, kb_id, doc_id, block_span, text, embedding,
                                       order_confidence, degraded, heading_path, strategy)
                   VALUES (:cid, :kb, :doc, int4range(:lo, :hi, '[]'), :text, (:emb)::vector,
                           :conf, :degraded, :heading, :strategy)
                   ON CONFLICT (chunk_id) DO NOTHING""",
                {
                    "cid": c.chunk_id,
                    "kb": staging_kb_id,
                    "doc": c.doc_id,
                    "lo": c.block_span[0],
                    "hi": c.block_span[1],
                    "text": c.text,
                    "emb": embedding_to_sql(embedding),
                    "conf": c.order_confidence,
                    "degraded": c.degraded,
                    "heading": c.heading_path,
                    "strategy": c.strategy,
                },
            )
        session.commit()

    return f"staged v{target_version}: {len(chunks)} chunks"
