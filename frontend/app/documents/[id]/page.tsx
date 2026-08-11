"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { use } from "react";
import { approveDocument, getDocument } from "@/lib/api";
import { ApproveButton } from "@/components/ApproveButton";
import { ClaimList } from "@/components/ClaimList";
import { SectionOutline } from "@/components/SectionOutline";
import { StatusBadge } from "@/components/StatusBadge";
import { SECTION_LABELS, SECTION_ORDER } from "@/lib/sections";

export default function DocumentPage({ params }: { params: Promise<{ id: string }> }) {
  const { id: documentId } = use(params);
  const queryClient = useQueryClient();
  const queryKey = ["document", documentId];

  const documentQuery = useQuery({
    queryKey,
    queryFn: () => getDocument(documentId),
  });

  const approve = useMutation({
    mutationFn: () => approveDocument(documentId, "team_lead", "approved"),
    onSuccess: (updated) => {
      queryClient.setQueryData(queryKey, updated);
    },
  });

  if (documentQuery.isLoading) {
    return <p className="text-slate-500">Loading…</p>;
  }
  if (documentQuery.isError || !documentQuery.data) {
    return <p className="text-red-700">Could not load document {documentId}.</p>;
  }

  const document = documentQuery.data;

  return (
    <main className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Market Research — {document.brand_id}</h1>
        <StatusBadge status={document.status} />
      </div>

      <SectionOutline document={document} />

      <div className="flex flex-col gap-6">
        {SECTION_ORDER.map((id) => {
          const section = document.sections[id];
          if (!section || section.claims.length === 0) return null;
          return (
            <div key={id} className="flex flex-col gap-2">
              <h2 className="text-lg font-medium">{SECTION_LABELS[id]}</h2>
              <ClaimList claims={section.claims} />
            </div>
          );
        })}
      </div>

      <div className="mt-2">
        <ApproveButton status={document.status} onApprove={() => approve.mutate()} pending={approve.isPending} />
      </div>

      {approve.isError && (
        <p className="text-sm text-red-700">Approval failed: {(approve.error as Error).message}</p>
      )}
    </main>
  );
}
