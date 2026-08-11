import type { ApprovalChoice, Deliverable, UploadResult } from "./types";

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
    throw new ApiError(res.status, `${init?.method ?? "GET"} ${path} failed: ${res.status}`);
  }
  return (await res.json()) as T;
}

export function uploadSource(brandId: string, file: File): Promise<UploadResult> {
  const form = new FormData();
  form.append("file", file);
  return request<UploadResult>(`/brands/${encodeURIComponent(brandId)}/sources`, {
    method: "POST",
    body: form,
  });
}

export function runResearch(brandId: string): Promise<Deliverable> {
  return request<Deliverable>(`/brands/${encodeURIComponent(brandId)}/research/run`, {
    method: "POST",
  });
}

export function getDeliverable(deliverableId: string): Promise<Deliverable> {
  return request<Deliverable>(`/deliverables/${encodeURIComponent(deliverableId)}`);
}

export function approveDeliverable(
  deliverableId: string,
  approverId: string,
  decision: ApprovalChoice,
): Promise<Deliverable> {
  return request<Deliverable>(`/deliverables/${encodeURIComponent(deliverableId)}/approve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ approver_id: approverId, decision }),
  });
}
