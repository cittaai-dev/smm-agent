from app.domain.claim import ClaimDraft, VerifiedClaim
from app.domain.retrieval import RetrievedContext


def verify_claims(
    claims: list[ClaimDraft], context: RetrievedContext
) -> list[VerifiedClaim]:
    """Deterministic, zero-LLM: does the tagged chunk_id exist in the assembled context (P4)."""
    known = {c.chunk_id: c for c in context.chunks}
    out: list[VerifiedClaim] = []
    for claim in claims:
        if claim.chunk_id is None:
            out.append(
                VerifiedClaim(
                    section=claim.section,
                    text=claim.text,
                    chunk_id="",
                    block_span=(0, 0),
                    verified=False,
                    rejection_reason="no_citation",
                )
            )
            continue
        chunk = known.get(claim.chunk_id)
        if chunk is None:
            out.append(
                VerifiedClaim(
                    section=claim.section,
                    text=claim.text,
                    chunk_id=claim.chunk_id,
                    block_span=(0, 0),
                    verified=False,
                    rejection_reason="missing_chunk",
                )
            )
            continue
        out.append(
            VerifiedClaim(
                section=claim.section,
                text=claim.text,
                chunk_id=claim.chunk_id,
                block_span=chunk.block_span,
                verified=True,
            )
        )
    return out
