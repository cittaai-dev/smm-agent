from pydantic import BaseModel

from app.domain.claim import ClaimDraft, DerivedClaimDraft
from app.domain.retrieval import RetrievalPlan, RetrievedContext
from app.domain.sop1 import SECTION_LABELS
from app.domain_knowledge.store import facts_for
from app.infra.settings import llm_settings
from app.orchestration.tracing import traced_llm_call
from app.prompts.render import (
    PlanContext,
    RepairContext,
    SynthesizeContext,
    SynthesizeFromPriorContext,
    UpstreamSectionClaims,
    render_plan,
    render_repair,
    render_synthesize,
    render_synthesize_from_prior,
)


class LLMNotConfiguredError(RuntimeError):
    """Raised instead of letting the OpenAI SDK's own error surface -- that
    error tells the caller to set OPENAI_API_KEY, which does nothing here
    since this app reads SMM_LLM_OPENAI_API_KEY (env_prefix="SMM_LLM_")."""


class _PlanOutput(BaseModel):
    sub_queries: list[str]
    k_per_query: int = 8


class _SynthesisOutput(BaseModel):
    claims: list[ClaimDraft]


class _DerivedSynthesisOutput(BaseModel):
    claims: list[DerivedClaimDraft]


def _client():
    if not llm_settings.openai_api_key:
        raise LLMNotConfiguredError(
            "SMM_LLM_OPENAI_API_KEY is not set. Add it to backend/.env "
            "(see backend/.env.example) or export it, then restart the backend."
        )
    from openai import OpenAI

    return OpenAI(api_key=llm_settings.openai_api_key)


@traced_llm_call("plan")
def call_plan(section: str, brand_id: str) -> RetrievalPlan:
    prompt = render_plan(
        PlanContext(brand_id=brand_id, section_id=section, section_label=SECTION_LABELS[section])
    )
    parsed = _client().beta.chat.completions.parse(
        model=llm_settings.plan_model,
        messages=[{"role": "system", "content": prompt}],
        response_format=_PlanOutput,
    ).choices[0].message.parsed
    return RetrievalPlan(sub_queries=parsed.sub_queries, k_per_query=parsed.k_per_query)


@traced_llm_call("synthesize")
def call_synthesize(section: str, context: RetrievedContext) -> list[ClaimDraft]:
    ctx = SynthesizeContext(
        section_id=section,
        section_label=SECTION_LABELS[section],
        chunks=context.chunks,
        domain_facts=facts_for(section),
    )
    prompt = render_synthesize(ctx)
    parsed = _client().beta.chat.completions.parse(
        model=llm_settings.synthesize_model,
        temperature=llm_settings.synthesize_temperature,
        messages=[{"role": "system", "content": prompt}],
        response_format=_SynthesisOutput,
    ).choices[0].message.parsed
    return parsed.claims


@traced_llm_call("synthesize")
def call_synthesize_from_prior(
    section: str, upstream: list[UpstreamSectionClaims], missing_sections: list[str]
) -> list[DerivedClaimDraft]:
    """Same call site as call_synthesize (P2 counts it once, not twice) -- just a
    different template/input shape, for synthesis_only sections that derive from
    upstream verified claims instead of raw evidence chunks."""
    ctx = SynthesizeFromPriorContext(
        section_id=section,
        section_label=SECTION_LABELS[section],
        upstream=upstream,
        missing_sections=missing_sections,
        domain_facts=facts_for(section),
    )
    prompt = render_synthesize_from_prior(ctx)
    parsed = _client().beta.chat.completions.parse(
        model=llm_settings.synthesize_model,
        temperature=llm_settings.synthesize_temperature,
        messages=[{"role": "system", "content": prompt}],
        response_format=_DerivedSynthesisOutput,
    ).choices[0].message.parsed
    return parsed.claims


@traced_llm_call("repair")
def call_repair(claims: list[ClaimDraft], context: RetrievedContext) -> list[ClaimDraft]:
    known_ids = {c.chunk_id for c in context.chunks}
    rejected = [c for c in claims if c.chunk_id is None or c.chunk_id not in known_ids]
    if not rejected:
        return claims

    prompt = render_repair(RepairContext(chunks=context.chunks, rejected_claims=rejected))
    parsed = _client().beta.chat.completions.parse(
        model=llm_settings.repair_model,
        messages=[{"role": "system", "content": prompt}],
        response_format=_SynthesisOutput,
    ).choices[0].message.parsed

    fixed_by_text = {c.text: c for c in parsed.claims}
    return [fixed_by_text.get(c.text, c) for c in claims]
