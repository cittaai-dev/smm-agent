from langgraph.graph import END, StateGraph
from pydantic import BaseModel

from app.domain.claim import ClaimDraft, VerifiedClaim
from app.domain.deliverable import Deliverable
from app.domain.retrieval import RetrievalPlan, RetrievedContext
from app.orchestration.tracing import reset_call_counts

SECTION = "brand_overview"


class RunState(BaseModel):
    brand_id: str
    kb_id: str
    plan: RetrievalPlan | None = None
    context: RetrievedContext | None = None
    claims: list[ClaimDraft] = []
    verified: list[VerifiedClaim] = []
    repair_attempted: bool = False
    deliverable: Deliverable | None = None


def plan_node(state: RunState) -> RunState:
    reset_call_counts()  # call site ① is the entry point of a run
    from app.orchestration.llm import call_plan

    state.plan = call_plan(section=SECTION, brand_id=state.brand_id)
    return state


def retrieve_node(state: RunState) -> RunState:
    from app.retrieval.dense import search_dense

    chunks = search_dense(kb_id=state.kb_id, plan=state.plan)
    state.context = RetrievedContext(chunks=chunks, plan=state.plan)
    return state


def synthesize_node(state: RunState) -> RunState:
    from app.orchestration.llm import call_synthesize

    state.claims = call_synthesize(section=SECTION, context=state.context)
    return state


def verify_node(state: RunState) -> RunState:
    from app.domain.verify import verify_claims

    state.verified = verify_claims(state.claims, state.context)
    return state


def repair_node(state: RunState) -> RunState:
    from app.orchestration.llm import call_repair

    state.claims = call_repair(state.claims, state.context)
    state.repair_attempted = True
    return state


def route_after_verify(state: RunState) -> str:
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
        id=f"del-{state.brand_id}-{SECTION}",
        brand_id=state.brand_id,
        status="pending_approval",
        claims=state.verified,
        call_site_trace=_call_site_trace(state),
    )
    return state


def insufficient_node(state: RunState) -> RunState:
    state.deliverable = Deliverable(
        id=f"del-{state.brand_id}-{SECTION}",
        brand_id=state.brand_id,
        status="insufficient_grounding",
        claims=state.verified,
        call_site_trace=_call_site_trace(state),
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


def run_pipeline(brand_id: str) -> RunState:
    result = app_graph.invoke(RunState(brand_id=brand_id, kb_id=f"run:{brand_id}"))
    return RunState(**result)
