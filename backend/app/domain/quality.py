from pydantic import BaseModel

from app.domain.market_research_document import MarketResearchDocument
from app.domain.sop1 import SOP1_SECTIONS

_MIN_COMPETITORS = 3


class QualityCheckpoint(BaseModel):
    all_sections_filled: bool
    competitor_count_ok: bool
    personas_grounded: bool
    findings_lead_to_recommendations: bool

    @property
    def passed(self) -> bool:
        return all(
            [
                self.all_sections_filled,
                self.competitor_count_ok,
                self.personas_grounded,
                self.findings_lead_to_recommendations,
            ]
        )


def evaluate_checkpoint(doc: MarketResearchDocument) -> QualityCheckpoint:
    """Operationalizes SOP-1's own quality checkpoints as code -- no LLM judges
    any of these, each is a deterministic check over data Verify already
    resolved (P4). None of the four are moot until Step 4 by construction:
    competitor_count_ok is the honest exception, tied to a Core-gated section
    that's always insufficient_evidence until then (that's not a bug in this
    function, it's the section correctly reporting it has nothing yet)."""
    return QualityCheckpoint(
        all_sections_filled=_all_sections_filled(doc),
        competitor_count_ok=_competitor_count_ok(doc),
        personas_grounded=_personas_grounded(doc),
        findings_lead_to_recommendations=_findings_lead_to_recommendations(doc),
    )


def _all_sections_filled(doc: MarketResearchDocument) -> bool:
    # Every SectionStatus value is "filled" by construction (a section always
    # gets verified/insufficient_evidence/team_provided, never absent status)
    # -- what's actually worth checking is structural completeness: did
    # run_all_sections finish and populate every expected section, or did a
    # partial/crashed run leave some missing from the dict entirely.
    return all(spec.id in doc.sections for spec in SOP1_SECTIONS)


def _competitor_count_ok(doc: MarketResearchDocument) -> bool:
    section = doc.sections.get("competitor_analysis")
    if section is None:
        return False
    if section.status == "insufficient_evidence":
        # Core (Step 4) isn't live -- this check doesn't apply yet, so it's
        # exempted rather than failed. Without this, checkpoint.passed could
        # never be True in Step 2/3's real operating conditions (§6 is always
        # insufficient_evidence until Step 4), which would make every
        # approval 422 forever -- directly contradicting Step 3's own goal of
        # making the brand-only sections production-grade on their own terms.
        return True
    if section.status != "verified":
        return False
    return len(section.claims) >= _MIN_COMPETITORS


def _personas_grounded(doc: MarketResearchDocument) -> bool:
    section = doc.sections.get("target_audience")
    if section is None or not section.personas:
        return False
    return all(p.verified for p in section.personas)


def _findings_lead_to_recommendations(doc: MarketResearchDocument) -> bool:
    # key_takeaways (synthesis_only) cites upstream *claim_ids* via
    # source_claim_ids, not raw chunk_ids -- Step 2's derived-claim citation
    # chain already gives a more precise version of the doc's own pseudocode
    # (which compared chunk_ids, a field key_takeaways' claims don't carry at
    # all). Only verified claims on both sides count -- a match against a
    # rejected claim isn't a real finding-to-recommendation link.
    key_takeaways = doc.sections.get("key_takeaways")
    if key_takeaways is None:
        return False
    takeaway_source_ids = {
        cid for c in key_takeaways.claims if c.verified for cid in c.source_claim_ids
    }
    prior_claim_ids = {
        c.claim_id
        for section_id, section in doc.sections.items()
        if section_id != "key_takeaways"
        for c in section.claims
        if c.verified
    }
    return bool(takeaway_source_ids & prior_claim_ids)
