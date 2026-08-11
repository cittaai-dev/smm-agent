from app.domain.retrieval import RetrievalPlan
from app.infra.db import get_session
from app.infra.embeddings import embed, embedding_to_sql
from app.infra.settings import bridge_settings
from app.retrieval.bridge import search_bridge


def _insert_chunk(kb_id: str, chunk_id: str, text: str) -> None:
    with get_session() as session:
        session.execute(
            "INSERT INTO document_registry (doc_id, kb_id, content_hash, source_uri) "
            "VALUES (:doc, :kb, :hash, 'test') ON CONFLICT (kb_id, content_hash) DO NOTHING",
            {"doc": f"doc-{chunk_id}", "kb": kb_id, "hash": chunk_id},
        )
        session.execute(
            """INSERT INTO chunk (chunk_id, kb_id, doc_id, block_span, text, embedding, order_confidence)
               VALUES (:cid, :kb, :doc, int4range(0, 1, '[]'), :text, (:emb)::vector, 1.0)""",
            {"cid": chunk_id, "kb": kb_id, "doc": f"doc-{chunk_id}", "text": text, "emb": embedding_to_sql(embed(text))},
        )
        session.commit()


def test_bridge_pairs_run_and_core_chunks():
    run_kb, core_kb = "run:brand-x", "core:market-intel@v1"
    _insert_chunk(run_kb, "run-1", "Our Instagram engagement was 2.3k this month")
    _insert_chunk(core_kb, "core-1", "Fitness category Instagram engagement benchmark is 2.8k")

    plan = RetrievalPlan(sub_queries=["Instagram engagement"], k_per_query=8)
    pairs = search_bridge(run_kb, core_kb, plan)

    assert len(pairs) >= 1
    assert pairs[0].run_chunk.chunk_id == "run-1"
    assert pairs[0].core_chunk.chunk_id == "core-1"


def test_bridge_respects_total_pair_budget(monkeypatch):
    monkeypatch.setattr(bridge_settings, "max_total_pairs", 3)
    run_kb, core_kb = "run:brand-y", "core:market-intel@v1"
    for i in range(5):
        _insert_chunk(run_kb, f"run-{i}", f"Brand platform signal number {i}")
    for i in range(5):
        _insert_chunk(core_kb, f"core-{i}", f"Category benchmark number {i}")

    plan = RetrievalPlan(sub_queries=["platform signal"], k_per_query=8)
    pairs = search_bridge(run_kb, core_kb, plan)

    assert len(pairs) <= 3


def test_bridge_returns_empty_when_run_kb_has_no_chunks():
    plan = RetrievalPlan(sub_queries=["anything"], k_per_query=8)
    pairs = search_bridge("run:brand-empty", "core:market-intel@v1", plan)
    assert pairs == []
