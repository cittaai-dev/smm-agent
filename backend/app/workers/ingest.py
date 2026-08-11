import hashlib

from app.infra.celery_app import celery_app
from app.infra.db import get_session
from app.infra.embeddings import embed, embedding_to_sql
from app.ingestion.parse import extract_text, split_paragraphs


@celery_app.task(name="app.workers.ingest.ingest_file")
def ingest_file(brand_id: str, file_path: str) -> str:
    with open(file_path, "rb") as f:
        content_hash = hashlib.sha256(f.read()).hexdigest()

    kb_id = f"run:{brand_id}"

    with get_session() as session:
        existing = session.execute(
            "SELECT 1 FROM document_registry WHERE kb_id = :kb AND content_hash = :h",
            {"kb": kb_id, "h": content_hash},
        ).first()
        if existing:
            return "skipped-duplicate"

        # doc_id (and therefore chunk_id, which is derived from it below) must be
        # scoped by kb_id too, not just content_hash -- otherwise two different
        # brands uploading identical content would collide on the same doc_id/
        # chunk_id PRIMARY KEY the moment the content_hash uniqueness constraint
        # stopped blocking them.
        doc_id = f"doc-{hashlib.sha256(f'{kb_id}:{content_hash}'.encode()).hexdigest()[:12]}"
        session.execute(
            """INSERT INTO document_registry (doc_id, kb_id, content_hash, source_uri)
               VALUES (:doc_id, :kb_id, :hash, :uri)""",
            {"doc_id": doc_id, "kb_id": kb_id, "hash": content_hash, "uri": file_path},
        )

        text = extract_text(file_path)
        for i, para in enumerate(split_paragraphs(text)):
            chunk_id = hashlib.sha256(f"{doc_id}:{i}".encode()).hexdigest()
            embedding = embed(para)
            session.execute(
                """INSERT INTO chunk (chunk_id, kb_id, doc_id, block_span, text, embedding)
                   VALUES (:cid, :kb, :doc, int4range(:lo, :hi, '[]'), :text, (:emb)::vector)""",
                {
                    "cid": chunk_id,
                    "kb": kb_id,
                    "doc": doc_id,
                    "lo": i,
                    "hi": i,
                    "text": para,
                    "emb": embedding_to_sql(embedding),
                },
            )
        session.commit()
    return "ingested"
