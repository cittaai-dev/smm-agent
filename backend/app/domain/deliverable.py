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
    # One failure vocabulary for every degrade path (step6_production_operations.md
    # "Core Concepts") -- a cost overrun, a provider outage, and a real evidence
    # gap all route to status="insufficient_grounding" with a distinct reason,
    # never three different statuses for what the caller must treat the same way.
    reason: str | None = None
    # RunCostTracker.usd_spent at the point this deliverable was produced --
    # union mode (orchestration/graph.py) only for now; bridge/synthesis_only
    # runners don't thread a tracker through yet, so their contribution reads
    # as 0.0 rather than a fabricated estimate (P7: confidence/cost travels
    # with the artifact, a boundary that drops it is a bug -- so an honest
    # partial number, not a silently wrong total).
    cost_usd: float = 0.0
