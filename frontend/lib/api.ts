import type {
  ApprovalChoice,
  ApprovalEvent,
  ApprovalGateRecord,
  ClientMarketResearchView,
  DataSourceCredentialSummary,
  DataSourceKind,
  DistributionLink,
  DistributionLinkCreated,
  DistributionRecord,
  EvalGateResult,
  KBVersion,
  MarketResearchDocument,
  MarketSegment,
  QualityCheckpoint,
  SourceFile,
  SourceKind,
  StrategicNote,
  TeamInput,
  UploadResult,
} from "./types";

export const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    // FastAPI's `detail` is a plain string for most errors but a structured
    // object for the checkpoint-failed 422 (CheckpointFailedDetail) -- kept
    // as unknown here (rather than that union) so this file doesn't need to
    // know every shape `detail` can take; callers that care narrow it.
    public detail?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, init);
  if (!res.ok) {
    const detail = await res
      .clone()
      .json()
      .then((body) => body?.detail ?? null)
      .catch(() => null);
    // FastAPI error responses are {"detail": "..."} for most endpoints, but
    // {"detail": {"reason": ..., "checkpoint": ...}} for the checkpoint gate
    // -- only a string detail makes a good headline message, so the object
    // case falls back to the generic "failed: 422" for `message` and relies
    // on the separate `detail` field for callers that need the structure.
    const message =
      typeof detail === "string" ? detail : `${init?.method ?? "GET"} ${path} failed: ${res.status}`;
    throw new ApiError(res.status, message, detail ?? undefined);
  }
  return (await res.json()) as T;
}

export function uploadSource(brandId: string, file: File, sourceKind?: SourceKind): Promise<UploadResult> {
  const form = new FormData();
  form.append("file", file);
  if (sourceKind) form.append("source_kind", sourceKind);
  return request<UploadResult>(`/brands/${encodeURIComponent(brandId)}/sources`, {
    method: "POST",
    body: form,
  });
}

export function listSources(brandId: string): Promise<SourceFile[]> {
  return request<SourceFile[]>(`/brands/${encodeURIComponent(brandId)}/sources`);
}

export function getTeamInput(brandId: string, sectionId: string): Promise<TeamInput | null> {
  return request<TeamInput | null>(
    `/brands/${encodeURIComponent(brandId)}/sections/${encodeURIComponent(sectionId)}/team-input`,
  );
}

export function submitTeamInput(
  brandId: string,
  sectionId: string,
  text: string,
  author?: string,
): Promise<{ status: string }> {
  return request<{ status: string }>(
    `/brands/${encodeURIComponent(brandId)}/sections/${encodeURIComponent(sectionId)}/team-input`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, author }),
    },
  );
}

export function runAllResearch(brandId: string): Promise<MarketResearchDocument> {
  return request<MarketResearchDocument>(`/brands/${encodeURIComponent(brandId)}/research/run-all`, {
    method: "POST",
  });
}

export function getDocument(documentId: string): Promise<MarketResearchDocument> {
  return request<MarketResearchDocument>(`/documents/${encodeURIComponent(documentId)}`);
}

