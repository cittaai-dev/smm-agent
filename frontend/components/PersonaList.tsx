import type { VerifiedAudiencePersona } from "@/lib/types";
import { PersonaCard } from "./PersonaCard";

export function PersonaList({ personas }: { personas: VerifiedAudiencePersona[] }) {
  if (personas.length === 0) {
    return null;
  }
  return (
    <div className="flex flex-col gap-3">
      <p className="text-xs font-medium uppercase tracking-wide text-slate-500">Audience personas</p>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {personas.map((persona) => (
          <PersonaCard key={persona.persona_id} persona={persona} />
        ))}
      </div>
    </div>
  );
}
