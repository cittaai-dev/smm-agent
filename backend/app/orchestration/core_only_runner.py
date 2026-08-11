from app.domain.retrieval import RetrievedContext
from app.domain.section_result import SectionResult
from app.domain.sop1 import SectionSpec
from app.domain.verify import verify_claims
from app.orchestration.core_kb import get_active_core_version
from app.retrieval.dense import search_dense


def run_core_only(brand_id: str, spec: SectionSpec) -> SectionResult:
    """core_only mode (market_overview, trends_opportunities): plan + retrieve
    against Market Intel Core alone, no Brand Workspace chunks involved. Same
    three call sites as the union path (graph.py) -- plan always once,
    synthesize always once, repair 0 or 1 times -- just against a different
    KB and without a full LangGraph state machine, matching synthesis_only.py's
    precedent for a simpler runner outside the graph.
    """
    from app.orchestration.llm import call_plan, call_repair, call_synthesize
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
    context = RetrievedContext(chunks=search_dense(core_kb_id, plan), plan=plan)
    claims = call_synthesize(section=spec.id, context=context)  # call site (2)
    verified = verify_claims(claims, context)

    repair_attempted = False
    if verified and not all(c.verified for c in verified):
        claims = call_repair(claims, context)  # call site (3), bounded to one attempt
        verified = verify_claims(claims, context)
        repair_attempted = True

    status = "verified" if verified and all(c.verified for c in verified) else "insufficient_evidence"
    return SectionResult(
        section=spec.id,
        brand_id=brand_id,
        status=status,
        claims=verified,
        call_site_trace={"plan": 1, "synthesize": 1, "repair": int(repair_attempted)},
    )
