import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ProseSection } from "./ProseSection";
import type { VerifiedClaim } from "@/lib/types";

function claim(overrides: Partial<VerifiedClaim>): VerifiedClaim {
  return {
    claim_id: "c1",
    section: "brand_overview",
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

describe("ProseSection", () => {
  it("renders each verified claim as its own paragraph, not a bordered card", () => {
    const claims = [
      claim({ claim_id: "1", text: "The brand sells outdoor gear." }),
      claim({ claim_id: "2", text: "It has served customers since 2015." }),
    ];
    render(<ProseSection claims={claims} />);

    const first = screen.getByText("The brand sells outdoor gear.");
    expect(first.tagName).toBe("P");
    expect(screen.getByText("It has served customers since 2015.")).toBeInTheDocument();
    expect(screen.queryByTestId("claim-card")).not.toBeInTheDocument();
  });

  it("excludes rejected claims from the prose flow", () => {
    const claims = [
      claim({ claim_id: "1", text: "Verified finding", verified: true }),
      claim({ claim_id: "2", text: "Rejected finding", verified: false, rejection_reason: "no_citation" }),
    ];
    render(<ProseSection claims={claims} />);
    expect(screen.getByText("Verified finding")).toBeInTheDocument();
    expect(screen.queryByText("Rejected finding")).not.toBeInTheDocument();
  });

  it("shows an honest empty message when there are no verified claims", () => {
    render(<ProseSection claims={[]} />);
    expect(screen.getByText("No verified findings yet.")).toBeInTheDocument();
  });
});
