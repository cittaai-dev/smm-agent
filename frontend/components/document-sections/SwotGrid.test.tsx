import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { SwotGrid } from "./SwotGrid";
import type { VerifiedClaim } from "@/lib/types";

function claim(overrides: Partial<VerifiedClaim>): VerifiedClaim {
  return {
    claim_id: "c1",
    section: "swot",
    text: "x",
    chunk_id: "",
    source_claim_ids: ["up1"],
    block_span: [0, 0],
    confidence: 1,
    verified: true,
    rejection_reason: null,
    group_key: null,
    field_key: null,
    ...overrides,
  };
}

describe("SwotGrid", () => {
  it("renders all 4 quadrants, grouping claims by bucket", () => {
    const claims = [
      claim({ claim_id: "1", text: "DISCOM track record", field_key: "strength" }),
      claim({ claim_id: "2", text: "Dated visual identity", field_key: "weakness" }),
    ];
    render(<SwotGrid claims={claims} />);

    expect(screen.getByText("Strengths")).toBeInTheDocument();
    expect(screen.getByText("Weaknesses")).toBeInTheDocument();
    expect(screen.getByText("Opportunities")).toBeInTheDocument();
    expect(screen.getByText("Threats")).toBeInTheDocument();
    expect(screen.getByText("DISCOM track record")).toBeInTheDocument();
  });

  it("shows an honest empty message for a bucket with no verified claims", () => {
    render(<SwotGrid claims={[]} />);
    expect(screen.getAllByText("No verified findings yet.")).toHaveLength(4);
  });
});
