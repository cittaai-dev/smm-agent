export interface BrandRunStepDef {
  title: string;
  desc: string;
  // Segment under /brands/[id]/run/. Empty string for the final step, which
  // lives outside this route group at /documents/[id] (a different id-space
  // -- document id, not brand id -- only known once a run has completed).
  path: string;
}

export const BRAND_RUN_STEPS: BrandRunStepDef[] = [
  { title: "Onboard a Brand", desc: "Brand intake", path: "onboard" },
  { title: "Document Understanding", desc: "Read & chunk", path: "plan" },
  { title: "Research Plan", desc: "Document outline", path: "research-plan" },
  { title: "Competitor & Market Analysis", desc: "Live scan", path: "competitors" },
  { title: "Synthesize Findings", desc: "Draft & verify", path: "synthesize" },
  { title: "Market Research Report", desc: "Cited deliverable", path: "" },
];
