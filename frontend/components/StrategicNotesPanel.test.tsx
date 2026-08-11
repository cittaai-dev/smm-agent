import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { StrategicNotesPanel } from "./StrategicNotesPanel";
import { addNote, listNotes } from "@/lib/api";
import type { StrategicNote } from "@/lib/types";

vi.mock("@/lib/api", () => ({
  listNotes: vi.fn(),
  addNote: vi.fn(),
}));

function renderWithClient(ui: React.ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

const existingNote: StrategicNote = {
  id: "note-1",
  document_id: "doc-1",
  section: "brand_overview",
  text: "Double-check founding year.",
  author: "jane@agency.com",
  created_at: "2026-08-11T12:00:00Z",
};

afterEach(() => {
  vi.resetAllMocks();
});

describe("StrategicNotesPanel", () => {
  it("lists existing notes with their section, author, and text", async () => {
    vi.mocked(listNotes).mockResolvedValue([existingNote]);
    renderWithClient(<StrategicNotesPanel documentId="doc-1" />);

    expect(await screen.findByText("Double-check founding year.")).toBeInTheDocument();
    expect(screen.getByText(/jane@agency.com/)).toBeInTheDocument();
  });

  it("submits a new note with the selected section, text, and author, and disables the button until both are filled", async () => {
    vi.mocked(listNotes).mockResolvedValue([]);
    vi.mocked(addNote).mockResolvedValue({ ...existingNote, id: "note-2" });
    renderWithClient(<StrategicNotesPanel documentId="doc-1" />);
    await waitFor(() => expect(listNotes).toHaveBeenCalled());

    const addButton = screen.getByRole("button", { name: "Add note" });
    expect(addButton).toBeDisabled();

    fireEvent.change(screen.getByLabelText("Your name"), { target: { value: "jane@agency.com" } });
    fireEvent.change(screen.getByLabelText("Note"), { target: { value: "Check the pricing page." } });
    expect(addButton).toBeEnabled();

    fireEvent.click(addButton);

    await waitFor(() =>
      expect(addNote).toHaveBeenCalledWith("doc-1", "brand_overview", "Check the pricing page.", "jane@agency.com"),
    );
  });
});
