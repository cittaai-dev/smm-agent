import { afterEach, describe, expect, it, vi } from "vitest";
import { approveDocument, uploadSource } from "./api";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("approveDocument", () => {
  it("POSTs the approver and decision to the document's approve endpoint", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ id: "doc-1", status: "approved" }),
    });
    vi.stubGlobal("fetch", fetchMock);

    await approveDocument("doc-1", "team_lead", "approved");

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/documents/doc-1/approve"),
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ approver_id: "team_lead", decision: "approved" }),
      }),
    );
  });
});

describe("uploadSource", () => {
  it("includes source_kind in the form body when provided", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ status: "queued" }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const file = new File(["content"], "insights.csv");
    await uploadSource("brand-x", file, "analytics");

    const [, init] = fetchMock.mock.calls[0];
    const form = init.body as FormData;
    expect(form.get("source_kind")).toBe("analytics");
    expect((form.get("file") as File).name).toBe("insights.csv");
  });

  it("omits source_kind when not provided, letting the backend infer it", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ status: "queued" }),
    });
    vi.stubGlobal("fetch", fetchMock);

    await uploadSource("brand-x", new File(["content"], "brand.pdf"));

    const [, init] = fetchMock.mock.calls[0];
    const form = init.body as FormData;
    expect(form.get("source_kind")).toBeNull();
  });
});
