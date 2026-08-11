from app.domain.audience_persona import VerifiedAudiencePersona
from app.domain.claim import VerifiedClaim
from app.domain.market_research_document import MarketResearchDocument
from app.domain.quality import evaluate_checkpoint
from app.domain.section_result import SectionResult
from app.domain.sop1 import SOP1_SECTIONS

_PERSONA = VerifiedAudiencePersona(
    persona_id="p1", section="target_audience", name="Busy professional",
    pain_points=["no time"], interests=["convenience"], chunk_ids=["c1"], verified=True,
)


def _claim(claim_id: str, section: str, verified: bool = True, source_claim_ids: list[str] | None = None) -> VerifiedClaim:
    return VerifiedClaim(
        claim_id=claim_id, section=section, text="x", chunk_id="c1", block_span=(0, 0),
        verified=verified, source_claim_ids=source_claim_ids or [],
    )


def _complete_passing_document() -> MarketResearchDocument:
    """A baseline doc that passes all four checkpoint fields -- each test
    mutates exactly one thing off this baseline to prove that specific check
    actually fires, rather than every test rebuilding a document from scratch."""
    sections: dict[str, SectionResult] = {}
    for spec in SOP1_SECTIONS:
        sections[spec.id] = SectionResult(section=spec.id, brand_id="brand-x", status="verified")

    sections["brand_overview"].claims = [_claim("bo1", "brand_overview")]
    sections["competitor_analysis"].claims = [
        _claim("comp1", "competitor_analysis"),
        _claim("comp2", "competitor_analysis"),
        _claim("comp3", "competitor_analysis"),
    ]
    sections["target_audience"].personas = [_PERSONA]
    sections["key_takeaways"].claims = [
        _claim("kt1", "key_takeaways", source_claim_ids=["bo1"])
    ]
    return MarketResearchDocument(
        id="doc-1", brand_id="brand-x", status="pending_approval", sections=sections, call_site_trace={}
    )


def test_complete_document_passes_checkpoint():
    checkpoint = evaluate_checkpoint(_complete_passing_document())
    assert checkpoint.passed


def test_missing_section_fails_all_sections_filled():
    doc = _complete_passing_document()
    del doc.sections["swot"]
    checkpoint = evaluate_checkpoint(doc)
    assert not checkpoint.all_sections_filled
    assert not checkpoint.passed


def test_competitor_analysis_insufficient_evidence_exempts_competitor_count():
    # the honest Step 2/3 case: Core (Step 4) isn't live, section correctly
    # degraded -- this check doesn't apply yet, so it's exempted rather than
    # failed. If it failed here, checkpoint.passed could never be True until
    # Step 4, which would make every approval 422 forever.
    doc = _complete_passing_document()
    doc.sections["competitor_analysis"] = SectionResult(
        section="competitor_analysis", brand_id="brand-x", status="insufficient_evidence"
    )
    checkpoint = evaluate_checkpoint(doc)
    assert checkpoint.competitor_count_ok
    assert checkpoint.passed


def test_verified_but_fewer_than_three_competitors_fails_competitor_count():
    # unlike insufficient_evidence, a *verified* section with too few
    # competitors is a real quality gap, not an unavailable check.
    doc = _complete_passing_document()
    doc.sections["competitor_analysis"].claims = [_claim("comp1", "competitor_analysis")]
    checkpoint = evaluate_checkpoint(doc)
    assert not checkpoint.competitor_count_ok


def test_no_personas_fails_personas_grounded():
    doc = _complete_passing_document()
    doc.sections["target_audience"].personas = []
    checkpoint = evaluate_checkpoint(doc)
    assert not checkpoint.personas_grounded
    assert not checkpoint.passed


def test_unverified_persona_fails_personas_grounded():
    doc = _complete_passing_document()
    doc.sections["target_audience"].personas = [
        VerifiedAudiencePersona(
            persona_id="p2", section="target_audience", name="X", pain_points=[], interests=[],
            verified=False, rejection_reason="incomplete_persona",
        )
    ]
    checkpoint = evaluate_checkpoint(doc)
    assert not checkpoint.personas_grounded


def test_key_takeaways_not_citing_any_prior_claim_fails_findings_check():
    doc = _complete_passing_document()
    doc.sections["key_takeaways"].claims = [_claim("kt1", "key_takeaways", source_claim_ids=["ghost"])]
    checkpoint = evaluate_checkpoint(doc)
    assert not checkpoint.findings_lead_to_recommendations
    assert not checkpoint.passed


def test_key_takeaways_citing_an_unverified_prior_claim_fails_findings_check():
    # citing a rejected upstream claim isn't a real finding-to-recommendation
    # link -- must not count.
    doc = _complete_passing_document()
    doc.sections["brand_overview"].claims = [_claim("bo1", "brand_overview", verified=False)]
    checkpoint = evaluate_checkpoint(doc)
    assert not checkpoint.findings_lead_to_recommendations
