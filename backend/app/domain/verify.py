import hashlib

from app.domain.claim import ClaimDraft, DerivedClaimDraft, VerifiedClaim
from app.domain.retrieval import RetrievedContext


def compute_claim_id(section: str, text: str, *keys: str) -> str:
    """Content-addressed like chunk_id (P6): same claim content -> same id, so a
    derived claim downstream can cite it by a stable, reproducible reference."""
    basis = ":".join([section, text, *sorted(keys)])
    return hashlib.sha256(basis.encode()).hexdigest()


def verify_claims(claims: list[ClaimDraft], context: RetrievedContext) -> list[VerifiedClaim]:
    """Deterministic, zero-LLM: does the tagged chunk_id exist in the assembled context (P4)."""
    known = {c.chunk_id: c for c in context.chunks}
    out: list[VerifiedClaim] = []
    for claim in claims:
        if claim.chunk_id is None:
            out.append(
                VerifiedClaim(
                    claim_id=compute_claim_id(claim.section, claim.text),
                    section=claim.section,
                    text=claim.text,
                    verified=False,
                    rejection_reason="no_citation",
                )
            )
            continue
        chunk = known.get(claim.chunk_id)
        if chunk is None:
            out.append(
                VerifiedClaim(
                    claim_id=compute_claim_id(claim.section, claim.text, claim.chunk_id),
                    section=claim.section,
                    text=claim.text,
                    chunk_id=claim.chunk_id,
                    verified=False,
                    rejection_reason="missing_chunk",
                )
            )
            continue
        out.append(
            VerifiedClaim(
                claim_id=compute_claim_id(claim.section, claim.text, claim.chunk_id),
                section=claim.section,
                text=claim.text,
                chunk_id=claim.chunk_id,
                block_span=chunk.block_span,
                verified=True,
            )
        )
    return out


def verify_derived_claims(
    claims: list[DerivedClaimDraft], upstream: list[VerifiedClaim]
) -> list[VerifiedClaim]:
    """Same P4 discipline as verify_claims, applied to synthesis-only sections: a
    derived claim's citation is a set of upstream claim_ids, and it's verified iff
    every one of them resolves to an upstream claim that was itself verified --
    citing a rejected upstream claim would launder ungrounded content through a
    second hop, so only the verified set counts as known."""
    known = {c.claim_id for c in upstream if c.verified}
    out: list[VerifiedClaim] = []
    for claim in claims:
        if not claim.source_claim_ids:
            out.append(
                VerifiedClaim(
                    claim_id=compute_claim_id(claim.section, claim.text),
                    section=claim.section,
                    text=claim.text,
                    verified=False,
                    rejection_reason="no_source_claims",
                )
            )
            continue
        missing = [cid for cid in claim.source_claim_ids if cid not in known]
        claim_id = compute_claim_id(claim.section, claim.text, *claim.source_claim_ids)
        if missing:
            out.append(
                VerifiedClaim(
                    claim_id=claim_id,
                    section=claim.section,
                    text=claim.text,
                    source_claim_ids=claim.source_claim_ids,
                    verified=False,
                    rejection_reason="missing_source_claim",
                )
            )
            continue
        out.append(
            VerifiedClaim(
                claim_id=claim_id,
                section=claim.section,
                text=claim.text,
                source_claim_ids=claim.source_claim_ids,
                verified=True,
            )
        )
    return out
