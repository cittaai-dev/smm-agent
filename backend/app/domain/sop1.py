from typing import Literal

from pydantic import BaseModel

SectionId = Literal[
    "brand_overview",
    "business_goals",
    "target_audience",
    "customer_needs",
    "market_overview",
    "competitor_analysis",
    "swot",
    "positioning_usp",
    "platform_analysis",
    "trends_opportunities",
    "key_takeaways",
]

RetrievalMode = Literal["union", "core_only", "bridge", "synthesis_only", "direct_input"]

# What a section's result means once a run finishes -- distinct from Deliverable/
# document-level approval status. "team_provided" is not a degrade state (P5) and
# not a grounding failure -- it's sections the SOP defines as client/Team-Lead
# authored input, never model-generated, so forcing them through citation
# verification would be meaningless.
SectionStatus = Literal["verified", "insufficient_evidence", "team_provided"]


class SectionSpec(BaseModel):
    id: SectionId
    label: str
    requires_core: bool
    retrieval_mode: RetrievalMode
    depends_on: list[SectionId] = []


SECTION_LABELS: dict[SectionId, str] = {
    "brand_overview": "Brand overview",
    "business_goals": "Business goals",
    "target_audience": "Target audience",
    "customer_needs": "Customer needs",
    "market_overview": "Market overview",
    "competitor_analysis": "Competitor analysis",
    "swot": "SWOT",
    "positioning_usp": "Positioning & USP",
    "platform_analysis": "Platform analysis",
    "trends_opportunities": "Trends & opportunities",
    "key_takeaways": "Key takeaways",
}

# Order matters: this is iteration order for run_all_sections, and every
# depends_on entry must already have appeared earlier in the list.
SOP1_SECTIONS: list[SectionSpec] = [
    SectionSpec(
        id="brand_overview",
        label=SECTION_LABELS["brand_overview"],
        requires_core=False,
        retrieval_mode="union",
    ),
    SectionSpec(
        id="business_goals",
        label=SECTION_LABELS["business_goals"],
        requires_core=False,
        retrieval_mode="direct_input",
    ),
    SectionSpec(
        id="target_audience",
        label=SECTION_LABELS["target_audience"],
        requires_core=False,
        retrieval_mode="union",
    ),
    SectionSpec(
        id="customer_needs",
        label=SECTION_LABELS["customer_needs"],
        requires_core=False,
        retrieval_mode="union",
    ),
    SectionSpec(
        id="market_overview",
        label=SECTION_LABELS["market_overview"],
        requires_core=True,
        retrieval_mode="core_only",
    ),
    SectionSpec(
        id="competitor_analysis",
        label=SECTION_LABELS["competitor_analysis"],
        requires_core=True,
        retrieval_mode="bridge",
    ),
    SectionSpec(
        id="swot",
        label=SECTION_LABELS["swot"],
        requires_core=False,
        retrieval_mode="synthesis_only",
        depends_on=[
            "brand_overview",
            "target_audience",
            "customer_needs",
            "market_overview",
            "competitor_analysis",
        ],
    ),
    SectionSpec(
        id="positioning_usp",
        label=SECTION_LABELS["positioning_usp"],
        requires_core=False,
        retrieval_mode="synthesis_only",
        depends_on=["swot"],
    ),
    SectionSpec(
        id="platform_analysis",
        label=SECTION_LABELS["platform_analysis"],
        requires_core=True,
        retrieval_mode="bridge",
    ),
    SectionSpec(
        id="trends_opportunities",
        label=SECTION_LABELS["trends_opportunities"],
        requires_core=True,
        retrieval_mode="core_only",
    ),
    SectionSpec(
        id="key_takeaways",
        label=SECTION_LABELS["key_takeaways"],
        requires_core=False,
        retrieval_mode="synthesis_only",
        depends_on=["swot", "positioning_usp", "platform_analysis", "trends_opportunities"],
    ),
]

SECTIONS_BY_ID: dict[str, SectionSpec] = {s.id: s for s in SOP1_SECTIONS}
