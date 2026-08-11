import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { RejectedStateActions } from "./RejectedStateActions";

describe("RejectedStateActions", () => {
  it("renders nothing unless the document is rejected", () => {
    render(
      <RejectedStateActions status="pending_approval" onRerun={vi.fn()} onResubmit={vi.fn()} />,
    );
    expect(screen.queryByText(/what changed/)).not.toBeInTheDocument();
  });

  it("calls onRerun when re-run is clicked", () => {
    const onRerun = vi.fn();
    render(<RejectedStateActions status="rejected" onRerun={onRerun} onResubmit={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: /Re-run agent/ }));
    expect(onRerun).toHaveBeenCalled();
  });

  it("disables resubmit until a note is entered, then calls onResubmit with it", () => {
    const onResubmit = vi.fn();
    render(<RejectedStateActions status="rejected" onRerun={vi.fn()} onResubmit={onResubmit} />);

    const resubmitButton = screen.getByRole("button", { name: /Resubmit for review/ });
    expect(resubmitButton).toBeDisabled();

    fireEvent.change(screen.getByPlaceholderText(/How was this addressed/), {
      target: { value: "fixed via notes" },
    });
    expect(resubmitButton).toBeEnabled();
    fireEvent.click(resubmitButton);
    expect(onResubmit).toHaveBeenCalledWith("fixed via notes");
  });
});
