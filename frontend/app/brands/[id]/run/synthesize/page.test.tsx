import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { getDocument } from "@/lib/api";
import type { MarketResearchDocument } from "@/lib/types";

vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams("documentId=doc-1"),
}));

vi.mock("@/lib/api", () => ({
  getDocument: vi.fn(),
}));

import SynthesizePage from "./page";

function renderWithClient() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <SynthesizePage />
    </QueryClientProvider>,
  );
}

const doc: MarketResearchDocument = {
  id: "doc-1",
  brand_id: "acme-1",
  status: "pending_approval",
  cost_usd: 0,
  call_site_trace: {},
  sections: {
    brand_overview: {
      section: "brand_overview",
      status: "verified",
      note: null,
      cost_usd: 0,
      call_site_trace: {},
      claims: [
        {
          claim_id: "c1",
          section: "brand_overview",
          text: "Acme sells specialty coffee.",
          chunk_id: "abc123",
          source_claim_ids: [],
          block_span: [0, 0],
          confidence: 1,
          verified: true,
          rejection_reason: null,
        },
      ],
      personas: [],
    },
  },
} as unknown as MarketResearchDocument;

afterEach(() => {
  vi.resetAllMocks();
});

describe("SynthesizePage", () => {
  it("fetches and renders the completed run's claims once documentId is present", async () => {
    vi.mocked(getDocument).mockResolvedValue(doc);
    renderWithClient();
    await waitFor(() => expect(getDocument).toHaveBeenCalledWith("doc-1"));
    expect(await screen.findByText("Acme sells specialty coffee.")).toBeInTheDocument();
  });
});
