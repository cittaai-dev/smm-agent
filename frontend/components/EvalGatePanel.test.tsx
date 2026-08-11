import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { EvalGatePanel } from "./EvalGatePanel";
import type { EvalGateResult } from "@/lib/types";

const passing: EvalGateResult = {
  citation_rejection_rate: 0.02,
  degraded_ratio: 0.01,
  l0_ratio: 0.05,
  coverage_ok: true,
  passed: true,
  thresholds: {
    max_citation_rejection_rate: 0.08,
    max_degraded_ratio: 0.05,
    max_l0_ratio: 0.15,
  },
};

describe("EvalGatePanel", () => {
  it("shows a passing gate as eligible for promotion", () => {
    render(<EvalGatePanel result={passing} />);
    expect(screen.getByText("Eligible for promotion")).toBeInTheDocument();
    expect(screen.getByText("✓ adequate")).toBeInTheDocument();
  });

  it("shows a failing gate as blocked, with the failing metric highlighted", () => {
    const failing: EvalGateResult = { ...passing, citation_rejection_rate: 0.2, passed: false };
    render(<EvalGatePanel result={failing} />);
    expect(screen.getByText(/Blocked/)).toBeInTheDocument();
  });

  it("shows insufficient coverage distinctly from a metric threshold miss", () => {
    const noCoverage: EvalGateResult = { ...passing, coverage_ok: false, passed: false };
    render(<EvalGatePanel result={noCoverage} />);
    expect(screen.getByText("✗ insufficient")).toBeInTheDocument();
  });
});
