import type { SectionStatus } from "@/lib/types";

const STYLES: Record<SectionStatus, string> = {
  verified: "bg-success-soft text-success",
  insufficient_evidence: "bg-run-soft text-run",
  team_provided: "bg-accent-soft text-accent-text",
};

export function SectionStatusBadge({
  status,
  claimsCount,
  note,
}: {
  status: SectionStatus;
  claimsCount: number;
  note?: string | null;
}) {
  const label =
    status === "verified"
      ? `${claimsCount} claim${claimsCount === 1 ? "" : "s"} verified`
      : status === "team_provided"
        ? "Provided by Team Lead"
        // The section's own note (e.g. "Awaiting Market Intel Core -- deferred
        // to Step 4") is honest about *why* -- a generic "empty" would hide
        // that this is an expected degrade (P5), not a failure.
        : (note ?? "Insufficient evidence");
  return (
    <span className={`rounded-full px-3 py-1 text-sm font-medium ${STYLES[status]}`}>{label}</span>
  );
}
