"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { use } from "react";
import {
  approveDocument,
  ApiError,
  getApprovalHistory,
  getCheckpoint,
  getDocument,
  rerunDocument,
  resubmitDocument,
} from "@/lib/api";
import { ApproveButton } from "@/components/ApproveButton";
import { ClaimList } from "@/components/ClaimList";
import { DecisionHistoryStrip } from "@/components/DecisionHistoryStrip";
import { DistributionPanel } from "@/components/DistributionPanel";
import { PersonaList } from "@/components/PersonaList";
import { QualityCheckpointPanel } from "@/components/QualityCheckpointPanel";
import { RejectedStateActions } from "@/components/RejectedStateActions";
import { RunCostBadge } from "@/components/RunCostBadge";
import { SectionOutline } from "@/components/SectionOutline";
import { StatusBadge } from "@/components/StatusBadge";
import { StrategicNotesPanel } from "@/components/StrategicNotesPanel";
import { SECTION_LABELS, SECTION_ORDER } from "@/lib/sections";
import type { CheckpointFailedDetail } from "@/lib/types";

// Mirrors backend/app/infra/settings.py's CostBudgetSettings.max_usd_per_run
// default (SMM_COST_MAX_USD_PER_RUN) -- there's no config-exposing endpoint
// yet, so this is a display-only approximation of the real server-enforced
// ceiling, not a second source of truth the backend reads from.
const RUN_COST_BUDGET_USD = 2.0;

function isCheckpointFailedDetail(detail: unknown): detail is CheckpointFailedDetail {
  return (
    typeof detail === "object" &&
    detail !== null &&
    (detail as { reason?: unknown }).reason === "quality_checkpoint_failed"
  );
}

export default function DocumentPage({ params }: { params: Promise<{ id: string }> }) {
  const { id: documentId } = use(params);
  const queryClient = useQueryClient();
  const queryKey = ["document", documentId];
  const checkpointKey = ["checkpoint", documentId];

  const documentQuery = useQuery({
    queryKey,
    queryFn: () => getDocument(documentId),
  });

  // Live preview of the same gate /approve enforces -- lets a Team Lead see
  // why approval is blocked before they click, not just after a 422.
  const checkpointQuery = useQuery({
    queryKey: checkpointKey,
    queryFn: () => getCheckpoint(documentId),
  });

  const historyKey = ["approval-history", documentId];
  const historyQuery = useQuery({
    queryKey: historyKey,
    queryFn: () => getApprovalHistory(documentId),
  });

  const approve = useMutation({
    mutationFn: () => approveDocument(documentId, "team_lead", "approved"),
    onSuccess: (updated) => {
      queryClient.setQueryData(queryKey, updated);
      queryClient.invalidateQueries({ queryKey: checkpointKey });
      queryClient.invalidateQueries({ queryKey: historyKey });
    },
  });

  const rerun = useMutation({
    mutationFn: () => rerunDocument(documentId),
    onSuccess: (updated) => {
      queryClient.setQueryData(queryKey, updated);
      queryClient.invalidateQueries({ queryKey: checkpointKey });
    },
  });

  const resubmit = useMutation({
    mutationFn: (note: string) => resubmitDocument(documentId, "team_lead", note),
    onSuccess: (updated) => {
      queryClient.setQueryData(queryKey, updated);
      queryClient.invalidateQueries({ queryKey: historyKey });
    },
  });

  if (documentQuery.isLoading) {
    return <p className="text-slate-500">Loading…</p>;
  }
  if (documentQuery.isError || !documentQuery.data) {
    return <p className="text-red-700">Could not load document {documentId}.</p>;
  }

  const document = documentQuery.data;
  const checkpoint = checkpointQuery.data;
  const approveError = approve.error instanceof ApiError ? approve.error : null;
  const checkpointFailure =
    approveError && isCheckpointFailedDetail(approveError.detail) ? approveError.detail : null;

  return (
    <main className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Market Research — {document.brand_id}</h1>
        <div className="flex items-center gap-3">
          <RunCostBadge usd={document.cost_usd} budget={RUN_COST_BUDGET_USD} />
          <StatusBadge status={document.status} />
        </div>
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
              <PersonaList personas={section.personas} />
            </div>
          );
        })}
      </div>

      {checkpoint && <QualityCheckpointPanel checkpoint={checkpoint} />}

      <div className="mt-2">
        <ApproveButton
          status={document.status}
          onApprove={() => approve.mutate()}
          pending={approve.isPending}
          checkpointPassed={checkpoint ? Object.values(checkpoint).every(Boolean) : true}
        />
      </div>

      {approve.isError && !checkpointFailure && (
        <p className="text-sm text-red-700">Approval failed: {(approve.error as Error).message}</p>
      )}
      {checkpointFailure && (
        <p className="text-sm text-red-700">
          Approval blocked — the quality checkpoint above must pass first.
        </p>
      )}

      <RejectedStateActions
        status={document.status}
        onRerun={() => rerun.mutate()}
        onResubmit={(note) => resubmit.mutate(note)}
        rerunPending={rerun.isPending}
        resubmitPending={resubmit.isPending}
      />

      {historyQuery.data && <DecisionHistoryStrip events={historyQuery.data} />}

      <StrategicNotesPanel documentId={documentId} />

      <DistributionPanel documentId={documentId} documentStatus={document.status} />
    </main>
  );
}
