import type { SectionId } from "./types";

// Mirrors backend/app/domain/sop1.py's SectionSpec.structured_* fields --
// static per-section structure, not per-run data, same rationale as
// SECTION_ORDER/SECTION_LABELS (sections.ts) mirroring sop1.py's id/label.
export type StructuredOutput = "competitor_table" | "platform_table" | "swot_grid" | null;

export interface SectionLayout {
  structuredOutput: StructuredOutput;
  groupLabel: string | null;
  fields: string[];
  rowValues: string[];
}

const PROSE: SectionLayout = { structuredOutput: null, groupLabel: null, fields: [], rowValues: [] };

// Platform analysis's fixed row set -- must match sop1.py's PLATFORM_NAMES.
export const PLATFORM_NAMES = [
  "Instagram",
  "Facebook",
  "LinkedIn",
  "YouTube",
  "X (Twitter)",
  "Threads",
  "Pinterest",
];

export const SECTION_LAYOUT: Record<SectionId, SectionLayout> = {
  brand_overview: PROSE,
  business_goals: PROSE,
  target_audience: PROSE,
  customer_needs: PROSE,
  market_overview: PROSE,
  competitor_analysis: {
    structuredOutput: "competitor_table",
    groupLabel: "competitor",
    fields: ["offer_positioning", "strengths", "weaknesses", "content_frequency", "gaps_to_use"],
    rowValues: [],
  },
  swot: {
    structuredOutput: "swot_grid",
    groupLabel: null,
    fields: ["strength", "weakness", "opportunity", "threat"],
    rowValues: [],
  },
  positioning_usp: PROSE,
  platform_analysis: {
    structuredOutput: "platform_table",
    groupLabel: "platform",
    fields: ["audience_here", "priority", "notes"],
    rowValues: PLATFORM_NAMES,
  },
  trends_opportunities: PROSE,
  key_takeaways: PROSE,
};

export const FIELD_LABELS: Record<string, string> = {
  offer_positioning: "Offer & positioning",
  strengths: "Strengths",
  weaknesses: "Weaknesses",
  content_frequency: "Content & frequency",
  gaps_to_use: "Gaps to use",
  audience_here: "Audience here? (Yes/No)",
  priority: "Priority (High/Med/Low)",
  notes: "Notes",
};
