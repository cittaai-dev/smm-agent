import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { BridgePairCard } from "./BridgePairCard";
import type { BridgePair, VerifiedClaim } from "@/lib/types";

const pair: BridgePair = {
  run_chunk: { chunk_id: "run-1", kb_id: "run:brand-x", text: "Our Instagram engagement was 2.3k this month" },
  core_chunk: {
    chunk_id: "core-1",
    kb_id: "core:market-intel@v1",
    text: "Fitness category Instagram engagement benchmark is 2.8k",
  },
};

describe("BridgePairCard", () => {
  it("shows both the observed and benchmark evidence", () => {
    render(<BridgePairCard pair={pair} />);
    expect(screen.getByText(pair.run_chunk.text)).toBeInTheDocument();
    expect(screen.getByText(pair.core_chunk.text)).toBeInTheDocument();
  });

  it("renders the synthesized claim when provided", () => {
    const claim: VerifiedClaim = {
      claim_id: "claim-1",
      section: "competitor_analysis",
      text: "Engagement trails category benchmark",
      chunk_id: "run-1",
      source_claim_ids: [],
      block_span: [0, 0],
      verified: true,
      rejection_reason: null,
    };
    render(<BridgePairCard pair={pair} claim={claim} />);
    expect(screen.getByText(claim.text)).toBeInTheDocument();
  });

  it("omits the claim section when no claim is provided", () => {
    render(<BridgePairCard pair={pair} />);
    expect(screen.queryByTestId("claim-card")).not.toBeInTheDocument();
  });
});
