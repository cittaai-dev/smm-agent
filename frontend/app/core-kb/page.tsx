"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { ApiError, createPromotionRequest, decidePromotion, listCoreVersions } from "@/lib/api";
import { EvalGatePanel } from "@/components/EvalGatePanel";
import type { EvalGateFailedDetail, KBVersion } from "@/lib/types";

function isEvalGateFailedDetail(detail: unknown): detail is EvalGateFailedDetail {
  return (
    typeof detail === "object" && detail !== null && (detail as { reason?: unknown }).reason === "eval_gate_failed"
  );
}

function VersionRow({ version, apiKey }: { version: KBVersion; apiKey: string }) {
  const queryClient = useQueryClient();
  const [summary, setSummary] = useState("");

  const requestPromotion = useMutation({
    mutationFn: () => createPromotionRequest(apiKey, version.version, summary),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["core-versions"] }),
  });

  const decide = useMutation({
    mutationFn: (params: { requestId: string; decision: "approved" | "rejected" }) =>
      decidePromotion(apiKey, params.requestId, params.decision),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["core-versions"] }),
  });

  const gateError = requestPromotion.error instanceof ApiError ? requestPromotion.error : null;
  const gateFailure = gateError && isEvalGateFailedDetail(gateError.detail) ? gateError.detail : null;

  return (
    <div className="rounded-lg border border-slate-200 p-4" data-testid="kb-version-row">
      <div className="flex items-center justify-between">
        <div>
          <p className="font-medium text-slate-900">v{version.version}</p>
          <p className="text-xs text-slate-500">{version.kb_id}</p>
        </div>
        <span
          className={
            version.status === "promoted"
              ? "rounded bg-green-100 px-2 py-1 text-xs font-medium text-green-800"
              : version.status === "staging"
                ? "rounded bg-amber-100 px-2 py-1 text-xs font-medium text-amber-800"
                : "rounded bg-slate-100 px-2 py-1 text-xs font-medium text-slate-600"
          }
        >
          {version.status}
        </span>
      </div>

      {version.eval_gate_result && (
        <div className="mt-3">
          <EvalGatePanel result={version.eval_gate_result} />
        </div>
      )}
      {gateFailure && (
        <div className="mt-3">
          <EvalGatePanel result={gateFailure.result} />
        </div>
      )}

      {version.status === "staging" && (
        <div className="mt-3 flex flex-col gap-2">
          <input
            className="rounded border border-slate-300 px-2 py-1 text-sm"
            placeholder="Source summary (what's in this build)"
            value={summary}
            onChange={(e) => setSummary(e.target.value)}
          />
          <button
            className="self-start rounded bg-slate-900 px-3 py-1.5 text-sm text-white disabled:opacity-50"
            disabled={!summary.trim() || requestPromotion.isPending}
            onClick={() => requestPromotion.mutate()}
          >
            Request promotion
          </button>
        </div>
      )}

      {requestPromotion.data?.status === "pending" && (
        <div className="mt-3 flex gap-2">
          <button
            className="rounded bg-green-700 px-3 py-1.5 text-sm text-white"
            onClick={() => decide.mutate({ requestId: requestPromotion.data!.request_id, decision: "approved" })}
          >
            Approve
          </button>
          <button
            className="rounded bg-red-700 px-3 py-1.5 text-sm text-white"
            onClick={() => decide.mutate({ requestId: requestPromotion.data!.request_id, decision: "rejected" })}
          >
            Reject
          </button>
        </div>
      )}
    </div>
  );
}

export default function CoreKBPage() {
  // Placeholder auth: Step 4's api-key gate has no session/login UI yet
  // (server-enforced via api/deps.py, api-key header only) -- a real login
  // flow is Step 5 scope.
  const [apiKey, setApiKey] = useState("");

  const versionsQuery = useQuery({ queryKey: ["core-versions"], queryFn: listCoreVersions });

  return (
    <main className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Market Intel Core</h1>
        <input
          className="rounded border border-slate-300 px-2 py-1 text-sm"
          placeholder="api-key"
          value={apiKey}
          onChange={(e) => setApiKey(e.target.value)}
        />
      </div>

      {versionsQuery.isLoading && <p className="text-slate-500">Loading…</p>}
      {versionsQuery.isError && <p className="text-red-700">Could not load Core versions.</p>}

      <div className="flex flex-col gap-4">
        {versionsQuery.data?.map((v) => (
          <VersionRow key={v.kb_id} version={v} apiKey={apiKey} />
        ))}
        {versionsQuery.data?.length === 0 && (
          <p className="text-sm text-slate-500">No Core versions built yet.</p>
        )}
      </div>
    </main>
  );
}
