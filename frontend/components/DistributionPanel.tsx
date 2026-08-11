"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { distributeDocument, getDistribution } from "@/lib/api";
import type { DocumentStatus } from "@/lib/types";

// SOP-1 step 13: distribute, the final state after approve. Gated on
// document.status === "approved" -- same "server is the real gate, this is
// UX only" discipline as ApproveButton: /distribute itself 422s otherwise.
export function DistributionPanel({
  documentId,
  documentStatus,
}: {
  documentId: string;
  documentStatus: DocumentStatus;
}) {
  const queryClient = useQueryClient();
  const queryKey = ["distribution", documentId];

  const distribution = useQuery({
    queryKey,
    queryFn: () => getDistribution(documentId),
  });

  const [internal, setInternal] = useState(true);
  const [client, setClient] = useState(false);

  const submit = useMutation({
    mutationFn: () => distributeDocument(documentId, internal, client),
    onSuccess: (record) => {
      queryClient.setQueryData(queryKey, record);
    },
  });

  const enabled = documentStatus === "approved" && !submit.isPending;
  const record = submit.data ?? distribution.data;

  return (
    <div className="flex flex-col gap-3 rounded-lg border border-slate-200 p-4">
      <p className="text-sm font-medium text-slate-900">Distribute</p>
      {documentStatus !== "approved" && (
        <p className="text-xs text-slate-500">Available once this document is approved.</p>
      )}

      <div className="flex gap-4 text-sm">
        <label className="flex items-center gap-1.5">
          <input
            type="checkbox"
            checked={internal}
            disabled={!enabled}
            onChange={(e) => setInternal(e.target.checked)}
          />
          Internal (agency)
        </label>
        <label className="flex items-center gap-1.5">
          <input
            type="checkbox"
            checked={client}
            disabled={!enabled}
            onChange={(e) => setClient(e.target.checked)}
          />
          Client
        </label>
      </div>

      <button
        type="button"
        className="w-fit rounded-md bg-slate-900 px-3 py-1.5 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-40"
        disabled={!enabled || (!internal && !client)}
        onClick={() => submit.mutate()}
      >
        {submit.isPending ? "Distributing…" : "Distribute"}
      </button>

      {submit.isError && <p className="text-sm text-red-700">{(submit.error as Error).message}</p>}

      {record && (
        <p className="text-xs text-slate-500">
          Last distributed {new Date(record.distributed_at).toLocaleString()} —{" "}
          {[record.internal && "internal", record.client && "client"].filter(Boolean).join(", ")}
        </p>
      )}
    </div>
  );
}
