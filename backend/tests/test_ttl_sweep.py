from app.infra.db import get_session
from app.infra.embeddings import embed, embedding_to_sql
from app.workers.ttl_sweep import sweep_expired_run_data


def _seed_source(brand_id: str, file_id: str, expired: bool) -> str:
    kb_id = f"run:{brand_id}"
    doc_id = f"doc-{file_id}"
    ttl_expr = "now() - interval '1 hour'" if expired else "now() + interval '90 days'"
    with get_session() as session:
        session.execute(
            f"""INSERT INTO source_file (file_id, brand_id, filename, content_hash, source_kind,
                                          status, ttl_expires_at)
               VALUES (:fid, :brand, 'f.txt', :hash, 'brand_material', 'ingested', {ttl_expr})""",
            {"fid": file_id, "brand": brand_id, "hash": f"hash-{file_id}"},
        )
        session.execute(
            "INSERT INTO document_registry (doc_id, kb_id, content_hash, source_uri) "
            "VALUES (:doc, :kb, :hash, 'test')",
            {"doc": doc_id, "kb": kb_id, "hash": f"hash-{file_id}"},
        )
        text = f"Some brand content for {file_id}."
        session.execute(
            """INSERT INTO chunk (chunk_id, kb_id, doc_id, block_span, text, embedding, order_confidence)
               VALUES (:cid, :kb, :doc, int4range(0, 1, '[]'), :text, (:emb)::vector, 1.0)""",
            {"cid": f"c-{file_id}", "kb": kb_id, "doc": doc_id, "text": text, "emb": embedding_to_sql(embed(text))},
        )
        session.commit()
    return doc_id


def test_sweep_deletes_only_expired_run_data():
    _seed_source("brand-old", "file-old", expired=True)
    _seed_source("brand-fresh", "file-fresh", expired=False)

    sweep_expired_run_data()

    with get_session() as session:
        old_chunks = session.execute(
            "SELECT 1 FROM chunk WHERE kb_id = 'run:brand-old'"
        ).first()
        fresh_chunks = session.execute(
            "SELECT 1 FROM chunk WHERE kb_id = 'run:brand-fresh'"
        ).first()
        old_status = session.execute(
            "SELECT status FROM source_file WHERE file_id = 'file-old'"
        ).scalar_one()
        fresh_status = session.execute(
            "SELECT status FROM source_file WHERE file_id = 'file-fresh'"
        ).scalar_one()

    assert old_chunks is None
    assert fresh_chunks is not None
    assert old_status == "deleted"
    assert fresh_status == "ingested"


def test_sweep_never_touches_core():
    kb_id = "core:market-intel@v1"
    with get_session() as session:
        session.execute(
            "INSERT INTO document_registry (doc_id, kb_id, content_hash, source_uri) "
            "VALUES ('doc-core', :kb, 'hash-core', 'test')",
            {"kb": kb_id},
        )
        text = "Category benchmark data."
        session.execute(
            """INSERT INTO chunk (chunk_id, kb_id, doc_id, block_span, text, embedding, order_confidence)
               VALUES ('c-core', :kb, 'doc-core', int4range(0, 1, '[]'), :text, (:emb)::vector, 1.0)""",
            {"kb": kb_id, "text": text, "emb": embedding_to_sql(embed(text))},
        )
        session.commit()

    sweep_expired_run_data()

    with get_session() as session:
        still_there = session.execute("SELECT 1 FROM chunk WHERE kb_id = :kb", {"kb": kb_id}).first()
    assert still_there is not None
