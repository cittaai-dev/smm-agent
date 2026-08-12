import { SECTION_LABELS, SECTION_ORDER } from "./sections";
import type { SectionId } from "./types";

// Hand-mirrors backend/app/domain/sop1.py's SOP1_SECTIONS retrieval_mode /
// requires_core -- static per-section structure, not per-run data, same
// rationale as SECTION_ORDER/SECTION_LABELS above mirroring sop1.py's
// id/label. Keep in sync by hand when sop1.py's registry changes.
export interface EvidencePill {
  label: string;
  tone: "neutral" | "core" | "lead" | "synth";
}

const EVIDENCE_PILLS: Record<SectionId, EvidencePill[]> = {
  brand_overview: [{ label: "Brand materials", tone: "neutral" }],
  business_goals: [{ label: "Team Lead confirmed", tone: "lead" }],
  target_audience: [{ label: "Brand materials", tone: "neutral" }],
  customer_needs: [{ label: "Brand materials", tone: "neutral" }],
  market_overview: [{ label: "Market Intel Core", tone: "core" }],
  competitor_analysis: [
    { label: "Brand materials", tone: "neutral" },
    { label: "Market Intel Core (bridge)", tone: "core" },
  ],
  swot: [{ label: "Synthesized from §1–6", tone: "synth" }],
  positioning_usp: [{ label: "Synthesized from SWOT", tone: "synth" }],
  platform_analysis: [
    { label: "Brand materials", tone: "neutral" },
    { label: "Market Intel Core (bridge)", tone: "core" },
  ],
  trends_opportunities: [{ label: "Market Intel Core", tone: "core" }],
  key_takeaways: [{ label: "Synthesized, last", tone: "synth" }],
};

export const RESEARCH_PLAN_SECTIONS = SECTION_ORDER.map((id, i) => ({
  n: i + 1,
  id,
  title: SECTION_LABELS[id],
  pills: EVIDENCE_PILLS[id],
}));
