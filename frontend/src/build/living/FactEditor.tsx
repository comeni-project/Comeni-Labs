import { useId, useState } from "react";
import type { components } from "../../api/schema";

export type FactValue = string | number | boolean | (string | number | boolean)[] | null;
type Declaration = Pick<components["schemas"]["Measurement"], "id" | "kind"> &
  Partial<components["schemas"]["Measurement"]>;

/** Registry declarations determine the editor; the server validates every selection. */
export function FactEditor({ subject, value, kind, declaration, disabled = false, onSave }: {
  subject: string; value: FactValue; kind: "input" | "measurement";
  declaration?: Declaration; disabled?: boolean;
  onSave: (value: FactValue) => Promise<unknown>;
}) {
  const id = useId();
  const [typed, setTyped] = useState(value === null ? "" : Array.isArray(value) ? value.join(", ") : String(value));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const boolean = kind === "input" || declaration?.kind === "boolean";
  const enumerated = declaration?.kind === "enum";
  const numeric = declaration?.kind === "integer" || declaration?.kind === "number";
  const listed = Array.isArray(value);
  async function save(unknown = false) {
    let selected: FactValue = null;
    if (!unknown) {
      const parse = (text: string) => boolean ? text === "true" : numeric ? Number(text) : text;
      selected = listed ? typed.split(",").map(s => parse(s.trim())) : parse(typed);
    }
    setBusy(true); setError(null);
    try { await onSave(selected); }
    catch (failure) { setError(failure instanceof Error ? failure.message : String(failure)); }
    finally { setBusy(false); }
  }
  const locked = disabled || busy;
  return <form className="mt-2 text-[12px]" onSubmit={event => { event.preventDefault(); void save(); }}>
    <label htmlFor={id} className="sr-only">{subject}</label>
    {(boolean || enumerated) && !listed ? <select id={id} value={typed}
      disabled={locked} onChange={event => setTyped(event.target.value)} className="border bg-transparent p-1">
      <option value="">Choose an answer</option>
      {(boolean ? ["true", "false"] : declaration?.values ?? []).map(option =>
        <option key={option} value={option}>{boolean ? option === "true" ? "Yes" : "No" : option}</option>)}
    </select> : <input id={id} value={typed} disabled={locked}
      type={numeric && !listed ? "number" : "text"}
      min={declaration?.minimum ?? undefined} max={declaration?.maximum ?? undefined}
      step={declaration?.kind === "integer" ? 1 : "any"}
      onChange={event => setTyped(event.target.value)} className="border bg-transparent p-1 w-36" />}
    <button type="submit" disabled={locked || !typed.trim()}
      className="ml-2 text-now-ink underline">Save correction</button>
    <button type="button" disabled={locked} onClick={() => void save(true)}
      className="ml-2 text-ink-3 underline">Return to unknown</button>
    {kind === "input" && typed === "false" && <p>This input is unavailable; the chat will check what the analysis needs.</p>}
    {listed && <p>One value per sample, separated by commas.</p>}
    {error && <p role="alert" className="text-ink-2">{error}</p>}
  </form>;
}
