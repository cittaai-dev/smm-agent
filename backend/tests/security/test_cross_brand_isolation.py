"""step5_trust_boundary.md §4 -- Part A's actual deliverable. RLS is
defense-in-depth on top of Step 4 §0's app-layer check (already proven in
tests/test_brand_scope.py); this file proves the DB itself can't be tricked
into returning another brand's data even if a future call site forgets the
app-layer filter."""

import hashlib

from app.infra.db import get_session
from app.infra.embeddings import embed, embedding_to_sql
from app.workers.ingest import ingest_file


def _ingest_text(brand_id: str, text: str) -> None:
    kb_id = f"run:{brand_id}"
    content_hash = hashlib.sha256(text.encode()).hexdigest()
    doc_id = f"doc-{content_hash[:12]}"
    with get_session() as session:
        session.execute(
            "INSERT INTO document_registry (doc_id, kb_id, content_hash, source_uri) "
            "VALUES (:doc, :kb, :hash, 'test')",
            {"doc": doc_id, "kb": kb_id, "hash": content_hash},
        )
        session.execute(
            """INSERT INTO chunk (chunk_id, kb_id, doc_id, block_span, text, embedding, order_confidence)
               VALUES (:cid, :kb, :doc, int4range(0, 1, '[]'), :text, (:emb)::vector, 1.0)""",
            {
                "cid": f"c-{content_hash[:12]}",
                "kb": kb_id,
                "doc": doc_id,
                "text": text,
                "emb": embedding_to_sql(embed(text)),
            },
        )
        session.commit()


def test_rls_blocks_explicit_cross_brand_query():
    _ingest_text("brand-a", "brand-a's confidential positioning notes.")
    with get_session(kb_id="run:brand-b") as session:
        rows = session.execute("SELECT * FROM chunk WHERE kb_id LIKE 'run:brand-a%'").fetchall()
    assert rows == []


def test_rls_allows_own_brand_data():
    _ingest_text("brand-a", "brand-a's own onboarding material.")
    with get_session(kb_id="run:brand-a") as session:
        rows = session.execute("SELECT * FROM chunk WHERE kb_id = 'run:brand-a'").fetchall()
    assert len(rows) == 1


def test_rls_never_blocks_core_reads_regardless_of_scope():
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

    with get_session(kb_id="run:brand-a") as session:
        rows = session.execute("SELECT * FROM chunk WHERE kb_id = :kb", {"kb": kb_id}).fetchall()
    assert len(rows) == 1


def test_ingest_pipeline_end_to_end_is_still_isolated(sample_file):
    ingest_file(brand_id="brand-x", file_path=sample_file)
    with get_session(kb_id="run:brand-y") as session:
        rows = session.execute("SELECT * FROM chunk WHERE kb_id = 'run:brand-x'").fetchall()
    assert rows == []
