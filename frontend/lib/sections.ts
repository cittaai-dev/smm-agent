import type { SectionId } from "./types";

// Mirrors backend/app/domain/sop1.py's SECTION_LABELS/SOP1_SECTIONS. Order
// matters for display: it's dependency order (swot/positioning_usp/
// key_takeaways come after the sections they synthesize from), not just
// alphabetical -- and MarketResearchDocument.sections is a keyed object, not
// an array, so rendering needs an explicit order rather than relying on
// incidental key-order preservation across the Python dict -> JSON -> JS
// object boundary.
export const SECTION_ORDER: SectionId[] = [
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
];

export const SECTION_LABELS: Record<SectionId, string> = {
  brand_overview: "Brand overview",
  business_goals: "Business goals",
  target_audience: "Target audience",
  customer_needs: "Customer needs",
  market_overview: "Market overview",
  competitor_analysis: "Competitor analysis",
  swot: "SWOT",
  positioning_usp: "Positioning & USP",
  platform_analysis: "Platform analysis",
  trends_opportunities: "Trends & opportunities",
  key_takeaways: "Key takeaways",
};
