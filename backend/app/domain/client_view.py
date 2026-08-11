from pydantic import BaseModel

from app.domain.market_research_document import MarketResearchDocument
from app.domain.sop1 import SectionId

# Deliberately absent from both models below: chunk_id, block_span,
# call_site_trace, rejection_reason, approver_id -- an external client never
# sees retrieval/verification internals, only the shipped claim text
# (step5_trust_boundary.md Part B §9).


class ClientClaim(BaseModel):
    text: str


class ClientPersona(BaseModel):
    name: str
    pain_points: list[str] = []
    interests: list[str] = []


class ClientMarketResearchView(BaseModel):
    brand_id: str
    sections: dict[SectionId, list[ClientClaim]]
    personas: list[ClientPersona]


def project_for_client(doc: MarketResearchDocument) -> ClientMarketResearchView:
    """Computed at request time from the approved document, never a second
    write path -- there is exactly one source of truth, so this can never
    drift out of sync with what a Team Lead actually approved."""
    sections = {
        section_id: [ClientClaim(text=c.text) for c in result.claims if c.verified]
        for section_id, result in doc.sections.items()
        if result.status in ("verified", "team_provided")
    }
    personas = [
        ClientPersona(name=p.name, pain_points=p.pain_points, interests=p.interests)
        for result in doc.sections.values()
        for p in result.personas
        if p.verified
    ]
    return ClientMarketResearchView(brand_id=doc.brand_id, sections=sections, personas=personas)
