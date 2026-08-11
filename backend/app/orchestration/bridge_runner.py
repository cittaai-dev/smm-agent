from app.domain.section_result import SectionResult
from app.domain.sop1 import SectionSpec
from app.domain.verify import verify_bridge_claims
from app.orchestration.core_kb import get_active_core_version
from app.retrieval.bridge import search_bridge


def run_bridge(brand_id: str, spec: SectionSpec) -> SectionResult:
    """bridge mode (competitor_analysis, platform_analysis): plan once,
    fan out run-chunk -> core-chunk pairs (retrieval/bridge.py, budget-capped),
    synthesize once against the pairs. No repair call site yet -- call_repair's
    re-tag-by-text logic only fixes a single chunk_id, not a (chunk_id,
    supporting_chunk_id) pair, so a bridge claim that fails verification
    degrades straight to insufficient_evidence (P5) rather than a repair
    attempt that couldn't actually fix a bridge citation. Revisit once a
    bridge-aware repair prompt exists.
    """
    from app.orchestration.llm import call_plan, call_synthesize_bridge
    from app.orchestration.tracing import reset_call_counts

    core_kb_id = get_active_core_version()
    if core_kb_id is None:
        return SectionResult(
            section=spec.id,
            brand_id=brand_id,
            status="insufficient_evidence",
            note="Market Intel Core not yet available",
        )

    reset_call_counts()
    plan = call_plan(section=spec.id, brand_id=brand_id)  # call site (1)
    pairs = search_bridge(f"run:{brand_id}", core_kb_id, plan)

    if not pairs:
        return SectionResult(
            section=spec.id,
            brand_id=brand_id,
            status="insufficient_evidence",
            note="No matching brand/benchmark evidence pairs found",
            call_site_trace={"plan": 1, "synthesize": 0, "repair": 0},
        )

    claims = call_synthesize_bridge(section=spec.id, pairs=pairs)  # call site (2)
    verified = verify_bridge_claims(claims, pairs)

    status = "verified" if verified and all(c.verified for c in verified) else "insufficient_evidence"
    return SectionResult(
        section=spec.id,
        brand_id=brand_id,
        status=status,
        claims=verified,
        call_site_trace={"plan": 1, "synthesize": 1, "repair": 0},
    )
