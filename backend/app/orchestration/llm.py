from pydantic import BaseModel

from app.domain.audience_persona import AudiencePersonaDraft
from app.domain.claim import ClaimDraft, DerivedClaimDraft
from app.domain.cost import RunCostTracker
from app.domain.retrieval import RetrievalPlan, RetrievedContext
from app.domain.sop1 import SECTION_LABELS
from app.domain_knowledge.store import facts_for
from app.infra.circuit_breaker import CircuitBreaker
from app.infra.settings import circuit_breaker_settings, cost_budget_settings, llm_settings
from app.infra.telemetry import traced_call_site
from app.orchestration.tracing import traced_llm_call
from app.prompts.render import (
    PlanContext,
    RepairContext,
    SynthesizeBridgeContext,
    SynthesizeContext,
    SynthesizeFromPriorContext,
    UpstreamSectionClaims,
    render_plan,
    render_repair,
    render_synthesize,
    render_synthesize_bridge,
    render_synthesize_from_prior,
    render_synthesize_target_audience,
)
from app.retrieval.bridge import BridgePair


class LLMNotConfiguredError(RuntimeError):
    """Raised instead of letting the OpenAI SDK's own error surface -- that
    error tells the caller to set OPENAI_API_KEY, which does nothing here
    since this app reads SMM_LLM_OPENAI_API_KEY (env_prefix="SMM_LLM_")."""


class _PlanOutput(BaseModel):
    sub_queries: list[str]
    k_per_query: int = 8


class _SynthesisOutput(BaseModel):
    claims: list[ClaimDraft]


class _SynthesisWithPersonasOutput(BaseModel):
    claims: list[ClaimDraft]
    personas: list[AudiencePersonaDraft]


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


# Process-wide, not per-run: the point is to notice a provider outage across
# concurrent Celery tasks and stop piling up worker time, which only works if
# state survives across runs on the same worker (step6_production_operations.md
# Part A §2).
_breaker = CircuitBreaker(
    failure_threshold=circuit_breaker_settings.failure_threshold,
    reset_after_s=circuit_breaker_settings.reset_after_seconds,
)


def _chat_parse(
    *,
    model: str,
    messages: list[dict],
    response_format: type[BaseModel],
    temperature: float | None = None,
    cost_tracker: RunCostTracker | None = None,
):
    """The one place every call site's actual network call goes through --
    circuit-breaker wrapped (a 6th consecutive failure fails fast instead of
    timing out) and cost-tracked (raises CostBudgetExceeded before the run
    keeps spending), so neither concern has to be reimplemented per call site."""
    kwargs: dict = {"model": model, "messages": messages, "response_format": response_format}
    if temperature is not None:
        kwargs["temperature"] = temperature

    def _call():
        return _client().beta.chat.completions.parse(**kwargs)

    completion = _breaker.call(_call)

    if cost_tracker is not None and completion.usage is not None:
        tokens = completion.usage.total_tokens
        usd = (tokens / 1000) * cost_budget_settings.usd_per_1k_tokens
        cost_tracker.record(tokens=tokens, usd=usd)

    return completion.choices[0].message.parsed


@traced_llm_call("plan")
@traced_call_site("plan")
def call_plan(section: str, brand_id: str, cost_tracker: RunCostTracker | None = None) -> RetrievalPlan:
    prompt = render_plan(
        PlanContext(brand_id=brand_id, section_id=section, section_label=SECTION_LABELS[section])
    )
    parsed = _chat_parse(
        model=llm_settings.plan_model,
        messages=[{"role": "system", "content": prompt}],
        response_format=_PlanOutput,
        cost_tracker=cost_tracker,
    )
    return RetrievalPlan(sub_queries=parsed.sub_queries, k_per_query=parsed.k_per_query)


