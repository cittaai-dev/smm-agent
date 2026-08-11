import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { QualityCheckpointPanel } from "./QualityCheckpointPanel";
import type { QualityCheckpoint } from "@/lib/types";

const passing: QualityCheckpoint = {
  all_sections_filled: true,
  competitor_count_ok: true,
  personas_grounded: true,
  findings_lead_to_recommendations: true,
};

describe("QualityCheckpointPanel", () => {
  it("shows every row as passing when the checkpoint passed, with no warning", () => {
    render(<QualityCheckpointPanel checkpoint={passing} />);
    expect(screen.getByText("All sections filled")).toBeInTheDocument();
    expect(screen.getAllByText("✓")).toHaveLength(4);
    expect(screen.queryByText(/must pass before/)).not.toBeInTheDocument();
  });

  it("shows a failing row as unmet and warns approval is blocked", () => {
    render(<QualityCheckpointPanel checkpoint={{ ...passing, personas_grounded: false }} />);
    expect(screen.getAllByText("✓")).toHaveLength(3);
    expect(screen.getAllByText("—")).toHaveLength(1);
    expect(screen.getByText(/must pass before/)).toBeInTheDocument();
  });
});
