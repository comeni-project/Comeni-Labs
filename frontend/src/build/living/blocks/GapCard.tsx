import { useId, useState } from "react";

import type { AuthoringProposal, SampleInspected } from "../../../api/types";
import { Explain, uploadHeadline } from "./Explain";
import { BlockFrame, Primary, Secondary } from "./parts";
import { SampleUpload } from "./SampleUpload";

/** One thing the analysis needs that nobody has said yet, asked by the engine (14.7.3).
 *
 * **The options are the engine's**, and a click is the whole answer: no model reads it. An open
 * value (`read_length`) is a number field, checked by the server against the measurement's
 * declaration (`MI0208`) rather than here — a browser copy of the rule is a copy that can be
 * looser than the one that counts. *Not sure* and *can't share it* are answers, never skips:
 * nothing is guessed, and what is left open is decided later, by the person, at tier 4.
 */
const DATA = { label: "a question about your data", title: "Needs you" };

export function GapCard({
  proposal,
  busy,
  onAnswer,
  onUpload,
  onAnswered = () => {},
  frame = DATA,
}: {
  proposal: AuthoringProposal;
  busy: boolean;
  onAnswer: (option: string, value?: number) => void;
  /** Answer with a sample (issue 134). Without it the `upload` answer is not drawn at all: a
   *  button that sent it would be refused, since the click is not an answer, the sample is. */
  onUpload?: (files: File[]) => Promise<SampleInspected>;
  onAnswered?: (result: SampleInspected, files: string[]) => void;
  /** What the question is about, for a screen reader and the eye: the data, unless said. */
  frame?: { label: string; title: string };
}) {
  const field = useId();
  // While a sample is out, the other answers wait: an answer and a sample must not race.
  const [measuring, setMeasuring] = useState(false);
  // While files are picked, *Measure* is the one primary: the others are drawn secondary.
  const [picked, setPicked] = useState(false);
  const block = proposal.block;
  // **A suggestion pre-fills, the person sends** (issues 170 and 171): a value the person stated,
  // or a model read from their reply, starts in the field and goes nowhere until they press.
  const [typed, setTyped] = useState(
    block.kind === "question" && block.value !== null && block.value !== undefined
      ? String(block.value) : "");
  if (block.kind !== "question") return null;
  // While the AI reads a sample, the other answers wait too (issue 135): two answers must not race.
  const waiting = measuring || block.reading?.state === "pending";
  const suggested = block.options.find((o) => o.recommended && o.note);
  // What it is and why it is asked (Part I.1); an offer made before that carries none.
  const explained = proposal.envelope?.offer === "gap" ? proposal.envelope.explain ?? null : null;
  const headline = explained ? uploadHeadline(explained) : null;

  const typedOption = block.options.find((o) => o.id === "value");
  const uploadOption = block.options.find((o) => o.id === "upload");
  const buttons = block.options.filter((o) => o.id !== "value" && o.id !== "upload");
  // **Only the question's ordinary answers are primary.** Deferring, withholding, and the one that
  // ends the session (*I don't have one*) are secondary: an answer that stops everything must not
  // look like the recommended one (issue 168).
  const quiet = new Set(["not_sure", "cant_share", "dont_have"]);
  const number = typed.trim() === "" ? null : Number(typed);
  const Send = picked ? Secondary : Primary;

  return (
    <BlockFrame label={frame.label} title={frame.title}>
      <h3 className="m-0 mb-1 text-[15px] leading-[1.4] font-semibold text-ink">{block.asks}</h3>
      <p className="m-0 mb-3 text-[12.5px] text-ink-2">{block.why_open}</p>
      {explained && <Explain explanation={explained} />}
      {suggested && (
        <p data-testid="suggested" className="m-0 mb-3 text-[12px] text-now-ink">
          {suggested.id === "value" ? String(block.value ?? "") : suggested.label} — {suggested.note}
        </p>
      )}
      {typedOption && (
        <div className="flex items-center gap-2 mb-3">
          <label htmlFor={field} className="sr-only">{typedOption.label}</label>
          <input
            id={field}
            type="number"
            aria-label={typedOption.label}
            placeholder={typedOption.label}
            value={typed}
            onChange={(e) => setTyped(e.target.value)}
            className="w-[140px] font-data text-[12px] bg-transparent text-ink border px-2 py-[5px]"
            style={{ borderColor: "var(--line-2)" }}
          />
          <Send
            disabled={busy || waiting || number === null || Number.isNaN(number)}
            onClick={() => number !== null && onAnswer("value", number)}
          >
            Use this
          </Send>
        </div>
      )}
      {uploadOption && onUpload && (
        <div className="mb-3">
          {headline && <p className="m-0 mb-2 text-[12px] text-ink-2">{headline}</p>}
          <SampleUpload
            proposalId={proposal.id}
            label={uploadOption.label}
            busy={busy}
            onUpload={onUpload}
            onAnswered={onAnswered}
            onMeasuring={setMeasuring}
            onPicked={setPicked}
            reading={block.reading ?? null}
            files={explained?.files ?? 1}
          />
        </div>
      )}
      <div className="flex flex-wrap gap-2">
        {buttons.map((option) =>
          picked || quiet.has(option.id) || typedOption || (suggested && suggested.id !== option.id) ? (
            <Secondary key={option.id} disabled={busy || waiting} onClick={() => onAnswer(option.id, undefined)}>
              {option.label}
            </Secondary>
          ) : (
            <Primary key={option.id} disabled={busy || waiting} onClick={() => onAnswer(option.id, undefined)}>
              {option.label}
            </Primary>
          ),
        )}
      </div>
      {/* **Who asked, who worded it, whose explanation: one quiet line** (one builder plan 3).
          The words may be a model's; the question and its answers are the engine's. */}
      <p data-testid="provenance" className="m-0 mt-3 font-data text-[10.5px] text-ink-3">
        {["asked by the engine", block.phrasing === "done" ? "worded by the model" : null,
          explained?.what ? "curated explanation" : null].filter(Boolean).join(" · ")}
      </p>
    </BlockFrame>
  );
}
