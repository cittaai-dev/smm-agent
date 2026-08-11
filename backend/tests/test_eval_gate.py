from app.domain.claim import VerifiedClaim
from app.domain.kb_version import GoldenCase
from app.eval.gate import evaluate_staging
from app.infra.db import get_session
from app.infra.embeddings import embed, embedding_to_sql


def _insert_chunk(kb_id: str, chunk_id: str, text: str, degraded: bool, strategy: str) -> None:
    with get_session() as session:
        session.execute(
            "INSERT INTO document_registry (doc_id, kb_id, content_hash, source_uri) "
            "VALUES (:doc, :kb, :hash, 'test') ON CONFLICT (kb_id, content_hash) DO NOTHING",
            {"doc": f"doc-{chunk_id}", "kb": kb_id, "hash": chunk_id},
        )
        session.execute(
            """INSERT INTO chunk (chunk_id, kb_id, doc_id, block_span, text, embedding,
                                   order_confidence, degraded, strategy)
               VALUES (:cid, :kb, :doc, int4range(0, 1, '[]'), :text, (:emb)::vector,
                       1.0, :degraded, :strategy)""",
            {
                "cid": chunk_id,
                "kb": kb_id,
                "doc": f"doc-{chunk_id}",
                "text": text,
                "emb": embedding_to_sql(embed(text)),
                "degraded": degraded,
                "strategy": strategy,
            },
        )
        session.commit()


def test_eval_gate_passes_good_corpus():
    kb_id = "core:market-intel@v1:staging"
    _insert_chunk(kb_id, "c1", "Fitness category engagement benchmark", degraded=False, strategy="L1")
    _insert_chunk(kb_id, "c2", "Competitor posting cadence data", degraded=False, strategy="L1")
    golden = [GoldenCase(id="g1", topic="fitness category", section="market_overview")]

    def fake_synthesis(case: GoldenCase, staging_kb_id: str) -> list[VerifiedClaim]:
        return [VerifiedClaim(claim_id="cl1", section=case.section, text="...", chunk_id="c1", verified=True)]

    result = evaluate_staging(kb_id, golden, run_synthesis_against=fake_synthesis)
    assert result.passed
    assert result.citation_rejection_rate == 0.0
    assert result.degraded_ratio == 0.0
    assert result.coverage_ok


def test_eval_gate_fails_on_high_rejection_rate():
    kb_id = "core:market-intel@v2:staging"
    _insert_chunk(kb_id, "c1", "Fitness category engagement benchmark", degraded=False, strategy="L1")
    golden = [GoldenCase(id="g1", topic="fitness category", section="market_overview")]

    def fake_synthesis_all_rejected(case: GoldenCase, staging_kb_id: str) -> list[VerifiedClaim]:
        return [
            VerifiedClaim(claim_id="cl1", section=case.section, text="...", verified=False,
                          rejection_reason="no_citation")
        ]

    result = evaluate_staging(kb_id, golden, run_synthesis_against=fake_synthesis_all_rejected)
    assert not result.passed
    assert result.citation_rejection_rate == 1.0


def test_eval_gate_fails_on_high_degraded_ratio():
    kb_id = "core:market-intel@v3:staging"
    for i in range(10):
        _insert_chunk(kb_id, f"c{i}", f"chunk {i}", degraded=(i < 6), strategy="L0" if i < 6 else "L1")
    golden: list[GoldenCase] = []

    result = evaluate_staging(kb_id, golden, run_synthesis_against=lambda case, kb: [])
    assert not result.passed
    assert result.degraded_ratio == 0.6


def test_eval_gate_rejects_empty_corpus():
    result = evaluate_staging(
        "core:market-intel@v99:staging", [], run_synthesis_against=lambda case, kb: []
    )
    assert not result.passed
    assert result.degraded_ratio == 1.0