export function approveDocument(
  documentId: string,
  approverId: string,
  decision: ApprovalChoice,
  note?: string,
): Promise<MarketResearchDocument> {
  return request<MarketResearchDocument>(`/documents/${encodeURIComponent(documentId)}/approve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ approver_id: approverId, decision, note: note ?? null }),
  });
}

export function getCheckpoint(documentId: string): Promise<QualityCheckpoint> {
  return request<QualityCheckpoint>(`/documents/${encodeURIComponent(documentId)}/checkpoint`);
}

export function getApprovalGate(documentId: string): Promise<ApprovalGateRecord | null> {
  return request<ApprovalGateRecord | null>(`/documents/${encodeURIComponent(documentId)}/approval-gate`);
}

export function listNotes(documentId: string): Promise<StrategicNote[]> {
  return request<StrategicNote[]>(`/documents/${encodeURIComponent(documentId)}/notes`);
}

export function addNote(
  documentId: string,
  section: string,
  text: string,
  author: string,
): Promise<StrategicNote> {
  return request<StrategicNote>(`/documents/${encodeURIComponent(documentId)}/notes`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ section, text, author }),
  });
}

export function distributeDocument(
  documentId: string,
  internal: boolean,
  client: boolean,
): Promise<DistributionRecord> {
  return request<DistributionRecord>(`/documents/${encodeURIComponent(documentId)}/distribute`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ internal, client }),
  });
}

export function getDistribution(documentId: string): Promise<DistributionRecord | null> {
  return request<DistributionRecord | null>(`/documents/${encodeURIComponent(documentId)}/distribution`);
}

export function getApprovalHistory(documentId: string): Promise<ApprovalEvent[]> {
  return request<ApprovalEvent[]>(`/documents/${encodeURIComponent(documentId)}/approval-history`);
}

export function rerunDocument(documentId: string): Promise<MarketResearchDocument> {
  return request<MarketResearchDocument>(`/documents/${encodeURIComponent(documentId)}/rerun`, {
    method: "POST",
  });
}

export function resubmitDocument(
  documentId: string,
  approverId: string,
  note: string,
): Promise<MarketResearchDocument> {
  return request<MarketResearchDocument>(`/documents/${encodeURIComponent(documentId)}/resubmit`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ approver_id: approverId, note }),
  });
}

export function listDistributionLinks(documentId: string): Promise<DistributionLink[]> {
  return request<DistributionLink[]>(`/documents/${encodeURIComponent(documentId)}/distribution-links`);
}

export function createDistributionLink(
  documentId: string,
  createdBy: string,
  ttlDays = 30,
): Promise<DistributionLinkCreated> {
  return request<DistributionLinkCreated>(`/documents/${encodeURIComponent(documentId)}/distribution-links`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ created_by: createdBy, ttl_days: ttlDays }),
  });
}

export function revokeDistributionLink(linkId: string): Promise<{ id: string; revoked: boolean }> {
  return request(`/distribution-links/${encodeURIComponent(linkId)}/revoke`, { method: "POST" });
}

export function getClientView(token: string): Promise<ClientMarketResearchView> {
  return request<ClientMarketResearchView>(`/client/view/${encodeURIComponent(token)}`);
}

// Step 4: Market Intel Core console -- all requests need the api-key header
// (api/deps.py's current_user), unlike the brand-workflow endpoints above
// which don't enforce auth yet (Step 4's gate lands as a separate PR).
function withApiKey(apiKey: string, init?: RequestInit): RequestInit {
  return { ...init, headers: { ...(init?.headers ?? {}), "api-key": apiKey } };
}

export function triggerStagingBuild(
  apiKey: string,
  sourcePaths: string[],
  targetVersion: number,
): Promise<{ status: string; target_version: number }> {
  return request(
    "/core/staging/build",
    withApiKey(apiKey, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ source_paths: sourcePaths, target_version: targetVersion }),
    }),
  );
}

export function listCoreVersions(): Promise<KBVersion[]> {
  return request<KBVersion[]>("/core/versions");
}

export function createPromotionRequest(
  apiKey: string,
  version: number,
  sourceSummary: string,
): Promise<{ request_id: string; kb_id: string; status: string; eval_result: EvalGateResult }> {
  return request(
    `/core/staging/${version}/promotion-requests`,
    withApiKey(apiKey, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ source_summary: sourceSummary }),
    }),
  );
}

export function decidePromotion(
  apiKey: string,
  requestId: string,
  decision: ApprovalChoice,
): Promise<{ request_id: string; decision: ApprovalChoice; kb_id?: string }> {
  return request(
    `/core/promotion-requests/${encodeURIComponent(requestId)}/decide`,
    withApiKey(apiKey, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ decision }),
    }),
  );
}

// Step 5 Part D: per-brand data source credentials + market segment
// whitelist -- both gated by resolve_brand_scope, same api-key discipline as
// the Core console above.
export function saveDataSourceCredential(
  apiKey: string,
  brandId: string,
  source: DataSourceKind,
  sourceApiKey: string,
  rateLimitPerHour = 60,
): Promise<{ status: string; source: DataSourceKind }> {
  return request(
    `/brands/${encodeURIComponent(brandId)}/data-sources/credentials`,
    withApiKey(apiKey, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ source, api_key: sourceApiKey, rate_limit_per_hour: rateLimitPerHour }),
    }),
  );
}

export function listDataSourceCredentials(
  apiKey: string,
  brandId: string,
): Promise<DataSourceCredentialSummary[]> {
  return request(
    `/brands/${encodeURIComponent(brandId)}/data-sources/credentials`,
    withApiKey(apiKey),
  );
}

export function getMarketSegment(apiKey: string, brandId: string): Promise<MarketSegment | null> {
  return request(`/brands/${encodeURIComponent(brandId)}/market-segments`, withApiKey(apiKey));
}

export function setMarketSegment(
  apiKey: string,
  brandId: string,
  segment: Omit<MarketSegment, "brand_id">,
): Promise<MarketSegment> {
  return request(
    `/brands/${encodeURIComponent(brandId)}/market-segments`,
    withApiKey(apiKey, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(segment),
    }),
  );
}
