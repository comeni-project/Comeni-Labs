import { useEffect, useRef, useState } from "react";
import type { AuthoringSession, AuthoringVocabulary } from "../../api/types";
import { FactEditor, type FactValue } from "./FactEditor";
import { FactHistory, factWords, sourceWords } from "./FactHistory";

export type CorrectFact = (subject: string, value: FactValue, kind: "input" | "measurement") => Promise<unknown>;
export function CurrentFacts({ session, declarations, onCorrect, onRelease, openRequest = 0, disabled = false }: {
  session: AuthoringSession; declarations?: AuthoringVocabulary["measurements"];
  onCorrect?: CorrectFact; disabled?: boolean; openRequest?: number;
  onRelease?: (type: string, states: string[]) => Promise<unknown>;
}) {
  const [editing, setEditing] = useState<string | null>(null);
  const details = useRef<HTMLDetailsElement>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    if (openRequest && details.current) {
      details.current.open = true;
      details.current.scrollIntoView?.({ block: "start" });
    }
  }, [openRequest]);
  const pins = session.goal?.constraints?.producers ?? [];
  const facts = (session.facts ?? []).filter(fact => fact.kind === "measurement");
  const absent = (session.fact_subjects ?? []).filter(subject => !facts.some(fact => fact.subject === subject));
  const inputs = session.inputs ?? [];
  if (!facts.length && !inputs.length && !pins.length && !absent.length) return null;
  return <details ref={details} className="mb-4 text-[12px]" open={editing !== null ? true : undefined}>
    <summary className="cursor-pointer text-ink-2">Current answers · {facts.length + inputs.length + absent.length}</summary>
    {error && <p role="alert">{error}</p>}
    {pins.map(pin => <p key={`${pin.site.type_id}:${pin.site.states.join(",")}`}>
      Tool choice for {pin.site.type_id}: {pin.contract}
      {onRelease && <button disabled={disabled} className="ml-2 text-link underline" onClick={() => {
        void onRelease(pin.site.type_id, pin.site.states).catch(failure => setError(String(failure)));
      }}>Release this tool choice</button>}
    </p>)}
    {session.ownership === "manual" && <p>Corrections open a new linked draft and preserve your manual work.</p>}
    {[...inputs.map(input => ({ subject: input.key, label: input.name ?? input.type_id,
      value: input.origin === "open" ? null : input.present, source: input.origin, kind: "input" as const })),
    ...facts.map(fact => ({ subject: fact.subject, label: fact.subject, value: fact.value ?? null,
      source: fact.source, kind: "measurement" as const })),
    ...absent.map(subject => ({ subject, label: subject, value: null, source: "open", kind: "measurement" as const }))].map(fact => <div key={`${fact.kind}:${fact.subject}`} className="border-t py-2">
      <span>{fact.label}: {factWords(fact.value)} · {sourceWords[fact.source]}</span>
      {onCorrect && <button type="button" disabled={disabled} className="ml-2 text-link underline"
        onClick={() => setEditing(editing === fact.subject ? null : fact.subject)}>Correct {fact.label}</button>}
      {editing === fact.subject && onCorrect && <FactEditor subject={fact.subject} value={fact.value}
        kind={fact.kind} declaration={declarations?.[fact.subject]} disabled={disabled}
        onSave={value => onCorrect(fact.subject, value, fact.kind)} />}
      {<FactHistory sessionId={session.id} subject={fact.subject} revision={session.row_version} />}
    </div>)}
  </details>;
}
