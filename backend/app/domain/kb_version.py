from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class EvalGateResult(BaseModel):
    """Zero-LLM, arithmetic-only verdict over an already-verified corpus
    (app/eval/gate.py) -- the eval gate is necessary, not sufficient; a
    passing corpus still requires an explicit human /decide call."""

    citation_rejection_rate: float
    degraded_ratio: float
    l0_ratio: float
    coverage_ok: bool
    passed: bool
    thresholds: dict[str, float]


class KBVersion(BaseModel):
    kb_id: str  # "core:market-intel@v1" once promoted; "...@v1:staging" before
    version: int
    status: Literal["staging", "promoted", "rejected"]
    eval_gate_result: EvalGateResult | None = None
    promoted_at: datetime | None = None
    promoted_by: str | None = None


class GoldenCase(BaseModel):
    """A fixed (topic, section, expected-evidence) triple the eval gate replays
    synthesis against -- not a real brand run, so it never touches a run:<brand_id>
    KB. fixture_chunks stand in for what search_hybrid would have returned,
    keeping the gate deterministic across re-runs of the same staging corpus."""

    id: str
    topic: str
    section: str
    fixture_chunks: list[str] = []
