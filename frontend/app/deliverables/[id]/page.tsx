"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { use } from "react";
import { approveDeliverable, getDeliverable } from "@/lib/api";
import { ApproveButton } from "@/components/ApproveButton";
import { ClaimList } from "@/components/ClaimList";
import { StatusBadge } from "@/components/StatusBadge";

export default function DeliverablePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const queryClient = useQueryClient();

  const deliverableQuery = useQuery({
    queryKey: ["deliverable", id],
    queryFn: () => getDeliverable(id),
  });

  const approve = useMutation({
    mutationFn: () => approveDeliverable(id, "team_lead", "approved"),
    onSuccess: (updated) => {
      queryClient.setQueryData(["deliverable", id], updated);
    },
  });

  if (deliverableQuery.isLoading) {
    return <p className="text-slate-500">Loading…</p>;
  }
  if (deliverableQuery.isError || !deliverableQuery.data) {
    return <p className="text-red-700">Could not load deliverable {id}.</p>;
  }

  const deliverable = deliverableQuery.data;

  return (
    <main className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Brand overview — {deliverable.brand_id}</h1>
        <StatusBadge status={deliverable.status} />
      </div>

      <ClaimList claims={deliverable.claims} />

      <div className="mt-2">
        <ApproveButton deliverable={deliverable} onApprove={() => approve.mutate()} pending={approve.isPending} />
      </div>

      {approve.isError && (
        <p className="text-sm text-red-700">Approval failed: {(approve.error as Error).message}</p>
      )}
    </main>
  );
}
