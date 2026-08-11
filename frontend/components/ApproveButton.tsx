import type { DocumentStatus } from "@/lib/types";

export function ApproveButton({
  status,
  onApprove,
  pending,
  checkpointPassed = true,
}: {
  status: DocumentStatus;
  onApprove: () => void;
  pending?: boolean;
  // Defaults to true so existing callers (and this component's own tests)
  // that don't yet fetch a QualityCheckpoint keep working -- the server
  // still enforces the real gate on /approve regardless of this prop; this
  // is UX-only, matching every other approve gate in this codebase.
  checkpointPassed?: boolean;
}) {
  const enabled = status === "pending_approval" && checkpointPassed && !pending;
  return (
    <button
      type="button"
      className="rounded-md bg-green-600 px-4 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-40"
      disabled={!enabled}
      onClick={onApprove}
    >
      {pending ? "Approving…" : "Approve"}
    </button>
  );
}
