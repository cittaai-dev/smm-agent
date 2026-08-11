from collections.abc import Callable

from app.domain.chunk import Chunk
from app.domain.claim import VerifiedClaim
from app.domain.kb_version import EvalGateResult, GoldenCase
from app.infra.db import get_session
from app.infra.settings import eval_gate_settings

# Injectable so this module never hard-depends on the BRIDGE/core_only
# orchestration runners (Phase 3) existing yet -- tests supply a fake, matching
# this codebase's existing fake_synthesize_* pattern in tests/conftest.py.
# Signature: (golden_case, staging_kb_id) -> list[VerifiedClaim].
SynthesisRunner = Callable[[GoldenCase, str], list[VerifiedClaim]]


def _load_staging_chunks(staging_kb_id: str) -> list[Chunk]:
    with get_session() as session:
        rows = session.execute(
            "SELECT chunk_id, kb_id, doc_id, lower(block_span) AS lo, "
            "upper(block_span) - 1 AS hi, text, order_confidence, degraded, "
            "heading_path, strategy FROM chunk WHERE kb_id = :kb",
            {"kb": staging_kb_id},
        ).mappings().all()
    return [
        Chunk(
            chunk_id=r["chunk_id"],
            kb_id=r["kb_id"],
            doc_id=r["doc_id"],
            block_span=(r["lo"], r["hi"]),
            text=r["text"],
            order_confidence=r["order_confidence"],
            degraded=r["degraded"],
            heading_path=r["heading_path"] or [],
            strategy=r["strategy"] or "L1",
        )
        for r in rows
    ]


def _degraded_ratio(chunks: list[Chunk]) -> float:
    return sum(1 for c in chunks if c.degraded) / len(chunks) if chunks else 0.0


def _l0_ratio(chunks: list[Chunk]) -> float:
    return sum(1 for c in chunks if c.strategy == "L0") / len(chunks) if chunks else 0.0


def _coverage_ok(chunks: list[Chunk], golden_set: list[GoldenCase]) -> bool:
    """Deterministic, zero-LLM: does the staging corpus contain at least one
    chunk whose text mentions the golden case's topic. A coarse substring
    check on purpose -- real semantic coverage is what citation_rejection_rate
    already measures via actual retrieval+synthesis; this only guards against
    a corpus that's silent on a topic entirely."""
    if not golden_set:
        return True
    texts = [c.text.lower() for c in chunks]
    covered = sum(1 for case in golden_set if any(case.topic.lower() in t for t in texts))
    return (covered / len(golden_set)) >= eval_gate_settings.min_coverage_ratio


def evaluate_staging(
    staging_kb_id: str,
    golden_set: list[GoldenCase],
    run_synthesis_against: SynthesisRunner,
) -> EvalGateResult:
    """The eval gate: necessary, not sufficient (dev_guidelines.md) -- a
    passing corpus still requires an explicit human /decide call
    (api/routes/core.py's promotion-request/decide split). degraded_ratio,
    l0_ratio, and coverage_ok are pure arithmetic over already-ingested
    chunks; citation_rejection_rate replays golden cases through
    run_synthesis_against, an ingest-time-exempt call (P2) injected by the
    caller so this module never assumes a specific orchestration runner.
    """
    chunks = _load_staging_chunks(staging_kb_id)
    if not chunks:
        return EvalGateResult(
            citation_rejection_rate=1.0,
            degraded_ratio=1.0,
            l0_ratio=1.0,
            coverage_ok=False,
            passed=False,
            thresholds=eval_gate_settings.model_dump(),
        )

    degraded_ratio = _degraded_ratio(chunks)
    l0_ratio = _l0_ratio(chunks)
    coverage_ok = _coverage_ok(chunks, golden_set)

    rejections, total = 0, 0
    for case in golden_set:
        claims = run_synthesis_against(case, staging_kb_id)
        total += len(claims)
        rejections += sum(1 for c in claims if not c.verified)
    citation_rejection_rate = (rejections / total) if total else 0.0

    passed = (
        citation_rejection_rate <= eval_gate_settings.max_citation_rejection_rate
        and degraded_ratio <= eval_gate_settings.max_degraded_ratio
        and l0_ratio <= eval_gate_settings.max_l0_ratio
        and coverage_ok
    )

    return EvalGateResult(
        citation_rejection_rate=citation_rejection_rate,
        degraded_ratio=degraded_ratio,
        l0_ratio=l0_ratio,
        coverage_ok=coverage_ok,
        passed=passed,
        thresholds={
            "max_citation_rejection_rate": eval_gate_settings.max_citation_rejection_rate,
            "max_degraded_ratio": eval_gate_settings.max_degraded_ratio,
            "max_l0_ratio": eval_gate_settings.max_l0_ratio,
            "min_coverage_ratio": eval_gate_settings.min_coverage_ratio,
        },
    )
