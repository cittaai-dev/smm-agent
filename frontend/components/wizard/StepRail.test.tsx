import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { StepRail } from "./StepRail";

const steps = [
  { title: "Onboard a Brand", desc: "Brand intake" },
  { title: "Document Understanding", desc: "Read & chunk" },
  { title: "Research Plan", desc: "Document outline" },
];

describe("StepRail", () => {
  it("marks steps before the current index as done and shows a checkmark", () => {
    render(
      <StepRail
        brandLabel="Brand Run"
        steps={steps}
        currentIndex={1}
        maxVisitedIndex={2}
        stepHref={(i) => `/step-${i}`}
        profileCard={<div>profile</div>}
      />,
    );
    expect(screen.getAllByText("✓")).toHaveLength(1);
    expect(screen.getByText("2")).toBeInTheDocument(); // current step's own number
  });

  it("only renders a link for steps within maxVisitedIndex, not the current or future ones", () => {
    render(
      <StepRail
        brandLabel="Brand Run"
        steps={steps}
        currentIndex={1}
        maxVisitedIndex={1}
        stepHref={(i) => `/step-${i}`}
        profileCard={<div>profile</div>}
      />,
    );
    expect(screen.getByRole("link", { name: /Onboard a Brand/ })).toHaveAttribute("href", "/step-0");
    expect(screen.queryByRole("link", { name: /Document Understanding/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /Research Plan/ })).not.toBeInTheDocument();
  });

  it("renders the profile card slot", () => {
    render(
      <StepRail
        brandLabel="Brand Run"
        steps={steps}
        currentIndex={0}
        maxVisitedIndex={0}
        stepHref={(i) => `/step-${i}`}
        profileCard={<div>WORKSPACE PROFILE</div>}
      />,
    );
    expect(screen.getByText("WORKSPACE PROFILE")).toBeInTheDocument();
  });
});
