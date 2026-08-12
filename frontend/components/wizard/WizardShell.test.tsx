import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { WizardShell } from "./WizardShell";

const steps = [
  { title: "Onboard a Brand", desc: "Brand intake" },
  { title: "Document Understanding", desc: "Read & chunk" },
];

describe("WizardShell", () => {
  it("renders the pipeline badge, scope label, and step counter", () => {
    render(
      <WizardShell
        brandLabel="Brand Run"
        pipelineBadge="BRAND WORKSPACE"
        scopeLabel="brand:acme-1"
        steps={steps}
        currentIndex={0}
        maxVisitedIndex={0}
        stepHref={(i) => `/step-${i}`}
        profileCard={<div />}
        backHref={null}
        nextHref="/step-1"
      >
        <p>content</p>
      </WizardShell>,
    );
    expect(screen.getByText("BRAND WORKSPACE")).toBeInTheDocument();
    expect(screen.getByText("brand:acme-1")).toBeInTheDocument();
    expect(screen.getByText("STEP 1 / 2")).toBeInTheDocument();
    expect(screen.getByText("content")).toBeInTheDocument();
  });

  it("hides the Back link on the first step and renders a real Next link when enabled", () => {
    render(
      <WizardShell
        brandLabel="Brand Run"
        pipelineBadge="BRAND WORKSPACE"
        scopeLabel="brand:acme-1"
        steps={steps}
        currentIndex={0}
        maxVisitedIndex={0}
        stepHref={(i) => `/step-${i}`}
        profileCard={<div />}
        backHref={null}
        nextHref="/step-1"
      >
        <p>content</p>
      </WizardShell>,
    );
    expect(screen.queryByRole("link", { name: "← Back" })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Next →" })).toHaveAttribute("href", "/step-1");
  });

  it("disables Next and shows the hint when nextDisabled is set, instead of a dead link", () => {
    render(
      <WizardShell
        brandLabel="Brand Run"
        pipelineBadge="BRAND WORKSPACE"
        scopeLabel="brand:acme-1"
        steps={steps}
        currentIndex={0}
        maxVisitedIndex={0}
        stepHref={(i) => `/step-${i}`}
        profileCard={<div />}
        backHref={null}
        nextHref={null}
        nextDisabled
        nextHint="Run research (Step 2) to continue"
      >
        <p>content</p>
      </WizardShell>,
    );
    expect(screen.queryByRole("link", { name: "Next →" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Next →" })).toBeDisabled();
    expect(screen.getByText("Run research (Step 2) to continue")).toBeInTheDocument();
  });
});
