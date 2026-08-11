from app.domain.section_result import SectionResult
from app.domain.sop1 import SECTION_LABELS, SectionSpec
from app.domain.verify import verify_derived_claims
from app.prompts.render import UpstreamSectionClaims


def run_synthesis_only(brand_id: str, spec: SectionSpec, prior: dict[str, SectionResult]) -> SectionResult:
    from app.orchestration.llm import call_synthesize_from_prior
    from app.orchestration.tracing import reset_call_counts

    upstream: list[UpstreamSectionClaims] = []
    missing_sections: list[str] = []
    all_upstream_claims = []
    for dep in spec.depends_on:
        dep_result = prior.get(dep)
        dep_usable = (
            dep_result is not None
            and dep_result.status in ("verified", "team_provided")
            and dep_result.claims
        )
        if not dep_usable:
            missing_sections.append(SECTION_LABELS[dep])
            continue
        upstream.append(
            UpstreamSectionClaims(section_label=SECTION_LABELS[dep], claims=dep_result.claims)
        )
        all_upstream_claims.extend(dep_result.claims)

    if not all_upstream_claims:
        # Nothing to synthesize from at all -- degrade without burning a call
        # site (same discipline as the union path skipping repair on an empty
        # claim list). Cascading only when *every* dep is unavailable, not on
        # any single missing dep, matters most for key_takeaways: it depends on
        # two Core-gated sections that are guaranteed insufficient_evidence
        # until Step 4, and cascading on "any missing dep" would make it
        # permanently degraded rather than synthesizing from what does exist.
        return SectionResult(
            section=spec.id,
            brand_id=brand_id,
            status="insufficient_evidence",
            note=f"No verified upstream findings available yet ({', '.join(missing_sections)})",
        )

    reset_call_counts()  # this section's run doesn't go through plan_node
    claims = call_synthesize_from_prior(spec.id, upstream, missing_sections)
    verified = verify_derived_claims(claims, all_upstream_claims)

    if not verified or not all(c.verified for c in verified):
        return SectionResult(
            section=spec.id,
            brand_id=brand_id,
            status="insufficient_evidence",
            claims=verified,  # kept, even when rejected, for audit (P7) -- mirrors the union path
            call_site_trace={"plan": 0, "synthesize": 1, "repair": 0},
        )

    return SectionResult(
        section=spec.id,
        brand_id=brand_id,
        status="verified",
        claims=verified,
        call_site_trace={"plan": 0, "synthesize": 1, "repair": 0},
    )
