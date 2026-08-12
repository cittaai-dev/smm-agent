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
    # Structured-table sections only (competitor_analysis, platform_analysis):
    # tags this claim as one cell of a table, grouped by group_key (e.g. a
    # competitor/platform name) and field_key (e.g. "strengths"/"priority").
    # None for every ordinary prose claim -- rendering groups these client-side
    # (and in docx_builder.py) rather than via a second, parallel domain type.
    group_key: str | None = None
    field_key: str | None = None


class DerivedClaimDraft(BaseModel):
    """Synthesis-only sections (SWOT, positioning, key takeaways) don't cite raw
    chunks -- they cite the upstream VerifiedClaim(s) they were derived from.
    Kept as a distinct type from ClaimDraft rather than an optional field on it,
    so a call site can only ever produce one citation shape, never a claim that's
    ambiguously both grounded and derived."""

    section: SectionId
    text: str
    source_claim_ids: list[str] = []
    # SWOT only: field_key holds the bucket ("strength"/"weakness"/"opportunity"/
    # "threat"). group_key is unused here -- SWOT has no row concept, just 4
    # buckets -- but kept for shape symmetry with ClaimDraft/VerifiedClaim.
    group_key: str | None = None
    field_key: str | None = None


class VerifiedClaim(BaseModel):
    claim_id: str
    section: str
    text: str
    chunk_id: str = ""
    supporting_chunk_id: str | None = None  # BRIDGE mode only (P7: travels with the artifact)
    source_claim_ids: list[str] = []
    block_span: tuple[int, int] = (0, 0)
    # P7: the cited chunk(s)' order_confidence, carried forward so a claim built
    # on degraded evidence is distinguishable from one built on clean evidence --
    # 1.0 for unverified claims (no evidence to derive a confidence from).
    confidence: float = 1.0
    verified: bool
    rejection_reason: (
        Literal[
            "missing_chunk", "no_citation", "missing_source_claim", "no_source_claims", "missing_bridge_pair"
        ]
        | None
    ) = None
    # See ClaimDraft.group_key/field_key -- carried through verification
    # untouched, same as every other pass-through field.
    group_key: str | None = None
    field_key: str | None = None
