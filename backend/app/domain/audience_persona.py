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
    # Persona-comparison-table fields (TEMPLATE_1_Market_Research.docx's
    # persona table: Name/Age range/Location/Occupation-income/Interests/Pain
    # points/Preferred platforms). Empty string/list, same as pain_points and
    # interests, when the evidence doesn't support them -- never fabricated.
    age_range: str = ""
    location: str = ""
    occupation_income: str = ""
    preferred_platforms: list[str] = []


class VerifiedAudiencePersona(BaseModel):
    persona_id: str
    section: str
    name: str
    pain_points: list[str] = []
    interests: list[str] = []
    chunk_ids: list[str] = []
    age_range: str = ""
    location: str = ""
    occupation_income: str = ""
    preferred_platforms: list[str] = []
    # P7: same confidence discipline as VerifiedClaim -- derived from the cited
    # chunks' order_confidence.
    confidence: float = 1.0
    verified: bool
    rejection_reason: Literal["no_citation", "missing_chunk", "incomplete_persona"] | None = None
