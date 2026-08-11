from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from pydantic import BaseModel

from app.domain.chunk import Chunk
from app.domain.claim import ClaimDraft, VerifiedClaim
from app.domain_knowledge.store import DomainFact
from app.retrieval.bridge import BridgePair

_PROMPTS_DIR = Path(__file__).parent
_env = Environment(loader=FileSystemLoader(_PROMPTS_DIR), trim_blocks=True, lstrip_blocks=True)


class PlanContext(BaseModel):
    brand_id: str
    section_id: str
    section_label: str


class SynthesizeContext(BaseModel):
    section_id: str
    section_label: str
    chunks: list[Chunk]
    domain_facts: list[DomainFact] = []


class RepairContext(BaseModel):
    chunks: list[Chunk]
    rejected_claims: list[ClaimDraft]


class SynthesizeBridgeContext(BaseModel):
    section_id: str
    section_label: str
    pairs: list[BridgePair]
    domain_facts: list[DomainFact] = []


class UpstreamSectionClaims(BaseModel):
    section_label: str
    claims: list[VerifiedClaim]


class SynthesizeFromPriorContext(BaseModel):
    section_id: str
    section_label: str
    upstream: list[UpstreamSectionClaims]
    missing_sections: list[str] = []
    domain_facts: list[DomainFact] = []


def render_plan(ctx: PlanContext, version: str = "v1") -> str:
    return _env.get_template(f"plan/{version}.jinja").render(**ctx.model_dump())


def render_synthesize(ctx: SynthesizeContext, version: str = "v1") -> str:
    return _env.get_template(f"synthesize/{version}.jinja").render(**ctx.model_dump())


def render_repair(ctx: RepairContext, version: str = "v1") -> str:
    return _env.get_template(f"repair/{version}.jinja").render(**ctx.model_dump())


def render_synthesize_from_prior(ctx: SynthesizeFromPriorContext, version: str = "v1") -> str:
    return _env.get_template(f"synthesize_from_prior/{version}.jinja").render(**ctx.model_dump())


def render_synthesize_target_audience(ctx: SynthesizeContext, version: str = "v1") -> str:
    # Reuses SynthesizeContext's shape as-is (section_id/section_label/chunks/
    # domain_facts) -- the persona-extraction task only needs a different
    # template, not a different input shape.
    return _env.get_template(f"synthesize_target_audience/{version}.jinja").render(**ctx.model_dump())


def render_synthesize_bridge(ctx: SynthesizeBridgeContext, version: str = "v1") -> str:
    return _env.get_template(f"synthesize_bridge/{version}.jinja").render(**ctx.model_dump())