@traced_llm_call("synthesize")
@traced_call_site("synthesize")
def call_synthesize(
    section: str, context: RetrievedContext, cost_tracker: RunCostTracker | None = None
) -> list[ClaimDraft]:
    ctx = SynthesizeContext(
        section_id=section,
        section_label=SECTION_LABELS[section],
        chunks=context.chunks,
        domain_facts=facts_for(section),
    )
    prompt = render_synthesize(ctx)
    parsed = _chat_parse(
        model=llm_settings.synthesize_model,
        temperature=llm_settings.synthesize_temperature,
        messages=[{"role": "system", "content": prompt}],
        response_format=_SynthesisOutput,
        cost_tracker=cost_tracker,
    )
    return parsed.claims


@traced_llm_call("synthesize")
@traced_call_site("synthesize")
def call_synthesize_with_personas(
    section: str, context: RetrievedContext, cost_tracker: RunCostTracker | None = None
) -> tuple[list[ClaimDraft], list[AudiencePersonaDraft]]:
    """Same call site as call_synthesize (P2 counts it once) -- one combined
    structured output (claims + personas) in a single call, not two separate
    generative calls, which would make this a 4th call site in spirit even if
    call-count tracing didn't happen to enforce it."""
    ctx = SynthesizeContext(
        section_id=section,
        section_label=SECTION_LABELS[section],
        chunks=context.chunks,
        domain_facts=facts_for(section),
    )
    prompt = render_synthesize_target_audience(ctx)
    parsed = _chat_parse(
        model=llm_settings.synthesize_model,
        temperature=llm_settings.synthesize_temperature,
        messages=[{"role": "system", "content": prompt}],
        response_format=_SynthesisWithPersonasOutput,
        cost_tracker=cost_tracker,
    )
    return parsed.claims, parsed.personas


@traced_llm_call("synthesize")
@traced_call_site("synthesize")
def call_synthesize_from_prior(
    section: str,
    upstream: list[UpstreamSectionClaims],
    missing_sections: list[str],
    cost_tracker: RunCostTracker | None = None,
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
    parsed = _chat_parse(
        model=llm_settings.synthesize_model,
        temperature=llm_settings.synthesize_temperature,
        messages=[{"role": "system", "content": prompt}],
        response_format=_DerivedSynthesisOutput,
        cost_tracker=cost_tracker,
    )
    return parsed.claims


@traced_llm_call("synthesize")
@traced_call_site("synthesize")
def call_synthesize_bridge(
    section: str, pairs: list[BridgePair], cost_tracker: RunCostTracker | None = None
) -> list[ClaimDraft]:
    """Same call site as call_synthesize (P2 counts it once) -- BRIDGE mode's
    input shape is pairs, not raw chunks, but it's still exactly one
    generative call per section run, same as every other synthesize variant."""
    ctx = SynthesizeBridgeContext(
        section_id=section,
        section_label=SECTION_LABELS[section],
        pairs=pairs,
        domain_facts=facts_for(section),
    )
    prompt = render_synthesize_bridge(ctx)
    parsed = _chat_parse(
        model=llm_settings.synthesize_model,
        temperature=llm_settings.synthesize_temperature,
        messages=[{"role": "system", "content": prompt}],
        response_format=_SynthesisOutput,
        cost_tracker=cost_tracker,
    )
    return parsed.claims


@traced_llm_call("repair")
@traced_call_site("repair")
def call_repair(
    claims: list[ClaimDraft], context: RetrievedContext, cost_tracker: RunCostTracker | None = None
) -> list[ClaimDraft]:
    known_ids = {c.chunk_id for c in context.chunks}
    rejected = [c for c in claims if c.chunk_id is None or c.chunk_id not in known_ids]
    if not rejected:
        return claims

    prompt = render_repair(RepairContext(chunks=context.chunks, rejected_claims=rejected))
    parsed = _chat_parse(
        model=llm_settings.repair_model,
        messages=[{"role": "system", "content": prompt}],
        response_format=_SynthesisOutput,
        cost_tracker=cost_tracker,
    )

    fixed_by_text = {c.text: c for c in parsed.claims}
    return [fixed_by_text.get(c.text, c) for c in claims]
