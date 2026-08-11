import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { PersonaList } from "./PersonaList";
import type { VerifiedAudiencePersona } from "@/lib/types";

const persona: VerifiedAudiencePersona = {
  persona_id: "persona-1",
  section: "target_audience",
  name: "Budget-conscious commuter",
  pain_points: ["Long commute times"],
  interests: ["Public transit"],
  chunk_ids: ["chunk-1"],
  verified: true,
  rejection_reason: null,
};

describe("PersonaList", () => {
  it("renders nothing for an empty persona list -- no empty-state noise on non-persona sections", () => {
    const { container } = render(<PersonaList personas={[]} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("renders one PersonaCard per persona", () => {
    render(<PersonaList personas={[persona, { ...persona, persona_id: "persona-2", name: "Second" }]} />);
    expect(screen.getByText("Budget-conscious commuter")).toBeInTheDocument();
    expect(screen.getByText("Second")).toBeInTheDocument();
  });
});
