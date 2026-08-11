import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ClaimCard } from "./ClaimCard";
import type { VerifiedClaim } from "@/lib/types";

const verified: VerifiedClaim = {
  claim_id: "claim-1",
  section: "brand_overview",
  text: "Acme Roasters sells specialty coffee.",
  chunk_id: "abc123",
  source_claim_ids: [],
  block_span: [0, 0],
  verified: true,
  rejection_reason: null,
};

describe("ClaimCard", () => {
  it("shows a verified claim as verified with its chunk_id", () => {
    render(<ClaimCard claim={verified} />);
    expect(screen.getByText(verified.text)).toBeInTheDocument();
    expect(screen.getByText("verified")).toBeInTheDocument();
    expect(screen.getByText("abc123")).toBeInTheDocument();
  });

  it("shows a rejected claim with its rejection reason, not as verified", () => {
    const rejected: VerifiedClaim = { ...verified, verified: false, rejection_reason: "missing_chunk" };
    render(<ClaimCard claim={rejected} />);
    expect(screen.queryByText("verified")).not.toBeInTheDocument();
    expect(screen.getByText(/does not resolve/)).toBeInTheDocument();
  });

  it("shows a derived claim's upstream citation count, not 'no chunk_id'", () => {
    const derived: VerifiedClaim = {
      ...verified,
      chunk_id: "",
      source_claim_ids: ["claim-1", "claim-2"],
    };
    render(<ClaimCard claim={derived} />);
    expect(screen.getByText("derived from 2 upstream claims")).toBeInTheDocument();
  });

  it("shows 'no citation' for a claim with neither a chunk_id nor source_claim_ids", () => {
    const uncited: VerifiedClaim = {
      ...verified,
      chunk_id: "",
      source_claim_ids: [],
      verified: false,
      rejection_reason: "no_citation",
    };
    render(<ClaimCard claim={uncited} />);
    expect(screen.getByText("no citation")).toBeInTheDocument();
  });
});
