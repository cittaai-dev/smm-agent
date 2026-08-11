import type { Deliverable } from "@/lib/types";

export function ApproveButton({
  deliverable,
  onApprove,
  pending,
}: {
  deliverable: Deliverable;
  onApprove: () => void;
  pending?: boolean;
}) {
  const enabled = deliverable.status === "pending_approval" && !pending;
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
