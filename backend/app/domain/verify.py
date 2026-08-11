import hashlib

from app.domain.audience_persona import AudiencePersonaDraft, VerifiedAudiencePersona
from app.domain.claim import ClaimDraft, DerivedClaimDraft, VerifiedClaim
from app.domain.retrieval import RetrievedContext
from app.infra.telemetry import record_claim_verification
from app.retrieval.bridge import BridgePair


def compute_claim_id(section: str, text: str, *keys: str) -> str:
    """Content-addressed like chunk_id (P6): same claim content -> same id, so a
    derived claim downstream can cite it by a stable, reproducible reference."""
    basis = ":".join([section, text, *sorted(keys)])
    return hashlib.sha256(basis.encode()).hexdigest()


def compute_persona_id(section: str, name: str, *keys: str) -> str:
    basis = ":".join([section, name, *sorted(keys)])
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
    for claim in out:
        record_claim_verification(claim.section, claim.verified)
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
    for claim in out:
        record_claim_verification(claim.section, claim.verified)
    return out


def verify_bridge_claims(claims: list[ClaimDraft], pairs: list[BridgePair]) -> list[VerifiedClaim]:
    """BRIDGE's P4 discipline: a claim is verified iff (chunk_id, supporting_chunk_id)
    matches an *actual* pair the retrieval step produced -- not two independently
    resolvable chunk_ids that happen to exist in different pairs. That distinction
    matters: citing a real observation against an unrelated benchmark would be a
    fabricated comparison even though both halves are individually real evidence."""
    known_pairs = {(p.run_chunk.chunk_id, p.core_chunk.chunk_id) for p in pairs}
    out: list[VerifiedClaim] = []
    for claim in claims:
        if claim.chunk_id is None or claim.supporting_chunk_id is None:
            out.append(
                VerifiedClaim(
                    claim_id=compute_claim_id(claim.section, claim.text),
                    section=claim.section,
                    text=claim.text,
                    chunk_id=claim.chunk_id or "",
                    verified=False,
                    rejection_reason="no_citation",
                )
            )
            continue
        if (claim.chunk_id, claim.supporting_chunk_id) not in known_pairs:
            out.append(
                VerifiedClaim(
                    claim_id=compute_claim_id(claim.section, claim.text, claim.chunk_id),
                    section=claim.section,
                    text=claim.text,
                    chunk_id=claim.chunk_id,
                    verified=False,
                    rejection_reason="missing_bridge_pair",
                )
            )
            continue
        run_chunk = next(p.run_chunk for p in pairs if p.run_chunk.chunk_id == claim.chunk_id)
        out.append(
            VerifiedClaim(
                claim_id=compute_claim_id(claim.section, claim.text, claim.chunk_id),
                section=claim.section,
                text=claim.text,
                chunk_id=claim.chunk_id,
                supporting_chunk_id=claim.supporting_chunk_id,
                block_span=run_chunk.block_span,
                verified=True,
            )
        )
    for claim in out:
        record_claim_verification(claim.section, claim.verified)
    return out


def verify_audience_personas(
    personas: list[AudiencePersonaDraft], context: RetrievedContext
) -> list[VerifiedAudiencePersona]:
    """Same P4 discipline as verify_claims: a persona's grounding is a
    deterministic check against the assembled context, never the model's own
    say-so. incomplete_persona is a structural check (does it have both
    pain_points and interests), not the model judging its own quality --
    matches how the doc's own evaluate_checkpoint reasons about personas, just
    enforced here instead of left to a checkpoint to notice later."""
    known = {c.chunk_id for c in context.chunks}
    out: list[VerifiedAudiencePersona] = []
    for p in personas:
        persona_id = compute_persona_id(p.section, p.name, *p.chunk_ids)
        if not p.pain_points or not p.interests:
            out.append(
                VerifiedAudiencePersona(
                    persona_id=persona_id,
                    section=p.section,
                    name=p.name,
                    pain_points=p.pain_points,
                    interests=p.interests,
                    chunk_ids=p.chunk_ids,
                    verified=False,
                    rejection_reason="incomplete_persona",
                )
            )
            continue
        if not p.chunk_ids:
            out.append(
                VerifiedAudiencePersona(
                    persona_id=persona_id,
                    section=p.section,
                    name=p.name,
                    pain_points=p.pain_points,
                    interests=p.interests,
                    verified=False,
                    rejection_reason="no_citation",
                )
            )
            continue
        missing = [cid for cid in p.chunk_ids if cid not in known]
        if missing:
            out.append(
                VerifiedAudiencePersona(
                    persona_id=persona_id,
                    section=p.section,
                    name=p.name,
                    pain_points=p.pain_points,
                    interests=p.interests,
                    chunk_ids=p.chunk_ids,
                    verified=False,
                    rejection_reason="missing_chunk",
                )
            )
            continue
        out.append(
            VerifiedAudiencePersona(
                persona_id=persona_id,
                section=p.section,
                name=p.name,
                pain_points=p.pain_points,
                interests=p.interests,
                chunk_ids=p.chunk_ids,
                verified=True,
            )
        )
    return out
