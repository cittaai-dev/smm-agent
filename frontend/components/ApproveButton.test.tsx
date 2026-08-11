import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ApproveButton } from "./ApproveButton";
import type { Deliverable } from "@/lib/types";

const base: Deliverable = {
  id: "del-1",
  brand_id: "acme",
  status: "pending_approval",
  claims: [],
  call_site_trace: {},
};

describe("ApproveButton", () => {
  it("is enabled when the deliverable is pending approval", () => {
    render(<ApproveButton deliverable={base} onApprove={vi.fn()} />);
    expect(screen.getByRole("button", { name: "Approve" })).toBeEnabled();
  });

  it("is disabled once the deliverable is already approved — server is the real gate, this is UX only", () => {
    render(<ApproveButton deliverable={{ ...base, status: "approved" }} onApprove={vi.fn()} />);
    expect(screen.getByRole("button")).toBeDisabled();
  });
});
