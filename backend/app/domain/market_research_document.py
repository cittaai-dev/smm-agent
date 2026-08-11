from typing import Literal

from pydantic import BaseModel

from app.domain.section_result import SectionResult
from app.domain.sop1 import SectionId

# Mirrors Deliverable's status vocabulary (domain/deliverable.py) -- same
# meaning, document-scoped: insufficient_grounding = nothing approvable came
# out of this run at all, not just one degraded section.
DocumentStatus = Literal["draft", "pending_approval", "approved", "rejected", "insufficient_grounding"]


class MarketResearchDocument(BaseModel):
    id: str
    brand_id: str
    status: DocumentStatus
    sections: dict[SectionId, SectionResult]
    call_site_trace: dict[str, int]
    # Sum of SectionResult.cost_usd -- see Deliverable.cost_usd's caveat,
    # same partial-coverage honesty applies here.
    cost_usd: float = 0.0
