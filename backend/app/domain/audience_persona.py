from typing import Literal

from pydantic import BaseModel

from app.domain.sop1 import SectionId

# Named "AudiencePersona", not "Persona" -- prompts/partials/persona.jinja
# already means something else entirely (the LLM's own voice/role), and
# reusing the word for a buyer-persona domain type in the same codebase would
# be genuinely confusing, not just a style nitpick.


class AudiencePersonaDraft(BaseModel):
    section: SectionId
    name: str
    pain_points: list[str] = []
    interests: list[str] = []
    chunk_ids: list[str] = []


class VerifiedAudiencePersona(BaseModel):
    persona_id: str
    section: str
    name: str
    pain_points: list[str] = []
    interests: list[str] = []
    chunk_ids: list[str] = []
    verified: bool
    rejection_reason: Literal["no_citation", "missing_chunk", "incomplete_persona"] | None = None
