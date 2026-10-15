import { useState } from "react";
import type { AuthoringProposal, AuthoringVocabulary } from "../../../api/types";
import { FactEditor, type FactValue } from "../FactEditor";
import { BlockFrame, Secondary } from "./parts";
export function DisagreementCard({ proposal, declarations, busy, onAnswer }: {
  proposal: AuthoringProposal; declarations?: AuthoringVocabulary["measurements"];
  busy: boolean; onAnswer: (option: string, value?: FactValue) => Promise<unknown>;
}) {
  const [correcting, setCorrecting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const offer = proposal.envelope;
  if (offer.offer !== "disagreement") return null;
  async function answer(option: string, value?: FactValue) {
    try { setError(null); await onAnswer(option, value); }
    catch (failure) { setError(String(failure)); }
  }
  return <BlockFrame label="check conflicting evidence" title="Your answer and this sample differ" aside="asked by the engine">
    <p className="text-[12.5px]">{offer.block.asks}</p>
    <p className="text-[11.5px] text-ink-3">{offer.block.why_open}</p>
    <div className="flex flex-wrap gap-2">{offer.block.options.map(option =>
      <Secondary key={option.id} disabled={busy} onClick={() => option.id === "correct" ?
        setCorrecting(true) : void answer(option.id)}>{option.label}</Secondary>)}</div>
    {correcting && <FactEditor subject={offer.subject} value={offer.current_value}
      kind="measurement" declaration={declarations?.[offer.subject]} disabled={busy}
      onSave={value => answer(value === null ? "unknown" : "correct", value)} />}
    {error && <p role="alert">{error}</p>}
  </BlockFrame>;
}
