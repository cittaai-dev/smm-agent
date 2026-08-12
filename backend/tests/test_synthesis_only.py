from app.domain.claim import DerivedClaimDraft, VerifiedClaim
from app.domain.section_result import SectionResult
from app.domain.sop1 import SECTIONS_BY_ID
from app.orchestration.section_runner import run_section

_UPSTREAM_CLAIM = VerifiedClaim(
    claim_id="claim-1", section="brand_overview", text="Acme sells specialty coffee.",
    chunk_id="c1", block_span=(0, 0), verified=True,
)


def _verified_prior(section: str, claim: VerifiedClaim = _UPSTREAM_CLAIM) -> SectionResult:
    return SectionResult(section=section, brand_id="brand-x", status="verified", claims=[claim])


def _insufficient_prior(section: str) -> SectionResult:
    return SectionResult(section=section, brand_id="brand-x", status="insufficient_evidence")


def test_synthesis_only_degrades_without_llm_call_when_no_deps_available():
    spec = SECTIONS_BY_ID["positioning_usp"]  # depends_on=["swot"]
    prior = {"swot": _insufficient_prior("swot")}

    result = run_section("brand-x", spec, prior)

    assert result.status == "insufficient_evidence"
    assert result.call_site_trace == {}  # no LLM call burned on nothing to synthesize from


def test_synthesis_only_synthesizes_from_available_deps(monkeypatch):
    def _fake(section, upstream, missing_sections, **kwargs):
        [claim] = upstream[0].claims
        return [DerivedClaimDraft(section=section, text="Derived claim", source_claim_ids=[claim.claim_id])]

    monkeypatch.setattr("app.orchestration.llm.call_synthesize_from_prior", _fake)

    spec = SECTIONS_BY_ID["positioning_usp"]
    prior = {"swot": _verified_prior("swot")}

    result = run_section("brand-x", spec, prior)

    assert result.status == "verified"
    assert result.call_site_trace == {"plan": 0, "synthesize": 1, "repair": 0}
    [claim] = result.claims
    assert claim.verified
    assert claim.source_claim_ids == ["claim-1"]


def test_synthesis_only_rejects_claim_citing_unverified_upstream_id(monkeypatch):
    def _fake(section, upstream, missing_sections, **kwargs):
        return [DerivedClaimDraft(section=section, text="Fabricated", source_claim_ids=["not-a-real-id"])]

    monkeypatch.setattr("app.orchestration.llm.call_synthesize_from_prior", _fake)

    spec = SECTIONS_BY_ID["positioning_usp"]
    prior = {"swot": _verified_prior("swot")}

    result = run_section("brand-x", spec, prior)

    assert result.status == "insufficient_evidence"
    [claim] = result.claims
    assert not claim.verified
    assert claim.rejection_reason == "missing_source_claim"


def test_key_takeaways_synthesizes_from_partial_deps_when_core_sections_unavailable(monkeypatch):
    # key_takeaways depends on swot, positioning_usp, platform_analysis,
    # trends_opportunities -- the latter two are Core-gated and guaranteed
    # insufficient_evidence in Step 2. It must still synthesize from whatever
    # IS available rather than cascading to insufficient_evidence on any single
    # missing dep (that would make it permanently degraded until Step 4).
    captured = {}

    def _fake(section, upstream, missing_sections, **kwargs):
        captured["missing_sections"] = missing_sections
        claim = upstream[0].claims[0]
        return [DerivedClaimDraft(section=section, text="Key takeaway", source_claim_ids=[claim.claim_id])]

    monkeypatch.setattr("app.orchestration.llm.call_synthesize_from_prior", _fake)

    spec = SECTIONS_BY_ID["key_takeaways"]
    prior = {
        "swot": _verified_prior("swot"),
        "positioning_usp": _insufficient_prior("positioning_usp"),
        "platform_analysis": _insufficient_prior("platform_analysis"),
        "trends_opportunities": _insufficient_prior("trends_opportunities"),
    }

    result = run_section("brand-x", spec, prior)

    assert result.status == "verified"
    assert len(captured["missing_sections"]) == 3


def test_swot_synthesizes_with_bucket_field_key(monkeypatch):
    # swot is the one synthesis_only section with structured_fields set
    # (sop1.py) -- proves the bucket tag actually reaches SECTIONS_BY_ID's
    # caller and survives verify_derived_claims untouched.
    captured = {}

    def _fake(section, upstream, missing_sections, structured_fields=None, **kwargs):
        captured["structured_fields"] = structured_fields
        [claim] = upstream[0].claims
        return [
            DerivedClaimDraft(
                section=section, text="Deep DISCOM experience", source_claim_ids=[claim.claim_id],
                field_key="strength",
            )
        ]

    monkeypatch.setattr("app.orchestration.llm.call_synthesize_from_prior", _fake)

    spec = SECTIONS_BY_ID["swot"]
    prior = {dep: _verified_prior(dep) for dep in spec.depends_on}

    result = run_section("brand-x", spec, prior)

    assert result.status == "verified"
    assert captured["structured_fields"] == ["strength", "weakness", "opportunity", "threat"]
    [claim] = result.claims
    assert claim.field_key == "strength"
