from langgraph.graph import END, StateGraph
from pydantic import BaseModel, ConfigDict, Field

from app.domain.audience_persona import AudiencePersonaDraft, VerifiedAudiencePersona
from app.domain.claim import ClaimDraft, VerifiedClaim
from app.domain.cost import CostBudget, CostBudgetExceeded, RunCostTracker
from app.domain.deliverable import Deliverable
from app.domain.retrieval import RetrievalPlan, RetrievedContext
from app.domain.sop1 import SectionId
from app.infra.circuit_breaker import CircuitOpenError


class RunState(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    brand_id: str
    kb_id: str
    section: SectionId
    plan: RetrievalPlan | None = None
    context: RetrievedContext | None = None
    claims: list[ClaimDraft] = []
    verified: list[VerifiedClaim] = []
    # target_audience only (SectionSpec.extracts_audience_personas) -- empty
    # for every other section.
    persona_drafts: list[AudiencePersonaDraft] = []
    personas: list[VerifiedAudiencePersona] = []
    repair_attempted: bool = False
    deliverable: Deliverable | None = None
    cost_tracker: RunCostTracker = Field(default_factory=RunCostTracker)
    # Set by plan/synthesize/repair nodes on a cost overrun or provider outage --
    # every subsequent node short-circuits so the run reaches insufficient_grounding
    # through the same route_after_verify branch an evidence gap uses (P5: one
    # failure vocabulary, distinguished only by Deliverable.reason).
    degrade_reason: str | None = None


def plan_node(state: RunState) -> RunState:
    from app.orchestration.llm import call_plan

    try:
        state.plan = call_plan(section=state.section, brand_id=state.brand_id, cost_tracker=state.cost_tracker)
    except CostBudgetExceeded:
        state.degrade_reason = "cost_budget_exceeded"
    except CircuitOpenError:
        state.degrade_reason = "llm_provider_unavailable"
    return state


def retrieve_node(state: RunState) -> RunState:
    if state.degrade_reason:
        return state

    from app.retrieval.hybrid import search_hybrid

    chunks = search_hybrid(kb_id=state.kb_id, plan=state.plan)
    state.context = RetrievedContext(chunks=chunks, plan=state.plan)
    return state


def synthesize_node(state: RunState) -> RunState:
    if state.degrade_reason:
        return state

    from app.domain.sop1 import SECTIONS_BY_ID

    try:
        if SECTIONS_BY_ID[state.section].extracts_audience_personas:
            from app.orchestration.llm import call_synthesize_with_personas

            state.claims, state.persona_drafts = call_synthesize_with_personas(
                section=state.section, context=state.context, cost_tracker=state.cost_tracker
            )
        else:
            from app.orchestration.llm import call_synthesize

            state.claims = call_synthesize(
                section=state.section, context=state.context, cost_tracker=state.cost_tracker
            )
    except CostBudgetExceeded:
        state.degrade_reason = "cost_budget_exceeded"
    except CircuitOpenError:
        state.degrade_reason = "llm_provider_unavailable"
    return state


def verify_node(state: RunState) -> RunState:
    if state.degrade_reason:
        return state

    from app.domain.verify import verify_audience_personas, verify_claims

    state.verified = verify_claims(state.claims, state.context)
    if state.persona_drafts:
        state.personas = verify_audience_personas(state.persona_drafts, state.context)
    return state


def repair_node(state: RunState) -> RunState:
    from app.orchestration.llm import call_repair

    try:
        state.claims = call_repair(state.claims, state.context, cost_tracker=state.cost_tracker)
    except CostBudgetExceeded:
        state.degrade_reason = "cost_budget_exceeded"
    except CircuitOpenError:
        state.degrade_reason = "llm_provider_unavailable"
    state.repair_attempted = True
    return state


def route_after_verify(state: RunState) -> str:
    # all(...) on an empty list is vacuously True -- zero claims must never
    # read as "everything verified." Repair is also pointless here: call_repair
    # only re-tags claims whose chunk_id doesn't resolve, so on an empty list
    # it's a no-op call site burned for nothing. Go straight to
    # insufficient_grounding (P5: degrade, never silently pass empty as good).
    if not state.verified:
        return "insufficient_grounding"
    all_ok = all(c.verified for c in state.verified)
    if all_ok:
        return "deliver"
    if state.repair_attempted:
        return "insufficient_grounding"
    return "repair"


def _call_site_trace(state: RunState) -> dict[str, int]:
    # Graph-structural truth, not a side-effect counter: plan+synthesize always run
    # exactly once per invoke(), repair runs 0 or 1 times, enforced by the
    # conditional edge on "verify" (route_after_verify), not by this function.
    return {"plan": 1, "synthesize": 1, "repair": int(state.repair_attempted)}


def deliver_node(state: RunState) -> RunState:
    state.deliverable = Deliverable(
        id=f"del-{state.brand_id}-{state.section}",
        brand_id=state.brand_id,
        status="pending_approval",
        claims=state.verified,
        call_site_trace=_call_site_trace(state),
        cost_usd=state.cost_tracker.usd_spent,
    )
    return state


def insufficient_node(state: RunState) -> RunState:
    state.deliverable = Deliverable(
        id=f"del-{state.brand_id}-{state.section}",
        brand_id=state.brand_id,
        status="insufficient_grounding",
        claims=state.verified,
        call_site_trace=_call_site_trace(state),
        reason=state.degrade_reason,
        cost_usd=state.cost_tracker.usd_spent,
    )
    return state


def build_graph():
    graph = StateGraph(RunState)
    graph.add_node("plan", plan_node)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("synthesize", synthesize_node)
    graph.add_node("verify", verify_node)
    graph.add_node("repair", repair_node)
    graph.add_node("deliver", deliver_node)
    graph.add_node("insufficient_grounding", insufficient_node)

    graph.set_entry_point("plan")
    graph.add_edge("plan", "retrieve")
    graph.add_edge("retrieve", "synthesize")
    graph.add_edge("synthesize", "verify")
    graph.add_conditional_edges(
        "verify",
        route_after_verify,
        {"deliver": "deliver", "repair": "repair", "insufficient_grounding": "insufficient_grounding"},
    )
    graph.add_edge("repair", "verify")
    graph.add_edge("deliver", END)
    graph.add_edge("insufficient_grounding", END)
    return graph.compile()


app_graph = build_graph()


def run_pipeline(
    brand_id: str, section: SectionId = "brand_overview", budget: CostBudget | None = None
) -> RunState:
    import time

    from app.infra.telemetry import record_run
    from app.orchestration.tracing import reset_call_counts

    reset_call_counts()  # call site ① is the entry point of a run
    initial = RunState(
        brand_id=brand_id,
        kb_id=f"run:{brand_id}",
        section=section,
        cost_tracker=RunCostTracker(budget),
    )
    started = time.monotonic()
    result = app_graph.invoke(initial)
    state = RunState(**result)
    record_run(duration_s=time.monotonic() - started, usd_spent=state.cost_tracker.usd_spent)
    return state
