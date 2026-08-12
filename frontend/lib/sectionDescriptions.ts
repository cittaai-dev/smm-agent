import type { SectionId } from "./types";

// Byte-matches TEMPLATE_1_Market_Research.docx's per-section instruction
// line (docs/TEMPLATE_1_Market_Research.docx) -- static copy, not per-run
// data, same mirroring rationale as sections.ts/sectionLayout.ts.
export const SECTION_DESCRIPTIONS: Record<SectionId, string> = {
  brand_overview: "What the brand does, its products/services, history, and current situation.",
  business_goals:
    "What the brand wants from social media (awareness, followers, leads, sales) and its main objectives.",
  target_audience: "Describe the audience, then fill in 2 personas.",
  customer_needs: "The problems customers face and what they are looking for.",
  market_overview: "Market size, growth, current trends, opportunities, and challenges.",
  competitor_analysis: "List 3 to 5 main competitors.",
  swot: "The brand's strengths, weaknesses, opportunities, and threats.",
  positioning_usp: "What makes the brand different and why customers should choose it.",
  platform_analysis: "Mark where the audience is and set a priority for each platform.",
  trends_opportunities: "Popular topics, formats, hashtags, and seasonal moments to use.",
  key_takeaways: "A short summary of findings and what they mean for the strategy.",
};
