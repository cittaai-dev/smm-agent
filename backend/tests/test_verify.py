from app.domain.audience_persona import AudiencePersonaDraft
from app.domain.chunk import Chunk
from app.domain.claim import ClaimDraft, DerivedClaimDraft, VerifiedClaim
from app.domain.retrieval import RetrievalPlan, RetrievedContext
from app.domain.verify import verify_audience_personas, verify_claims, verify_derived_claims

_PLAN = RetrievalPlan(sub_queries=["q"])
_CHUNK = Chunk(chunk_id="c1", kb_id="run:b", doc_id="d1", block_span=(0, 0), text="evidence")
_CONTEXT = RetrievedContext(chunks=[_CHUNK], plan=_PLAN)


def test_verified_claim_resolves_block_span():
    claims = [ClaimDraft(section="brand_overview", text="claim", chunk_id="c1")]
    [result] = verify_claims(claims, _CONTEXT)
    assert result.verified
    assert result.block_span == _CHUNK.block_span
    assert result.rejection_reason is None
    assert result.claim_id  # content-addressed id always assigned, even on the happy path


def test_missing_chunk_id_rejected_as_no_citation():
    claims = [ClaimDraft(section="brand_overview", text="claim", chunk_id=None)]
    [result] = verify_claims(claims, _CONTEXT)
    assert not result.verified
    assert result.rejection_reason == "no_citation"


def test_fabricated_chunk_id_rejected_as_missing_chunk():
    claims = [ClaimDraft(section="brand_overview", text="claim", chunk_id="does-not-exist")]
    [result] = verify_claims(claims, _CONTEXT)
    assert not result.verified
    assert result.rejection_reason == "missing_chunk"


def test_claim_id_is_content_addressed_not_random():
    claims = [ClaimDraft(section="brand_overview", text="claim", chunk_id="c1")]
    [first] = verify_claims(claims, _CONTEXT)
    [second] = verify_claims(claims, _CONTEXT)
    assert first.claim_id == second.claim_id


_UPSTREAM_VERIFIED = VerifiedClaim(
    claim_id="up1", section="brand_overview", text="Acme sells coffee.", chunk_id="c1",
    block_span=(0, 0), verified=True,
)
_UPSTREAM_REJECTED = VerifiedClaim(
    claim_id="up2", section="brand_overview", text="fabricated", verified=False,
    rejection_reason="missing_chunk",
)


def test_derived_claim_citing_verified_upstream_is_verified():
    claims = [DerivedClaimDraft(section="swot", text="Strength: coffee brand", source_claim_ids=["up1"])]
    [result] = verify_derived_claims(claims, [_UPSTREAM_VERIFIED, _UPSTREAM_REJECTED])
    assert result.verified
    assert result.rejection_reason is None


def test_derived_claim_with_no_source_claims_rejected():
    claims = [DerivedClaimDraft(section="swot", text="Strength: coffee brand", source_claim_ids=[])]
    [result] = verify_derived_claims(claims, [_UPSTREAM_VERIFIED])
    assert not result.verified
    assert result.rejection_reason == "no_source_claims"


def test_derived_claim_citing_rejected_upstream_claim_is_rejected():
    # citing an upstream claim that itself failed verification must not launder
    # ungrounded content through a second synthesis hop (P4).
    claims = [DerivedClaimDraft(section="swot", text="Strength: coffee brand", source_claim_ids=["up2"])]
    [result] = verify_derived_claims(claims, [_UPSTREAM_VERIFIED, _UPSTREAM_REJECTED])
    assert not result.verified
    assert result.rejection_reason == "missing_source_claim"


def test_derived_claim_citing_unknown_claim_id_rejected():
    claims = [DerivedClaimDraft(section="swot", text="Strength: coffee brand", source_claim_ids=["ghost"])]
    [result] = verify_derived_claims(claims, [_UPSTREAM_VERIFIED])
    assert not result.verified
    assert result.rejection_reason == "missing_source_claim"


def test_audience_persona_grounded_and_complete_is_verified():
    personas = [
        AudiencePersonaDraft(
            section="target_audience", name="Weekend warrior",
            pain_points=["Limited free time"], interests=["Quality gear"], chunk_ids=["c1"],
        )
    ]
    [result] = verify_audience_personas(personas, _CONTEXT)
    assert result.verified
    assert result.rejection_reason is None
    assert result.persona_id


def test_audience_persona_missing_pain_points_rejected_as_incomplete():
    personas = [
        AudiencePersonaDraft(
            section="target_audience", name="Weekend warrior",
            pain_points=[], interests=["Quality gear"], chunk_ids=["c1"],
        )
    ]
    [result] = verify_audience_personas(personas, _CONTEXT)
    assert not result.verified
    assert result.rejection_reason == "incomplete_persona"


def test_audience_persona_missing_interests_rejected_as_incomplete():
    personas = [
        AudiencePersonaDraft(
            section="target_audience", name="Weekend warrior",
            pain_points=["Limited free time"], interests=[], chunk_ids=["c1"],
        )
    ]
    [result] = verify_audience_personas(personas, _CONTEXT)
    assert not result.verified
    assert result.rejection_reason == "incomplete_persona"


def test_audience_persona_with_no_citation_rejected():
    personas = [
        AudiencePersonaDraft(
            section="target_audience", name="Weekend warrior",
            pain_points=["Limited free time"], interests=["Quality gear"], chunk_ids=[],
        )
    ]
    [result] = verify_audience_personas(personas, _CONTEXT)
    assert not result.verified
    assert result.rejection_reason == "no_citation"


def test_audience_persona_citing_fabricated_chunk_rejected():
    personas = [
        AudiencePersonaDraft(
            section="target_audience", name="Weekend warrior",
            pain_points=["Limited free time"], interests=["Quality gear"], chunk_ids=["does-not-exist"],
        )
    ]
    [result] = verify_audience_personas(personas, _CONTEXT)
    assert not result.verified
    assert result.rejection_reason == "missing_chunk"
