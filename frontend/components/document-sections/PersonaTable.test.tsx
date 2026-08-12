import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { PersonaTable } from "./PersonaTable";
import type { VerifiedAudiencePersona } from "@/lib/types";

function persona(overrides: Partial<VerifiedAudiencePersona>): VerifiedAudiencePersona {
  return {
    persona_id: "p1",
    section: "target_audience",
    name: "Weekend warrior",
    pain_points: ["Limited free time"],
    interests: ["Quality gear"],
    chunk_ids: ["c1"],
    age_range: "25-34",
    location: "Urban US",
    occupation_income: "Mid-career",
    preferred_platforms: ["Instagram"],
    confidence: 1,
    verified: true,
    rejection_reason: null,
    ...overrides,
  };
}

describe("PersonaTable", () => {
  it("transposes personas as columns and attributes as rows", () => {
    render(
      <PersonaTable
        personas={[persona({}), persona({ persona_id: "p2", name: "Busy parent", age_range: "35-44" })]}
      />,
    );

    expect(screen.getByText("Persona 1")).toBeInTheDocument();
    expect(screen.getByText("Persona 2")).toBeInTheDocument();
    expect(screen.getByText("Name / label")).toBeInTheDocument();
    expect(screen.getByText("Weekend warrior")).toBeInTheDocument();
    expect(screen.getByText("Busy parent")).toBeInTheDocument();
    expect(screen.getByText("25-34")).toBeInTheDocument();
    expect(screen.getByText("35-44")).toBeInTheDocument();
  });

  it("excludes rejected personas from the table", () => {
    render(<PersonaTable personas={[persona({ verified: false, rejection_reason: "incomplete_persona" })]} />);
    expect(screen.getByText("No verified personas yet.")).toBeInTheDocument();
  });
});
