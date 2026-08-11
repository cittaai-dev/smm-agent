import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { SectionRow } from "./SectionRow";
import type { SectionResult } from "@/lib/types";

const base: SectionResult = {
  section: "brand_overview",
  brand_id: "acme",
  status: "verified",
  claims: [],
  personas: [],
  call_site_trace: {},
  cost_usd: 0,
};

describe("SectionRow", () => {
  it("shows the section's human label, not the raw id", () => {
    render(<SectionRow section={{ ...base, section: "positioning_usp" }} />);
    expect(screen.getByText("Positioning & USP")).toBeInTheDocument();
  });

  it("shows claim count for a verified section", () => {
    const claim = {
      claim_id: "c1", section: "brand_overview", text: "x", chunk_id: "abc",
      source_claim_ids: [], block_span: [0, 0] as [number, number], verified: true, rejection_reason: null,
    };
    render(<SectionRow section={{ ...base, claims: [claim, claim] }} />);
    expect(screen.getByText("2 claims verified")).toBeInTheDocument();
  });

  it("shows the section's own note for insufficient_evidence, not a generic message", () => {
    render(
      <SectionRow
        section={{
          ...base,
          status: "insufficient_evidence",
          note: "Market Intel Core not yet available -- deferred to Step 4",
        }}
      />,
    );
    expect(screen.getByText(/deferred to Step 4/)).toBeInTheDocument();
  });

  it("shows 'Provided by Team Lead' for team_provided sections", () => {
    render(<SectionRow section={{ ...base, section: "business_goals", status: "team_provided" }} />);
    expect(screen.getByText("Provided by Team Lead")).toBeInTheDocument();
  });
});
