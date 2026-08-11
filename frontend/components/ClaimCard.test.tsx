import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ClaimCard } from "./ClaimCard";
import type { VerifiedClaim } from "@/lib/types";

const verified: VerifiedClaim = {
  section: "brand_overview",
  text: "Acme Roasters sells specialty coffee.",
  chunk_id: "abc123",
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
});
