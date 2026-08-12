import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { PersonaCard } from "./PersonaCard";
import type { VerifiedAudiencePersona } from "@/lib/types";

const verified: VerifiedAudiencePersona = {
  persona_id: "persona-1",
  section: "target_audience",
  name: "Budget-conscious commuter",
  pain_points: ["Long commute times", "Rising fuel costs"],
  interests: ["Public transit", "Podcasts"],
  chunk_ids: ["chunk-1"],
  age_range: "",
  location: "",
  occupation_income: "",
  preferred_platforms: [],
  confidence: 1,
  verified: true,
  rejection_reason: null,
};

describe("PersonaCard", () => {
  it("shows a verified persona's name, pain points, interests, and citation", () => {
    render(<PersonaCard persona={verified} />);
    expect(screen.getByText(verified.name)).toBeInTheDocument();
    expect(screen.getByText("Long commute times")).toBeInTheDocument();
    expect(screen.getByText("Public transit")).toBeInTheDocument();
    expect(screen.getByText("chunk-1")).toBeInTheDocument();
    expect(screen.getByText("verified")).toBeInTheDocument();
  });

  it("shows a rejected persona with its rejection reason, not as verified", () => {
    const rejected: VerifiedAudiencePersona = {
      ...verified,
      verified: false,
      rejection_reason: "incomplete_persona",
    };
    render(<PersonaCard persona={rejected} />);
    expect(screen.queryByText("verified")).not.toBeInTheDocument();
    expect(screen.getByText(/not grounded enough to act on/)).toBeInTheDocument();
  });

  it("shows 'no citation' for a persona with no chunk_ids", () => {
    const uncited: VerifiedAudiencePersona = {
      ...verified,
      chunk_ids: [],
      verified: false,
      rejection_reason: "no_citation",
    };
    render(<PersonaCard persona={uncited} />);
    expect(screen.getByText("no citation")).toBeInTheDocument();
  });
});
