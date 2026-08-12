import type { DocumentStatus } from "@/lib/types";

const STYLES: Record<DocumentStatus, string> = {
  draft: "bg-surface2 text-text-dim",
  pending_approval: "bg-run-soft text-run",
  approved: "bg-success-soft text-success",
  rejected: "bg-danger-soft text-danger",
  insufficient_grounding: "bg-run-soft text-run",
};

const LABELS: Record<DocumentStatus, string> = {
  draft: "Draft",
  pending_approval: "Pending approval",
  approved: "Approved",
  rejected: "Rejected",
  insufficient_grounding: "Insufficient grounding",
};

export function StatusBadge({ status }: { status: DocumentStatus }) {
  return (
    <span
      data-testid="status-badge"
      className={`rounded-full px-3 py-1 text-sm font-medium ${STYLES[status]}`}
    >
      {LABELS[status]}
    </span>
  );
}
