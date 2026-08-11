from typing import Literal

from pydantic import BaseModel

from app.domain.claim import VerifiedClaim


class Deliverable(BaseModel):
    id: str
    brand_id: str
    status: Literal[
        "draft", "pending_approval", "approved", "rejected", "insufficient_grounding"
    ]
    claims: list[VerifiedClaim]
    call_site_trace: dict[str, int]
