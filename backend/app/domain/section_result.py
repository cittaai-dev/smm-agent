from pydantic import BaseModel

from app.domain.audience_persona import VerifiedAudiencePersona
from app.domain.claim import VerifiedClaim
from app.domain.sop1 import SectionId, SectionStatus


class SectionResult(BaseModel):
    section: SectionId
    brand_id: str
    status: SectionStatus
    claims: list[VerifiedClaim] = []
    # target_audience only (SectionSpec.extracts_audience_personas) -- empty
    # for every other section, not a schema-wide concept.
    personas: list[VerifiedAudiencePersona] = []
    call_site_trace: dict[str, int] = {}
    # Why this section landed here when it's not obvious from status alone --
    # e.g. "Market Intel Core not yet available (Step 4)" vs. a real empty-evidence
    # run. Optional because "verified" sections don't need one.
    note: str | None = None
