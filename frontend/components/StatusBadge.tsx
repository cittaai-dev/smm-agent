import type { DocumentStatus } from "@/lib/types";

const STYLES: Record<DocumentStatus, string> = {
  draft: "bg-slate-100 text-slate-700",
  pending_approval: "bg-amber-100 text-amber-800",
  approved: "bg-green-100 text-green-800",
  rejected: "bg-red-100 text-red-800",
  insufficient_grounding: "bg-orange-100 text-orange-800",
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
