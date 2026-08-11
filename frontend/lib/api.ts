import type {
  ApprovalChoice,
  MarketResearchDocument,
  SourceFile,
  SourceKind,
  TeamInput,
  UploadResult,
} from "./types";

export const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, init);
  if (!res.ok) {
    // FastAPI error responses are {"detail": "..."} -- surface that instead
    // of just the status code, so e.g. "LLM not configured" reaches the UI
    // instead of a bare "failed: 503".
    const detail = await res
      .clone()
      .json()
      .then((body) => (typeof body?.detail === "string" ? body.detail : null))
      .catch(() => null);
    const message = detail ?? `${init?.method ?? "GET"} ${path} failed: ${res.status}`;
    throw new ApiError(res.status, message);
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
): Promise<MarketResearchDocument> {
  return request<MarketResearchDocument>(`/documents/${encodeURIComponent(documentId)}/approve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ approver_id: approverId, decision }),
  });
}
