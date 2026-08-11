import type { VerifiedAudiencePersona } from "@/lib/types";

const REASON_LABELS: Record<string, string> = {
  no_citation: "No citation was provided",
  missing_chunk: "Citation does not resolve to any retrieved chunk",
  incomplete_persona: "Missing pain points or interests -- not grounded enough to act on",
};

export function PersonaCard({ persona }: { persona: VerifiedAudiencePersona }) {
  const borderColor = persona.verified ? "border-green-500" : "border-red-500";
  return (
    <div className={`rounded-lg border-2 p-4 ${borderColor}`} data-testid="persona-card">
      <p className="font-medium text-slate-900">{persona.name}</p>

      {persona.pain_points.length > 0 && (
        <div className="mt-2">
          <p className="text-xs font-medium uppercase tracking-wide text-slate-500">Pain points</p>
          <ul className="list-inside list-disc text-sm text-slate-700">
            {persona.pain_points.map((p) => (
              <li key={p}>{p}</li>
            ))}
          </ul>
        </div>
      )}

      {persona.interests.length > 0 && (
        <div className="mt-2">
          <p className="text-xs font-medium uppercase tracking-wide text-slate-500">Interests</p>
          <ul className="list-inside list-disc text-sm text-slate-700">
            {persona.interests.map((p) => (
              <li key={p}>{p}</li>
            ))}
          </ul>
        </div>
      )}

      <div className="mt-3 flex items-center gap-2 text-xs text-slate-500">
        <code className="rounded bg-slate-100 px-1.5 py-0.5">
          {persona.chunk_ids.length > 0 ? persona.chunk_ids.join(", ") : "no citation"}
        </code>
        {persona.verified ? (
          <span className="text-green-700">verified</span>
        ) : (
          <span className="text-red-700">
            rejected — {REASON_LABELS[persona.rejection_reason ?? ""] ?? persona.rejection_reason}
          </span>
        )}
      </div>
    </div>
  );
}
