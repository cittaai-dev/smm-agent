from typing import Literal

from pydantic import BaseModel

from app.domain.sop1 import SectionId


class ClaimDraft(BaseModel):
    section: SectionId
    text: str
    chunk_id: str | None = None
    # BRIDGE mode only (Step 4): the Core-half chunk_id of the run/core pair
    # this claim benchmarks against. None for every union/synthesis_only claim.
    supporting_chunk_id: str | None = None


class DerivedClaimDraft(BaseModel):
    """Synthesis-only sections (SWOT, positioning, key takeaways) don't cite raw
    chunks -- they cite the upstream VerifiedClaim(s) they were derived from.
    Kept as a distinct type from ClaimDraft rather than an optional field on it,
    so a call site can only ever produce one citation shape, never a claim that's
    ambiguously both grounded and derived."""

    section: SectionId
    text: str
    source_claim_ids: list[str] = []


class VerifiedClaim(BaseModel):
    claim_id: str
    section: str
    text: str
    chunk_id: str = ""
    supporting_chunk_id: str | None = None  # BRIDGE mode only (P7: travels with the artifact)
    source_claim_ids: list[str] = []
    block_span: tuple[int, int] = (0, 0)
    verified: bool
    rejection_reason: (
        Literal[
            "missing_chunk", "no_citation", "missing_source_claim", "no_source_claims", "missing_bridge_pair"
        ]
        | None
    ) = None
