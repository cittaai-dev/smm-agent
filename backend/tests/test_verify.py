from app.domain.audience_persona import AudiencePersonaDraft
from app.domain.chunk import Chunk
from app.domain.claim import ClaimDraft, DerivedClaimDraft, VerifiedClaim
from app.domain.retrieval import RetrievalPlan, RetrievedContext
from app.domain.verify import (
    verify_audience_personas,
    verify_bridge_claims,
    verify_claims,
    verify_derived_claims,
)
from app.retrieval.bridge import BridgePair

_PLAN = RetrievalPlan(sub_queries=["q"])
_CHUNK = Chunk(chunk_id="c1", kb_id="run:b", doc_id="d1", block_span=(0, 0), text="evidence")
_CONTEXT = RetrievedContext(chunks=[_CHUNK], plan=_PLAN)

# The persona-table fields (target_audience's structured comparison table) --
# a persona needs all of these, not just pain_points/interests, to verify.
_COMPLETE_PERSONA_FIELDS = {
    "age_range": "25-34",
    "location": "Urban US",
    "occupation_income": "Mid-career, $60k-$90k",
    "preferred_platforms": ["Instagram"],
}


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


def test_verified_claim_confidence_carries_cited_chunks_order_confidence():
    degraded_chunk = Chunk(
        chunk_id="c2", kb_id="run:b", doc_id="d1", block_span=(0, 0), text="ocr'd",
        order_confidence=0.4,
    )
    context = RetrievedContext(chunks=[_CHUNK, degraded_chunk], plan=_PLAN)
    claims = [ClaimDraft(section="brand_overview", text="claim", chunk_id="c2")]
    [result] = verify_claims(claims, context)
    assert result.confidence == 0.4


def test_unverified_claim_confidence_defaults_to_full():
    claims = [ClaimDraft(section="brand_overview", text="claim", chunk_id=None)]
    [result] = verify_claims(claims, _CONTEXT)
    assert result.confidence == 1.0


def test_group_key_and_field_key_pass_through_verification_untouched():
    # competitor_analysis/platform_analysis table cells -- verification logic
    # is unaffected by these tags, but they must survive to the verified claim
    # (both on the happy path and the rejected path) so the frontend/docx
    # exporter can still group a rejected cell into the right slot.
    claims = [
        ClaimDraft(
            section="competitor_analysis", text="Fast shipping", chunk_id="c1",
            group_key="Acme Corp", field_key="strengths",
        )
    ]
    [result] = verify_claims(claims, _CONTEXT)
    assert result.verified
    assert result.group_key == "Acme Corp"
    assert result.field_key == "strengths"

    rejected = [
        ClaimDraft(
            section="competitor_analysis", text="Fast shipping", chunk_id="does-not-exist",
            group_key="Acme Corp", field_key="strengths",
        )
    ]
    [rejected_result] = verify_claims(rejected, _CONTEXT)
    assert not rejected_result.verified
    assert rejected_result.group_key == "Acme Corp"
    assert rejected_result.field_key == "strengths"


def test_bridge_claim_group_key_and_field_key_pass_through():
    run_chunk = Chunk(chunk_id="run1", kb_id="run:b", doc_id="d1", block_span=(0, 0), text="observed")
    core_chunk = Chunk(chunk_id="core1", kb_id="core:x@v1", doc_id="d2", block_span=(0, 0), text="benchmark")
    pairs = [BridgePair(run_chunk=run_chunk, core_chunk=core_chunk)]
    claims = [
        ClaimDraft(
            section="platform_analysis", text="High priority", chunk_id="run1", supporting_chunk_id="core1",
            group_key="Instagram", field_key="priority",
        )
    ]
    [result] = verify_bridge_claims(claims, pairs)
    assert result.verified
    assert result.group_key == "Instagram"
    assert result.field_key == "priority"


_UPSTREAM_VERIFIED = VerifiedClaim(
    claim_id="up1", section="brand_overview", text="Acme sells coffee.", chunk_id="c1",
    block_span=(0, 0), confidence=0.7, verified=True,
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
    assert result.confidence == 0.7  # inherited from the (only) upstream claim it cites


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
            **_COMPLETE_PERSONA_FIELDS,
        )
    ]
    [result] = verify_audience_personas(personas, _CONTEXT)
    assert result.verified
    assert result.rejection_reason is None
    assert result.persona_id
    assert result.confidence == 1.0
    assert result.age_range == "25-34"
    assert result.preferred_platforms == ["Instagram"]


def test_audience_persona_missing_age_range_rejected_as_incomplete():
    fields = {**_COMPLETE_PERSONA_FIELDS, "age_range": ""}
    personas = [
        AudiencePersonaDraft(
            section="target_audience", name="Weekend warrior",
            pain_points=["Limited free time"], interests=["Quality gear"], chunk_ids=["c1"],
            **fields,
        )
    ]
    [result] = verify_audience_personas(personas, _CONTEXT)
    assert not result.verified
    assert result.rejection_reason == "incomplete_persona"


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
            **_COMPLETE_PERSONA_FIELDS,
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
            **_COMPLETE_PERSONA_FIELDS,
        )
    ]
    [result] = verify_audience_personas(personas, _CONTEXT)
    assert not result.verified
    assert result.rejection_reason == "missing_chunk"
