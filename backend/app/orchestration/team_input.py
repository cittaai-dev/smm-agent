from app.domain.claim import VerifiedClaim
from app.domain.section_result import SectionResult
from app.domain.sop1 import SectionSpec
from app.domain.verify import compute_claim_id
from app.infra.db import get_session


def use_team_lead_input(brand_id: str, spec: SectionSpec) -> SectionResult:
    """business_goals (and any future direct_input section) isn't model-generated
    at all -- the SOP defines it as client/Team-Lead-authored. Forcing it through
    P4's citation verifier would be meaningless, so a team_provided claim is
    trivially verified (a human owns it directly, there's nothing to reject) --
    this is a deliberate carve-out, not a P4 violation."""
    with get_session() as session:
        row = session.execute(
            "SELECT text FROM team_input WHERE brand_id = :b AND section = :s",
            {"b": brand_id, "s": spec.id},
        ).mappings().first()

    if row is None:
        return SectionResult(
            section=spec.id,
            brand_id=brand_id,
            status="insufficient_evidence",
            note="Awaiting Team Lead input for this section",
        )

    claim = VerifiedClaim(
        claim_id=compute_claim_id(spec.id, row["text"]),
        section=spec.id,
        text=row["text"],
        verified=True,
    )
    return SectionResult(section=spec.id, brand_id=brand_id, status="team_provided", claims=[claim])
