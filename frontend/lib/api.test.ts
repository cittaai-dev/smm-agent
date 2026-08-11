import { afterEach, describe, expect, it, vi } from "vitest";
import { approveDeliverable } from "./api";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("approveDeliverable", () => {
  it("POSTs the approver and decision to the deliverable's approve endpoint", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ id: "del-1", status: "approved" }),
    });
    vi.stubGlobal("fetch", fetchMock);

    await approveDeliverable("del-1", "team_lead", "approved");

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/deliverables/del-1/approve"),
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ approver_id: "team_lead", decision: "approved" }),
      }),
    );
  });
});
