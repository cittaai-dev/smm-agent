from app.domain.market_research_document import MarketResearchDocument
from app.domain.section_result import SectionResult
from app.domain.sop1 import SOP1_SECTIONS, SectionSpec


def core_kb_available() -> bool:
    """Market Intel Core doesn't exist as infrastructure until Step 4 (dual-kb.md,
    implementation-roadmap). Hardcoded False is the honest Step 2 answer, not a
    stub -- flipping it early would silently fabricate core_only/bridge sections
    against zero curated evidence."""
    return False


def run_section(brand_id: str, spec: SectionSpec, prior: dict[str, SectionResult]) -> SectionResult:
    if spec.retrieval_mode == "direct_input":
        from app.orchestration.team_input import use_team_lead_input

        return use_team_lead_input(brand_id, spec)

    if spec.requires_core and not core_kb_available():
        return SectionResult(
            section=spec.id,
            brand_id=brand_id,
            status="insufficient_evidence",
            note="Market Intel Core not yet available -- deferred to Step 4",
        )

    if spec.retrieval_mode == "synthesis_only":
        from app.orchestration.synthesis_only import run_synthesis_only

        return run_synthesis_only(brand_id, spec, prior)

    # union -- the only mode left, and the one Step 1's graph already proves.
    from app.orchestration.graph import run_pipeline

    result = run_pipeline(brand_id=brand_id, section=spec.id)
    status = "verified" if result.deliverable.status == "pending_approval" else "insufficient_evidence"
    return SectionResult(
        section=spec.id,
        brand_id=brand_id,
        status=status,
        claims=result.deliverable.claims,
        personas=result.personas,
        call_site_trace=result.deliverable.call_site_trace,
    )


def run_all_sections(brand_id: str) -> dict[str, SectionResult]:
    # Registry order already respects dependency order (every depends_on entry
    # is declared earlier in SOP1_SECTIONS) -- see domain/sop1.py's ordering note.
    results: dict[str, SectionResult] = {}
    for spec in SOP1_SECTIONS:
        results[spec.id] = run_section(brand_id, spec, results)
    return results


def assemble_document(brand_id: str, results: dict[str, SectionResult]) -> MarketResearchDocument:
    total_trace: dict[str, int] = {}
    for r in results.values():
        for site, count in r.call_site_trace.items():
            total_trace[site] = total_trace.get(site, 0) + count

    # Mirrors Deliverable's own "zero claims must never read as pending_approval"
    # rule (route_after_verify in graph.py) at the document level: a run that
    # produced nothing anywhere isn't the same as a run where some sections
    # correctly degraded (P5) while others succeeded.
    has_any_claims = any(r.claims for r in results.values())
    status = "pending_approval" if has_any_claims else "insufficient_grounding"

    return MarketResearchDocument(
        id=f"doc-{brand_id}-market-research",
        brand_id=brand_id,
        status=status,
        sections=results,
        call_site_trace=total_trace,
    )
