from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.domain.quality import QualityCheckpoint

ApprovalDecisionKind = Literal["approved", "rejected", "resubmitted"]


class ApprovalEvent(BaseModel):
    """Append-only (step5_trust_boundary.md Part C) -- current_approval_status
    is a query over these, never a column that a reject-then-reapprove
    sequence could overwrite. checkpoint is the QualityCheckpoint as it stood
    *at decision time* (P7); resubmitted events carry no checkpoint since
    nothing new was evaluated, only the status transitioned."""

    id: int | None = None
    document_id: str
    decision: ApprovalDecisionKind
    approver_id: str
    note: str | None = None
    checkpoint: QualityCheckpoint | None = None
    decided_at: datetime | None = None
