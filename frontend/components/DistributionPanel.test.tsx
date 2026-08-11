import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { DistributionPanel } from "./DistributionPanel";
import { getDistribution, listDistributionLinks } from "@/lib/api";

vi.mock("@/lib/api", () => ({
  getDistribution: vi.fn(),
  distributeDocument: vi.fn(),
  listDistributionLinks: vi.fn(),
  createDistributionLink: vi.fn(),
  revokeDistributionLink: vi.fn(),
}));

function renderWithClient(ui: React.ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

afterEach(() => {
  vi.resetAllMocks();
});

describe("DistributionPanel", () => {
  it("disables Mark as shared before approval -- server is the real gate, this is UX only", async () => {
    vi.mocked(getDistribution).mockResolvedValue(null);
    vi.mocked(listDistributionLinks).mockResolvedValue([]);
    renderWithClient(<DistributionPanel documentId="doc-1" documentStatus="pending_approval" />);
    await waitFor(() => expect(getDistribution).toHaveBeenCalled());

    expect(screen.getByRole("button", { name: "Mark as shared" })).toBeDisabled();
    expect(screen.getByText(/Available once this document is approved/)).toBeInTheDocument();
  });

  it("enables Mark as shared once the document is approved", async () => {
    vi.mocked(getDistribution).mockResolvedValue(null);
    vi.mocked(listDistributionLinks).mockResolvedValue([]);
    renderWithClient(<DistributionPanel documentId="doc-1" documentStatus="approved" />);
    await waitFor(() => expect(getDistribution).toHaveBeenCalled());

    expect(screen.getByRole("button", { name: "Mark as shared" })).toBeEnabled();
  });

  it("never claims automated delivery it doesn't perform", async () => {
    vi.mocked(getDistribution).mockResolvedValue(null);
    vi.mocked(listDistributionLinks).mockResolvedValue([]);
    renderWithClient(<DistributionPanel documentId="doc-1" documentStatus="approved" />);
    await waitFor(() => expect(getDistribution).toHaveBeenCalled());

    expect(screen.queryByRole("button", { name: "Distribute" })).not.toBeInTheDocument();
    expect(screen.getByText(/delivery isn't automated yet/)).toBeInTheDocument();
  });
});
