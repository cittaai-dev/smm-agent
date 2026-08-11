// Domain types are generated from the backend's OpenAPI schema into
// ./api-types.ts (see package.json's gen:api-types script) -- re-run that
// against a running backend whenever the API surface changes. This file just
// re-exports ergonomic names from the generated schemas, plus genuinely
// FE-only shapes the backend doesn't own.
import type { components } from "./api-types";

export type SectionId = components["schemas"]["SectionResult"]["section"];
export type SectionStatus = components["schemas"]["SectionResult"]["status"];
export type SectionResult = components["schemas"]["SectionResult"];

export type DocumentStatus = components["schemas"]["MarketResearchDocument"]["status"];
export type MarketResearchDocument = components["schemas"]["MarketResearchDocument"];

export type VerifiedClaim = components["schemas"]["VerifiedClaim"];
export type RejectionReason = VerifiedClaim["rejection_reason"];

export type SourceFile = components["schemas"]["SourceFile"];
export type SourceKind = components["schemas"]["SourceFile"]["source_kind"];

export interface UploadResult {
  status: string;
}

export interface TeamInput {
  text: string;
  author: string | null;
}

export type ApprovalChoice = "approved" | "rejected";
