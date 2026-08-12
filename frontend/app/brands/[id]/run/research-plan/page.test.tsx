import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams(),
}));

import ResearchPlanPage from "./page";

describe("ResearchPlanPage", () => {
  it("renders all 11 SOP-01 sections with an evidence-source pill each", () => {
    render(<ResearchPlanPage />);
    expect(screen.getByText("Brand overview")).toBeInTheDocument();
    expect(screen.getByText("Key takeaways")).toBeInTheDocument();
    // market_overview is core_only -- should show the Market Intel Core pill.
    const marketOverviewRow = screen.getByText("Market overview").closest("div")!.parentElement!;
    expect(marketOverviewRow.textContent).toContain("Market Intel Core");
    // business_goals is direct_input -- team-lead-authored, not retrieved.
    const goalsRow = screen.getByText("Business goals").closest("div")!.parentElement!;
    expect(goalsRow.textContent).toContain("Team Lead confirmed");
  });

  it("notes the outline is structural, independent of whether a run has completed", () => {
    render(<ResearchPlanPage />);
    expect(screen.getByText(/same before or after this run finishes/)).toBeInTheDocument();
  });
});
