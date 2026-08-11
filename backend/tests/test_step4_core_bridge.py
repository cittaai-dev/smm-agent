from app.domain.claim import ClaimDraft
from app.domain.retrieval import RetrievalPlan
from app.domain.sop1 import SECTIONS_BY_ID
from app.infra.db import get_session
from app.infra.embeddings import embed, embedding_to_sql
from app.orchestration.section_runner import core_kb_available, run_section


def _promote_core_version(version: int = 1) -> str:
    kb_id = f"core:market-intel@v{version}"
    with get_session() as session:
        session.execute(
            "INSERT INTO app_user (id, email, role) VALUES ('u1', 'u1@example.com', 'team_lead') "
            "ON CONFLICT (id) DO NOTHING"
        )
        session.execute(
            "INSERT INTO kb_version (kb_id, version, status, promoted_by) "
            "VALUES (:kb, :v, 'promoted', 'u1')",
            {"kb": kb_id, "v": version},
        )
        session.commit()
    return kb_id


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


def test_core_kb_available_false_before_promotion():
    assert core_kb_available() is False


def test_core_kb_available_true_after_promotion():
    _promote_core_version(1)
    assert core_kb_available() is True


def test_core_only_section_verified_after_promotion(monkeypatch):
    core_kb = _promote_core_version(1)
    _insert_chunk(core_kb, "core-1", "The fitness app market grew 21% YoY")

    monkeypatch.setattr(
        "app.orchestration.llm.call_plan",
        lambda section, brand_id: RetrievalPlan(sub_queries=["fitness app market"], k_per_query=8),
    )
    monkeypatch.setattr(
        "app.orchestration.llm.call_synthesize",
        lambda section, context: [
            ClaimDraft(section=section, text="Market grew 21% YoY", chunk_id=context.chunks[0].chunk_id)
        ],
    )

    spec = SECTIONS_BY_ID["market_overview"]
    result = run_section("brand-x", spec, prior={})
    assert result.status == "verified"
    assert result.claims[0].verified


def test_bridge_section_verified_after_promotion(monkeypatch):
    core_kb = _promote_core_version(1)
    _insert_chunk("run:brand-x", "run-1", "Our Instagram engagement was 2.3k this month")
    _insert_chunk(core_kb, "core-1", "Fitness category Instagram engagement benchmark is 2.8k")

    monkeypatch.setattr(
        "app.orchestration.llm.call_plan",
        lambda section, brand_id: RetrievalPlan(sub_queries=["Instagram engagement"], k_per_query=8),
    )

    def fake_bridge_synth(section, pairs):
        pair = pairs[0]
        return [
            ClaimDraft(
                section=section,
                text="Engagement trails category benchmark",
                chunk_id=pair.run_chunk.chunk_id,
                supporting_chunk_id=pair.core_chunk.chunk_id,
            )
        ]

    monkeypatch.setattr("app.orchestration.llm.call_synthesize_bridge", fake_bridge_synth)

    spec = SECTIONS_BY_ID["competitor_analysis"]
    result = run_section("brand-x", spec, prior={})
    assert result.status == "verified"
    assert result.claims[0].supporting_chunk_id == "core-1"


def test_bridge_section_degrades_when_no_pairs_found():
    _promote_core_version(1)
    spec = SECTIONS_BY_ID["platform_analysis"]
    result = run_section("brand-empty", spec, prior={})
    assert result.status == "insufficient_evidence"
