import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { DecisionHistoryStrip } from "./DecisionHistoryStrip";
import type { ApprovalEvent } from "@/lib/types";

const events: ApprovalEvent[] = [
  {
    id: 1,
    document_id: "doc-1",
    decision: "rejected",
    approver_id: "u1",
    note: "missing evidence",
    checkpoint: null,
    decided_at: "2026-01-01T00:00:00Z",
  },
  {
    id: 2,
    document_id: "doc-1",
    decision: "resubmitted",
    approver_id: "u2",
    note: "brand uploaded updated deck",
    checkpoint: null,
    decided_at: "2026-01-02T00:00:00Z",
  },
  {
    id: 3,
    document_id: "doc-1",
    decision: "approved",
    approver_id: "u2",
    note: null,
    checkpoint: null,
    decided_at: "2026-01-03T00:00:00Z",
  },
];

describe("DecisionHistoryStrip", () => {
  it("shows every decision in the history, not just the latest", () => {
    render(<DecisionHistoryStrip events={events} />);
    expect(screen.getByText("rejected", { exact: false })).toBeInTheDocument();
    expect(screen.getByText("resubmitted", { exact: false })).toBeInTheDocument();
    expect(screen.getByText("approved", { exact: false })).toBeInTheDocument();
  });

  it("renders nothing for an empty history", () => {
    render(<DecisionHistoryStrip events={[]} />);
    expect(screen.queryByTestId("decision-history")).not.toBeInTheDocument();
  });
});
