"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import {
  ApiError,
  createPromotionRequest,
  decidePromotion,
  listCoreVersions,
  triggerStagingBuild,
} from "@/lib/api";
import { EvalGatePanel } from "@/components/EvalGatePanel";
import type { EvalGateFailedDetail, KBVersion } from "@/lib/types";

function isEvalGateFailedDetail(detail: unknown): detail is EvalGateFailedDetail {
  return (
    typeof detail === "object" && detail !== null && (detail as { reason?: unknown }).reason === "eval_gate_failed"
  );
}

function VersionRow({ version }: { version: KBVersion }) {
  const queryClient = useQueryClient();
  const [summary, setSummary] = useState("");

  const requestPromotion = useMutation({
    mutationFn: () => createPromotionRequest("", version.version, summary),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["core-versions"] }),
  });

  const decide = useMutation({
    mutationFn: (params: { requestId: string; decision: "approved" | "rejected" }) =>
      decidePromotion("", params.requestId, params.decision),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["core-versions"] }),
  });

  const gateError = requestPromotion.error instanceof ApiError ? requestPromotion.error : null;
  const gateFailure = gateError && isEvalGateFailedDetail(gateError.detail) ? gateError.detail : null;

  return (
    <div className="rounded-lg border border-border p-4" data-testid="kb-version-row">
      <div className="flex items-center justify-between">
        <div>
          <p className="font-medium text-text">v{version.version}</p>
          <p className="font-mono text-xs text-text-dim">{version.kb_id}</p>
        </div>
        <span
          className={
            version.status === "promoted"
              ? "rounded bg-success-soft px-2 py-1 text-xs font-medium text-success"
              : version.status === "staging"
                ? "rounded bg-run-soft px-2 py-1 text-xs font-medium text-run"
                : "rounded bg-surface2 px-2 py-1 text-xs font-medium text-text-dim"
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
            className="rounded border border-border px-2 py-1 text-sm"
            placeholder="Source summary (what's in this build)"
            value={summary}
            onChange={(e) => setSummary(e.target.value)}
          />
          <button
            className="self-start rounded bg-accent px-3 py-1.5 text-sm text-white disabled:opacity-50"
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
            className="rounded bg-success px-3 py-1.5 text-sm text-white"
            onClick={() => decide.mutate({ requestId: requestPromotion.data!.request_id, decision: "approved" })}
          >
            Approve
          </button>
          <button
            className="rounded bg-danger px-3 py-1.5 text-sm text-white"
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
  // Local dev (SMM_AUTH_DEV_BYPASS) skips the platform api-key/brand-grant
  // check server-side, so there's no key input here anymore -- lib/api.ts's
  // withApiKey supplies a dev-only default. A real login flow is Step 5 scope.
  const queryClient = useQueryClient();

  const versionsQuery = useQuery({ queryKey: ["core-versions"], queryFn: listCoreVersions });

  const [sourcePaths, setSourcePaths] = useState("");
  const [targetVersion, setTargetVersion] = useState(1);

  const startBuild = useMutation({
    mutationFn: () =>
      triggerStagingBuild(
        "",
        sourcePaths.split(",").map((s) => s.trim()).filter(Boolean),
        targetVersion,
      ),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["core-versions"] }),
  });

  return (
    <main className="flex flex-col gap-6">
      <h1 className="text-2xl font-semibold">Market Intel Core</h1>

      <section className="flex flex-col gap-3 rounded-lg border border-border p-4">
        <h2 className="text-lg font-medium">Start a build</h2>
        <p className="text-xs text-text-faint">
          Queues a staging build from the given source paths -- Step 1 of the Core KB pipeline.
        </p>
        <div className="flex flex-wrap items-center gap-2">
          <input
            className="min-w-64 flex-1 rounded border border-border px-2 py-1 text-sm"
            placeholder="Source paths, comma-separated"
            value={sourcePaths}
            onChange={(e) => setSourcePaths(e.target.value)}
          />
          <input
            className="w-24 rounded border border-border px-2 py-1 text-sm"
            type="number"
            min={1}
            value={targetVersion}
            onChange={(e) => setTargetVersion(Number(e.target.value))}
          />
          <button
            type="button"
            className="rounded bg-accent px-3 py-1.5 text-sm text-white disabled:opacity-50"
            disabled={!sourcePaths.trim() || startBuild.isPending}
            onClick={() => startBuild.mutate()}
          >
            {startBuild.isPending ? "Starting…" : "Start build"}
          </button>
        </div>
        {startBuild.isSuccess && (
          <p className="text-sm text-success">
            Build queued for target version {startBuild.data.target_version}.
          </p>
        )}
        {startBuild.isError && (
          <p className="text-sm text-danger">Could not start build: {(startBuild.error as Error).message}</p>
        )}
      </section>

      {versionsQuery.isLoading && <p className="text-text-dim">Loading…</p>}
      {versionsQuery.isError && <p className="text-danger">Could not load Core versions.</p>}

      <div className="flex flex-col gap-4">
        {versionsQuery.data?.map((v) => (
          <VersionRow key={v.kb_id} version={v} />
        ))}
        {versionsQuery.data?.length === 0 && (
          <p className="text-sm text-text-dim">No Core versions built yet.</p>
        )}
      </div>
    </main>
  );
}
