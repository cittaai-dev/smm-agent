import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ApproveButton } from "./ApproveButton";

describe("ApproveButton", () => {
  it("is enabled when pending approval", () => {
    render(<ApproveButton status="pending_approval" onApprove={vi.fn()} />);
    expect(screen.getByRole("button", { name: "Approve" })).toBeEnabled();
  });

  it("is disabled once already approved — server is the real gate, this is UX only", () => {
    render(<ApproveButton status="approved" onApprove={vi.fn()} />);
    expect(screen.getByRole("button")).toBeDisabled();
  });

  it("is disabled while an approve request is pending", () => {
    render(<ApproveButton status="pending_approval" onApprove={vi.fn()} pending />);
    expect(screen.getByRole("button", { name: "Approving…" })).toBeDisabled();
  });
});
