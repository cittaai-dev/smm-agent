// Mirrors backend/app/domain/*.py. Keep in sync by hand for Step 1; a generated
// openapi-typescript client (see CLAUDE.md's FE<->BE contract note) replaces
// this once the API surface stabilizes past Step 1.

export type RejectionReason = "missing_chunk" | "no_citation" | null;

export interface VerifiedClaim {
  section: string;
  text: string;
  chunk_id: string;
  block_span: [number, number];
  verified: boolean;
  rejection_reason: RejectionReason;
}

export type DeliverableStatus =
  | "draft"
  | "pending_approval"
  | "approved"
  | "rejected"
  | "insufficient_grounding";

export interface Deliverable {
  id: string;
  brand_id: string;
  status: DeliverableStatus;
  claims: VerifiedClaim[];
  call_site_trace: Record<string, number>;
}

export interface UploadResult {
  status: string;
}

export type ApprovalChoice = "approved" | "rejected";
