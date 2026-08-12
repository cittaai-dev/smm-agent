import type { VerifiedAudiencePersona } from "@/lib/types";

const ROWS: { field: keyof VerifiedAudiencePersona; label: string }[] = [
  { field: "name", label: "Name / label" },
  { field: "age_range", label: "Age range" },
  { field: "location", label: "Location" },
  { field: "occupation_income", label: "Occupation / income" },
  { field: "interests", label: "Interests" },
  { field: "pain_points", label: "Pain points" },
  { field: "preferred_platforms", label: "Preferred platforms" },
];

function cellValue(persona: VerifiedAudiencePersona, field: keyof VerifiedAudiencePersona): string {
  const value = persona[field];
  if (Array.isArray(value)) return value.join(", ");
  return value == null ? "" : String(value);
}

export function PersonaTable({ personas }: { personas: VerifiedAudiencePersona[] }) {
  const verified = personas.filter((p) => p.verified);

  if (verified.length === 0) {
    return <p className="text-sm text-text-faint">No verified personas yet.</p>;
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[480px] border-collapse text-sm" data-testid="persona-table">
        <thead>
          <tr>
            <th className="border border-border bg-success px-3 py-2 text-left font-semibold text-white">
              Persona detail
            </th>
            {verified.map((_, i) => (
              <th
                key={i}
                className="border border-border bg-success px-3 py-2 text-left font-semibold text-white"
              >
                Persona {i + 1}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {ROWS.map(({ field, label }) => (
            <tr key={field}>
              <td className="border border-border px-3 py-2 font-medium text-text">{label}</td>
              {verified.map((persona, i) => (
                <td key={i} className="border border-border px-3 py-2 text-text-dim">
                  {cellValue(persona, field)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
