import type { VerifiedAudiencePersona } from "@/lib/types";

const REASON_LABELS: Record<string, string> = {
  no_citation: "No citation was provided",
  missing_chunk: "Citation does not resolve to any retrieved chunk",
  incomplete_persona: "Missing pain points or interests -- not grounded enough to act on",
};

export function PersonaCard({ persona }: { persona: VerifiedAudiencePersona }) {
  const borderColor = persona.verified ? "border-success" : "border-danger";
  return (
    <div className={`rounded-lg border-2 p-4 ${borderColor}`} data-testid="persona-card">
      <p className="font-medium text-text">{persona.name}</p>

      {persona.pain_points.length > 0 && (
        <div className="mt-2">
          <p className="text-xs font-medium uppercase tracking-wide text-text-dim">Pain points</p>
          <ul className="list-inside list-disc text-sm text-text-dim">
            {persona.pain_points.map((p) => (
              <li key={p}>{p}</li>
            ))}
          </ul>
        </div>
      )}

      {persona.interests.length > 0 && (
        <div className="mt-2">
          <p className="text-xs font-medium uppercase tracking-wide text-text-dim">Interests</p>
          <ul className="list-inside list-disc text-sm text-text-dim">
            {persona.interests.map((p) => (
              <li key={p}>{p}</li>
            ))}
          </ul>
        </div>
      )}

      <div className="mt-3 flex items-center gap-2 text-xs text-text-dim">
        <code className="rounded bg-surface2 px-1.5 py-0.5 font-mono">
          {persona.chunk_ids.length > 0 ? persona.chunk_ids.join(", ") : "no citation"}
        </code>
        {persona.verified ? (
          <span className="text-success">
            verified{persona.confidence < 1 ? ` (confidence ${persona.confidence.toFixed(2)})` : ""}
          </span>
        ) : (
          <span className="text-danger">
            rejected — {REASON_LABELS[persona.rejection_reason ?? ""] ?? persona.rejection_reason}
          </span>
        )}
      </div>
    </div>
  );
}
