import type { VerifiedClaim } from "./types";

// Pure grouping over already-verified claims -- the same operation
// docx_builder.py's _group_claims does server-side for the .docx export, so
// the live document view and the download never drift apart. Never a second
// write path: this is computed at render time from data the API already
// returned, exactly like domain/client_view.py's projection precedent.

export function groupClaimsByKey(claims: VerifiedClaim[]): Record<string, Record<string, string>> {
  const groups: Record<string, Record<string, string>> = {};
  for (const c of claims) {
    if (!c.verified || !c.group_key || !c.field_key) continue;
    (groups[c.group_key] ??= {})[c.field_key] = c.text;
  }
  return groups;
}

export function groupClaimsByField(claims: VerifiedClaim[]): Record<string, string[]> {
  const groups: Record<string, string[]> = {};
  for (const c of claims) {
    if (!c.verified || !c.field_key) continue;
    (groups[c.field_key] ??= []).push(c.text);
  }
  return groups;
}
