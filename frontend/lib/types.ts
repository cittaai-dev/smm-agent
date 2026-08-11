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

export type VerifiedAudiencePersona = components["schemas"]["VerifiedAudiencePersona"];
export type PersonaRejectionReason = VerifiedAudiencePersona["rejection_reason"];

export type QualityCheckpoint = components["schemas"]["QualityCheckpoint"];
export type StrategicNote = components["schemas"]["StrategicNote"];
export type DistributionRecord = components["schemas"]["DistributionRecord"];
export type ApprovalGateRecord = components["schemas"]["ApprovalGateRecord"];

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

// Shape of the 422 the approve endpoint raises when the QualityCheckpoint
// gate fails -- distinct from the plain-string `detail` every other error
// uses, so ApiError carries it separately rather than losing it to the
// generic "failed: 422" message.
export interface CheckpointFailedDetail {
  reason: "quality_checkpoint_failed";
  checkpoint: QualityCheckpoint;
}

// Step 4: Market Intel Core types. Hand-written, not yet in api-types.ts --
// re-run `gen:api-types` against a running backend once these endpoints ship
// and delete these in favor of the generated components["schemas"] versions,
// matching every other type in this file.
export interface EvalGateResult {
  citation_rejection_rate: number;
  degraded_ratio: number;
  l0_ratio: number;
  coverage_ok: boolean;
  passed: boolean;
  thresholds: Record<string, number>;
}

export type KBVersionStatus = "staging" | "promoted" | "rejected";

export interface KBVersion {
  kb_id: string;
  version: number;
  status: KBVersionStatus;
  eval_gate_result: EvalGateResult | null;
  promoted_at: string | null;
  promoted_by: string | null;
}

// Shape of the 422 the promotion-requests endpoint raises when the eval gate
// blocks a staging corpus -- same pattern as CheckpointFailedDetail above.
export interface EvalGateFailedDetail {
  reason: "eval_gate_failed";
  result: EvalGateResult;
}

export interface BridgeChunk {
  chunk_id: string;
  kb_id: string;
  text: string;
}

export interface BridgePair {
  run_chunk: BridgeChunk;
  core_chunk: BridgeChunk;
}

// Step 5: trust boundary types. Hand-written for the same reason as the Step
// 4 block above -- re-run `gen:api-types` and delete these once these
// endpoints are exercised against a running backend.
export type ApprovalDecisionKind = "approved" | "rejected" | "resubmitted";

export interface ApprovalEvent {
  id: number | null;
  document_id: string;
  decision: ApprovalDecisionKind;
  approver_id: string;
  note: string | null;
  checkpoint: QualityCheckpoint | null;
  decided_at: string | null;
}

export interface DistributionLink {
  id: string;
  document_id: string;
  created_by: string;
  expires_at: string;
  revoked: boolean;
  created_at: string | null;
}

export interface DistributionLinkCreated {
  id: string;
  token: string;
  expires_at: string;
}

export interface ClientClaim {
  text: string;
}

export interface ClientPersona {
  name: string;
  pain_points: string[];
  interests: string[];
}

export interface ClientMarketResearchView {
  brand_id: string;
  sections: Record<string, ClientClaim[]>;
  personas: ClientPersona[];
}

export type DataSourceKind = "google_trends" | "newsapi" | "youtube" | "scrapy_competitor";

export interface DataSourceCredentialSummary {
  source: DataSourceKind;
  rate_limit_per_hour: number;
  created_at: string | null;
  last_used_at: string | null;
}

export interface MarketSegment {
  brand_id: string;
  segment_name: string;
  youtube_channel_keywords: string[];
  news_sources: string[];
  reddit_communities: string[];
  website_urls: string[];
  max_competitors_to_track: number;
}
