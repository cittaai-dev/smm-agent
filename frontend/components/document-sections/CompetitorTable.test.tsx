import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { CompetitorTable } from "./CompetitorTable";
import type { VerifiedClaim } from "@/lib/types";

function claim(overrides: Partial<VerifiedClaim>): VerifiedClaim {
  return {
    claim_id: "c1",
    section: "competitor_analysis",
    text: "x",
    chunk_id: "chunk-1",
    source_claim_ids: [],
    block_span: [0, 0],
    confidence: 1,
    verified: true,
    rejection_reason: null,
    group_key: null,
    field_key: null,
    ...overrides,
  };
}

describe("CompetitorTable", () => {
  it("groups claims into rows by competitor and columns by field", () => {
    const claims = [
      claim({ claim_id: "1", text: "Fast shipping", group_key: "Acme Corp", field_key: "strengths" }),
      claim({ claim_id: "2", text: "Slow support", group_key: "Acme Corp", field_key: "weaknesses" }),
      claim({ claim_id: "3", text: "Cheap pricing", group_key: "Beta Inc", field_key: "strengths" }),
    ];
    render(<CompetitorTable claims={claims} />);

    expect(screen.getByText("Acme Corp")).toBeInTheDocument();
    expect(screen.getByText("Beta Inc")).toBeInTheDocument();
    expect(screen.getByText("Fast shipping")).toBeInTheDocument();
    expect(screen.getByText("Offer & positioning")).toBeInTheDocument();
  });

  it("ignores unverified or untagged claims when grouping", () => {
    const claims = [
      claim({ claim_id: "1", text: "Rejected", group_key: "Acme Corp", field_key: "strengths", verified: false }),
      claim({ claim_id: "2", text: "Untagged", group_key: null, field_key: null }),
    ];
    render(<CompetitorTable claims={claims} />);
    expect(screen.getByText("No verified competitors yet.")).toBeInTheDocument();
  });
});
