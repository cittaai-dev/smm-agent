"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import {
  createDistributionLink,
  distributeDocument,
  getDistribution,
  listDistributionLinks,
  revokeDistributionLink,
} from "@/lib/api";
import type { DocumentStatus } from "@/lib/types";

// SOP-1 step 13: distribute, the final state after approve. Gated on
// document.status === "approved" -- same "server is the real gate, this is
// UX only" discipline as ApproveButton: /distribute and /distribution-links
// both 422 otherwise.
//
// Two distinct capabilities, not one button (step5_trust_boundary.md's gap
// analysis finding): the internal/client toggle below only ever wrote two
// booleans to a table -- no email, no portal, no webhook -- so it's labeled
// "Mark as shared", not "Distribute", to never claim automated delivery it
// doesn't perform. "Create client link" is the real capability added in Step
// 5: a scoped, revocable, token-based read-only view (DistributionLink).
export function DistributionPanel({
  documentId,
  documentStatus,
}: {
  documentId: string;
  documentStatus: DocumentStatus;
}) {
  const queryClient = useQueryClient();
  const queryKey = ["distribution", documentId];
  const linksKey = ["distribution-links", documentId];

  const distribution = useQuery({
    queryKey,
    queryFn: () => getDistribution(documentId),
  });

  const links = useQuery({
    queryKey: linksKey,
    queryFn: () => listDistributionLinks(documentId),
  });

  const [internal, setInternal] = useState(true);
  const [client, setClient] = useState(false);
  const [createdBy, setCreatedBy] = useState("");

  const submit = useMutation({
    mutationFn: () => distributeDocument(documentId, internal, client),
    onSuccess: (record) => {
      queryClient.setQueryData(queryKey, record);
    },
  });

  const createLink = useMutation({
    mutationFn: () => createDistributionLink(documentId, createdBy),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: linksKey }),
  });

  const revoke = useMutation({
    mutationFn: (linkId: string) => revokeDistributionLink(linkId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: linksKey }),
  });

  const enabled = documentStatus === "approved" && !submit.isPending;
  const record = submit.data ?? distribution.data;

  return (
    <div className="flex flex-col gap-3 rounded-lg border border-slate-200 p-4">
      <div>
        <p className="text-sm font-medium text-slate-900">Mark as shared</p>
        <p className="text-xs text-slate-400">
          Records that this was shared — email/portal delivery isn&apos;t automated yet.
        </p>
      </div>
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
        {submit.isPending ? "Marking…" : "Mark as shared"}
      </button>

      {submit.isError && <p className="text-sm text-red-700">{(submit.error as Error).message}</p>}

      {record && (
        <p className="text-xs text-slate-500">
          Last shared {new Date(record.distributed_at).toLocaleString()} —{" "}
          {[record.internal && "internal", record.client && "client"].filter(Boolean).join(", ")}
        </p>
      )}

      <div className="mt-2 flex flex-col gap-2 border-t border-slate-100 pt-3">
        <p className="text-sm font-medium text-slate-900">Create client link</p>
        <p className="text-xs text-slate-400">
          A scoped, revocable read-only view — no operator credential, no other brand&apos;s data.
        </p>
        <div className="flex items-center gap-2">
          <input
            className="min-w-40 rounded border border-slate-300 px-2 py-1 text-sm"
            placeholder="Your name"
            value={createdBy}
            disabled={!enabled}
            onChange={(e) => setCreatedBy(e.target.value)}
          />
          <button
            type="button"
            className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium disabled:cursor-not-allowed disabled:opacity-40"
            disabled={!enabled || !createdBy.trim() || createLink.isPending}
            onClick={() => createLink.mutate()}
          >
            {createLink.isPending ? "Creating…" : "Create client link"}
          </button>
        </div>

        {createLink.data && (
          <p className="text-xs text-slate-500">
            Link created, expires {new Date(createLink.data.expires_at).toLocaleDateString()} —{" "}
            <code className="rounded bg-slate-100 px-1">/view/{createLink.data.token}</code>
          </p>
        )}

        {links.data && links.data.length > 0 && (
          <ul className="flex flex-col gap-1">
            {links.data.map((link) => (
              <li key={link.id} className="flex items-center justify-between text-xs text-slate-500">
                <span>
                  {link.id} — {link.revoked ? "revoked" : `expires ${new Date(link.expires_at).toLocaleDateString()}`}
                </span>
                {!link.revoked && (
                  <button
                    type="button"
                    className="text-red-700 underline disabled:opacity-40"
                    disabled={revoke.isPending}
                    onClick={() => revoke.mutate(link.id)}
                  >
                    Revoke
                  </button>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
