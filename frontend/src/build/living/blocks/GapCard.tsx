import { useId, useState } from "react";

import type { AuthoringProposal } from "../../../api/types";
import { BlockFrame, Primary, Secondary } from "./parts";

/** One thing the analysis needs that nobody has said yet, asked by the engine (14.7.3).
 *
 * **The options are the engine's**, and a click is the whole answer: no model reads it. An open
 * value (`read_length`) is a number field, checked by the server against the measurement's
 * declaration (`MI0208`) rather than here — a browser copy of the rule is a copy that can be
 * looser than the one that counts. *Not sure* and *can't share it* are answers, never skips:
 * nothing is guessed, and what is left open is decided later, by the person, at tier 4.
 */
export function GapCard({
  proposal,
  busy,
  onAnswer,
}: {
  proposal: AuthoringProposal;
  busy: boolean;
  onAnswer: (option: string, value?: number) => void;
}) {
  const field = useId();
  const [typed, setTyped] = useState("");
  const block = proposal.block;
  if (block.kind !== "question") return null;

  const typedOption = block.options.find((o) => o.id === "value");
  const buttons = block.options.filter((o) => o.id !== "value");
  // **Only the question's ordinary answers are primary.** Deferring, withholding, and the one that
  // ends the session (*I don't have one*) are secondary: an answer that stops everything must not
  // look like the recommended one (issue 168).
  const quiet = new Set(["not_sure", "cant_share", "dont_have"]);
  const number = typed.trim() === "" ? null : Number(typed);

  return (
    <BlockFrame label="a question about your data" title="What it needs" aside="asked by the engine">
      <p className="m-0 mb-1 text-[12.5px] text-ink">{block.asks}</p>
      <p className="m-0 mb-3 text-[11.5px] text-ink-3">{block.why_open}</p>
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
          <Primary
            disabled={busy || number === null || Number.isNaN(number)}
            onClick={() => number !== null && onAnswer("value", number)}
          >
            Use this
          </Primary>
        </div>
      )}
      <div className="flex flex-wrap gap-2">
        {buttons.map((option) =>
          quiet.has(option.id) || typedOption ? (
            <Secondary key={option.id} disabled={busy} onClick={() => onAnswer(option.id, undefined)}>
              {option.label}
            </Secondary>
          ) : (
            <Primary key={option.id} disabled={busy} onClick={() => onAnswer(option.id, undefined)}>
              {option.label}
            </Primary>
          ),
        )}
      </div>
    </BlockFrame>
  );
}
