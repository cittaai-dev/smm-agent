import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { PlatformTable } from "./PlatformTable";
import type { VerifiedClaim } from "@/lib/types";

function claim(overrides: Partial<VerifiedClaim>): VerifiedClaim {
  return {
    claim_id: "c1",
    section: "platform_analysis",
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

describe("PlatformTable", () => {
  it("renders all 7 fixed platforms even with no claims yet", () => {
    render(<PlatformTable claims={[]} />);
    for (const platform of ["Instagram", "Facebook", "LinkedIn", "YouTube", "X (Twitter)", "Threads", "Pinterest"]) {
      expect(screen.getByText(platform)).toBeInTheDocument();
    }
  });

  it("fills in cells for platforms that do have tagged claims", () => {
    const claims = [
      claim({ claim_id: "1", text: "High priority", group_key: "Instagram", field_key: "priority" }),
    ];
    render(<PlatformTable claims={claims} />);
    expect(screen.getByText("High priority")).toBeInTheDocument();
  });
});
