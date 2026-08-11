import hashlib
from pathlib import Path

from app.infra.celery_app import celery_app
from app.infra.db import get_session
from app.infra.embeddings import embed, embedding_to_sql
from app.infra.telemetry import record_ingest_batch
from app.ingestion.parse import parse_by_type
from app.ingestion.router import route_and_chunk
from app.ingestion.validators import validate_batch

_ANALYTICS_EXTS = {".csv", ".xlsx"}


def infer_source_kind(file_path: str) -> str:
    """Extension-based default. Callers that know better (e.g. an explicit
    competitor-upload zone) should pass source_kind directly instead."""
    return "analytics" if Path(file_path).suffix.lower() in _ANALYTICS_EXTS else "brand_material"


def _mark_source_file(file_id: str, brand_id: str, status: str, reason: str | None) -> None:
    with get_session(kb_id=f"run:{brand_id}") as session:
        session.execute(
            "UPDATE source_file SET status = :status, degraded_reason = :reason WHERE file_id = :fid",
            {"status": status, "reason": reason, "fid": file_id},
        )
        session.commit()


@celery_app.task(name="app.workers.ingest.ingest_file")
def ingest_file(brand_id: str, file_path: str, source_kind: str | None = None) -> str:
    source_kind = source_kind or infer_source_kind(file_path)
    with open(file_path, "rb") as f:
        content_hash = hashlib.sha256(f.read()).hexdigest()

    kb_id = f"run:{brand_id}"
    # doc_id (and therefore chunk_id, derived from it) must be scoped by kb_id
    # too, not just content_hash -- otherwise two different brands uploading
    # identical content would collide on the same doc_id/chunk_id PRIMARY KEY
    # the moment the content_hash uniqueness constraint stopped blocking them.
    doc_id = f"doc-{hashlib.sha256(f'{kb_id}:{content_hash}'.encode()).hexdigest()[:12]}"
    file_id = f"file-{hashlib.sha256(f'{kb_id}:{content_hash}'.encode()).hexdigest()[:12]}"

    with get_session(kb_id=kb_id) as session:
        existing = session.execute(
            "SELECT 1 FROM document_registry WHERE kb_id = :kb AND content_hash = :h",
            {"kb": kb_id, "h": content_hash},
        ).first()
        if existing:
            return "skipped-duplicate"

        session.execute(
            """INSERT INTO source_file (file_id, brand_id, filename, content_hash, source_kind, status)
               VALUES (:fid, :brand, :fn, :hash, :kind, 'uploading')
               ON CONFLICT (file_id) DO NOTHING""",
            {
                "fid": file_id,
                "brand": brand_id,
                "fn": file_path,
                "hash": content_hash,
                "kind": source_kind,
            },
        )
        session.commit()

    try:
        blocks = parse_by_type(file_path, source_kind)
    except Exception as e:  # noqa: BLE001 -- P5: any parser's failure degrades
        # this one file, never aborts the brand's whole ingest. pymupdf/python-docx/
        # python-pptx/pandas each raise their own exception types for corrupt
        # input; narrowing to one library's type would leave the other three
        # unguarded, which defeats the point.
        _mark_source_file(file_id, brand_id, "degraded", str(e))
        return "degraded"

    non_empty = [b for b in blocks if b.text.strip()]
    if not non_empty:
        # Scanned/image-only content, empty spreadsheet, etc. -- honestly
        # nothing to chunk, not a chunk-level C1 violation to paper over.
        _mark_source_file(file_id, brand_id, "degraded", "no extractable text")
        return "degraded"

    with get_session(kb_id=kb_id) as session:
        session.execute(
            """INSERT INTO document_registry (doc_id, kb_id, content_hash, source_uri, source_kind)
               VALUES (:doc_id, :kb_id, :hash, :uri, :kind)""",
            {
                "doc_id": doc_id,
                "kb_id": kb_id,
                "hash": content_hash,
                "uri": file_path,
                "kind": source_kind,
            },
        )

        chunks = route_and_chunk(doc_id, kb_id, non_empty)
        if not all(r.passed for r in validate_batch(chunks)):
            chunks = route_and_chunk(doc_id, kb_id, non_empty, force_l0=True)

        for c in chunks:
            embedding = embed(c.text)
            session.execute(
                """INSERT INTO chunk (chunk_id, kb_id, doc_id, block_span, text, embedding,
                                       order_confidence, degraded, heading_path)
                   VALUES (:cid, :kb, :doc, int4range(:lo, :hi, '[]'), :text, (:emb)::vector,
                           :conf, :degraded, :heading)""",
                {
                    "cid": c.chunk_id,
                    "kb": kb_id,
                    "doc": doc_id,
                    "lo": c.block_span[0],
                    "hi": c.block_span[1],
                    "text": c.text,
                    "emb": embedding_to_sql(embedding),
                    "conf": c.order_confidence,
                    "degraded": c.degraded,
                    "heading": c.heading_path,
                },
            )
        session.commit()

    record_ingest_batch(kb_id, sum(1 for c in chunks if c.degraded), len(chunks))
    _mark_source_file(file_id, brand_id, "ingested", None)
    return "ingested"
