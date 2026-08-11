from datetime import datetime
from typing import Literal

from pydantic import BaseModel

DistributionChannel = Literal["internal", "client"]


class DistributionEvent(BaseModel):
    """Append-only (step5_trust_boundary.md Part C), same discipline as
    ApprovalEvent -- multiple distribution events for one document must not
    silently collapse into a single overwritten row."""

    id: int | None = None
    document_id: str
    channel: DistributionChannel
    distributed_by: str
    distributed_at: datetime | None = None


class DistributionLink(BaseModel):
    """Authorizes exactly one document's read-only ClientMarketResearchView
    projection, nothing else in the system (step5_trust_boundary.md Part B
    §10). document_id, not "deliverable_id" -- this codebase's MarketResearchDocument
    is what /documents/{document_id}/* routes already operate on; Deliverable
    (domain/deliverable.py) is the earlier Step 1 single-section concept and
    isn't what client links point at. The token itself is never persisted --
    only its hash, same content-addressed-secret discipline as api_key.key_hash."""

    id: str
    document_id: str
    created_by: str
    expires_at: datetime
    revoked: bool = False
    created_at: datetime | None = None
