import { useEffect, useState } from "react";
import { get } from "../../api/client";
import type { components } from "../../api/schema";

export const sourceWords: Record<string, string> = {
  person_said: "you said", measured: "measured", model_read: "read by AI", open: "unknown",
};
export function factWords(value: unknown): string {
  return value == null ? "unknown" : Array.isArray(value) ? value.map(factWords).join(", ") :
    typeof value === "boolean" ? value ? "yes" : "no" : String(value);
}

/** Load history while expanded, keeping its current-answer labels in sync with corrections. */
export function FactHistory({ sessionId, subject, revision }: {
  sessionId: string; subject: string; revision: number;
}) {
  const [entries, setEntries] = useState<components["schemas"]["FactHistoryEntry"][] | null>(null);
  const [open, setOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    if (!open) return;
    let active = true;
    setEntries(null); setError(null);
    void get<components["schemas"]["FactHistoryView"]>(
      `/pipeline/authoring/${sessionId}/facts/${encodeURIComponent(subject)}/history`)
      .then(view => { if (active) setEntries(view.entries); })
      .catch(failure => { if (active) setError(String(failure)); });
    // A response for an older selection or identity must never relabel it as current.
    return () => { active = false; };
  }, [open, sessionId, subject, revision]);
  return <details className="mt-2 text-[11px]" onToggle={event => setOpen(event.currentTarget.open)}>
    <summary className="cursor-pointer text-ink-3">History of {subject}</summary>
    {error && <p role="alert">{error}</p>}
    {!entries && !error && <p>Loading history…</p>}
    <ol className="pl-4">
      {entries?.map(entry => <li key={entry.revision_id ?? entry.observation_id} className="my-2">
        {factWords(entry.value)} · {sourceWords[entry.origin]} · {entry.current ? "current answer" :
          entry.selected ? entry.action === "retract" ? "returned to unknown" : "previous answer" : entry.legacy ? "legacy observation; activation unknown" : "unused observation"}
        {entry.selected && <> · {entry.actor_kind === "unknown" ? "chooser unknown" :
          `${entry.actor_kind}: ${entry.who ?? "unknown"}`}</>}
        {entry.inherited && " · inherited"}
        <time className="block text-ink-4" dateTime={entry.at}>{entry.legacy && "Migrated at "}{new Date(entry.at).toLocaleString()}</time>
      </li>)}
    </ol>
    <p className="text-ink-4">History is read-only. Undo will be added later.</p>
  </details>;
}
