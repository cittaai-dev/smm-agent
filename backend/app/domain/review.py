from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.domain.quality import QualityCheckpoint


class StrategicNote(BaseModel):
    id: str
    document_id: str
    section: str
    text: str
    author: str
    created_at: datetime


class ApprovalGateRecord(BaseModel):
    """Provenance, not the current-state field (document.status already carries
    that) -- the QualityCheckpoint as it stood *at decision time*, who decided,
    when. Dropping this at the approve boundary would be exactly the kind of
    confidence-loss P7 calls out."""

    document_id: str
    approver_id: str | None = None
    decision: Literal["approved", "rejected"] | None = None
    note: str | None = None
    checkpoint: QualityCheckpoint
    decided_at: datetime | None = None


class DistributionRecord(BaseModel):
    document_id: str
    internal: bool
    client: bool
    distributed_at: datetime
