import type { SectionStatus } from "@/lib/types";

const STYLES: Record<SectionStatus, string> = {
  verified: "bg-green-100 text-green-800",
  insufficient_evidence: "bg-amber-100 text-amber-800",
  team_provided: "bg-blue-100 text-blue-800",
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
