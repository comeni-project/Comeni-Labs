import { useId, useState } from "react";

import type { AuthoringProposal } from "../../../api/types";
import { processName, stepWords, type OfferProgress } from "../format";
import { BlockFrame, Primary, Secondary } from "./parts";

/** The one step on offer: what it does, why it is here, and the real options for it.
 *
 * **The recommended option is said in words, never by colour alone**, and it is the blueprint's own
 * choice — `keep` — with every alternative the resolver itself listed beneath it. Selecting an
 * option is a radio choice; nothing is applied until **Add it**, which is the deterministic request.
 *
 * Hover *and* keyboard focus preview an option on the canvas; the preview is enrichment and never
 * the only way to learn what an option is — its label and note are on the card.
 */
export function StepProposalCard({
  proposal,
  progress,
  showGapDetails = false,
  busy,
  onAccept,
  onPreview,
  onExplain,
  onSelect,
  onCorrectAnswers,
}: {
  proposal: AuthoringProposal;
  onCorrectAnswers?: () => void;
  /** Where this step stood in the plan when it was offered; `null` for an older offer. */
  progress: OfferProgress | null;
  /** Dev mode as the build recorded it: gap kinds and the files to fix are shown only then. */
  showGapDetails?: boolean;
  busy: boolean;
  /** `keep` (*Continue*), an alternative's id, or `fact_<measurement>` with the typed value. */
  onAccept: (option: string, value?: string | number) => void;
  onPreview: (option: string | null) => void;
  /** Ask why this step is here — a real turn to the model, not a canned sentence. */
  onExplain: () => void;
  /** Focus this step on the canvas — selecting a card highlights its object. */
  onSelect: () => void;
}) {
  const block = proposal.block;
  const group = useId();
  const [chosen, setChosen] = useState("keep");
  const [told, setTold] = useState("");
  const [previewing, setPreviewing] = useState<string | null>(null);
  if (block.kind !== "step_proposal") return null;

  /** Touch has no hover, so a preview is an explicit press — and pressing it again clears it. */
  const togglePreview = (option: string) => {
    const next = previewing === option ? null : option;
    setPreviewing(next);
    onPreview(next);
  };

  // **Only what the card offered can be sent** (spec §14.5): an alternative that cannot be built
  // from this goal is shown, with why, and is not a choice.
  const offered = new Set(proposal.options);
  const refused = block.alternatives.filter((option) => !offered.has(option.id));
  const facts = proposal.options.filter((id) => id.startsWith(FACT));
  const options = [
    { id: "keep", label: processName(block.node), note: block.reason, recommended: true },
    ...block.alternatives
      .filter((option) => offered.has(option.id))
      .map((option) => ({ id: option.id, label: option.label, note: option.note ?? "",
                          recommended: false })),
    ...facts.map((id) => ({ id, label: `Tell me the ${id.slice(FACT.length)}`,
                            note: "the rule that picks this tool reads it", recommended: false })),
  ];
  const fact = chosen.startsWith(FACT) ? chosen.slice(FACT.length) : null;
  const accept = () => onAccept(chosen, fact ? typed(told) : undefined);
  const unresolved = block.unresolved_settings ?? [];

  return (
    <BlockFrame
      label={`${stepWords(progress).toLowerCase()}: ${processName(block.node)}`}
      title={`${stepWords(progress)} — ${processName(block.node)}`}
      aside={`tier ${block.tier}`}
      actions={
        <>
          <Primary data-testid="accept-step" disabled={busy || (fact !== null && told.trim() === "")}
                   onClick={accept}>
            {busy ? "Working…" : chosen === "keep" ? "Continue" : "Change it"}
          </Primary>
          {onCorrectAnswers && <Secondary onClick={onCorrectAnswers} disabled={busy}>
            Correct current answers
          </Secondary>}
          <Secondary data-testid="explain-step" onClick={onExplain}>
            Show me why
          </Secondary>
        </>
      }
    >
      <button type="button" data-testid="select-step" onClick={onSelect}
              className="block w-full text-left bg-transparent border-0 p-0 cursor-pointer
                         focus-visible:shadow-[var(--ring)]">
        <span className="block m-0 mb-2 text-[13px] leading-[1.55] text-ink">{block.reason}</span>
        <span className="block m-0 mb-3 font-data text-[10.5px] text-ink-3">
          {(block.consumes ?? []).join(", ") || "nothing"} → {block.produces.join(", ") || "nothing"}
        </span>
      </button>
      {block.brief && <Brief brief={block.brief} />}
      {(showGapDetails ? (block.gaps ?? []).length : unresolved.length) > 0 && (
        <div data-testid="step-gaps" className="mb-3 px-[10px] py-2 border"
             style={{ borderColor: "var(--line-2)" }}>
          <p className="m-0 mb-1 font-data text-[10px] tracking-[.12em] uppercase text-ink-2">
            Registry information is incomplete
          </p>
          {showGapDetails ? (
            <ul className="m-0 p-0 list-none">
              {(block.gaps ?? []).map((gap) => (
                <li key={`${gap.kind}-${gap.subject}`} className="text-[12px] text-ink-2">
                  {gap.kind.replaceAll("_", " ")}: {gap.subject}{" "}
                  <span className="font-data text-[11px] text-ink-3">— fix {gap.fix}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="m-0 text-[12px] text-ink-2">
              No values are listed for {unresolved.join(", ")}, so {unresolved.length === 1 ? "it stays" : "they stay"} unset.
              It is not something you need to provide.
            </p>
          )}
        </div>
      )}
      <div role="radiogroup" aria-label={`options for ${processName(block.node)}`}>
        {options.map((option) => {
          const picked = chosen === option.id;
          return (
            <label
              key={option.id}
              data-testid={`option-${option.id}`}
              onMouseEnter={() => onPreview(option.id)}
              onMouseLeave={() => onPreview(null)}
              className="flex items-start gap-[9px] px-[10px] py-2 mb-[6px] border cursor-pointer
                         focus-within:shadow-[0_0_0_1px_color-mix(in_oklab,var(--link)_30%,transparent)]"
              style={{
                borderColor: picked ? "var(--link-line)" : "var(--line)",
                background: picked ? "var(--paper-2)" : "transparent",
              }}
            >
              {/* The native radio stays, for the keyboard and a screen reader; the artboard's square
                  dot is what is drawn. A circle beside square cards was the first render's tell. */}
              <input
                type="radio"
                name={group}
                value={option.id}
                checked={picked}
                onChange={() => setChosen(option.id)}
                onFocus={() => onPreview(option.id)}
                onBlur={() => onPreview(null)}
                className="sr-only"
              />
              <span
                aria-hidden
                className="mt-[3px] shrink-0 w-[9px] h-[9px] border"
                style={{
                  borderColor: picked ? "var(--link)" : "var(--port-line)",
                  background: picked ? "var(--link)" : "transparent",
                  boxShadow: picked ? "inset 0 0 0 2px var(--paper-2)" : undefined,
                }}
              />
              <span className="min-w-0 flex-1">
                <span className="flex items-baseline gap-3">
                  <span className="font-data text-[11px] text-ink">{option.label}</span>
                  {option.recommended && (
                    <span className="ml-auto font-data text-[9.5px] text-link">recommended</span>
                  )}
                </span>
                {option.note && option.id !== "keep" && (
                  <span className="block mt-1 text-[12px] text-ink-2">{option.note}</span>
                )}
              </span>
              {option.id !== "keep" && !option.id.startsWith(FACT) && (
                <button
                  type="button"
                  data-testid={`preview-${option.id}`}
                  aria-pressed={previewing === option.id}
                  aria-label={`preview ${option.label} on the canvas`}
                  onClick={(e) => {
                    e.preventDefault();
                    togglePreview(option.id);
                  }}
                  className="shrink-0 self-center font-data text-[10px] px-2 py-[2px] bg-transparent
                             text-ink-2 border cursor-pointer focus-visible:shadow-[var(--ring)]"
                  style={{ borderColor: previewing === option.id ? "var(--link)" : "var(--line-2)" }}
                >
                  Preview
                </button>
              )}
            </label>
          );
        })}
      </div>
      {fact && (
        <label className="block mb-2 text-[12px] text-ink-2">
          <span className="block mb-1 font-data text-[10px] tracking-[.08em] uppercase text-ink-3">
            {fact}
          </span>
          <input aria-label={fact} value={told} onChange={(e) => setTold(e.target.value)}
                 className="w-full px-2 py-1 border bg-transparent font-data text-[12px] text-ink
                            focus-visible:shadow-[var(--ring)]"
                 style={{ borderColor: "var(--line-2)" }} />
        </label>
      )}
      {refused.length > 0 && (
        <ul aria-label="tools that cannot be used here" className="m-0 p-0 list-none">
          {refused.map((option) => (
            <li key={option.id} data-testid={`refused-${option.id}`}
                className="px-[10px] py-1 text-[11.5px] text-ink-3">
              <span className="font-data">{option.label}</span> — {option.note}
            </li>
          ))}
        </ul>
      )}
    </BlockFrame>
  );
}

const FACT = "fact_";

/** A typed fact as the server checks it: a number when it reads as one. */
function typed(text: string): string | number {
  const trimmed = text.trim();
  return /^-?\d+(\.\d+)?$/.test(trimmed) ? Number(trimmed) : trimmed;
}


type StepBrief = NonNullable<Extract<AuthoringProposal["block"], { kind: "step_proposal" }>["brief"]>;

/** The card's four fields (spec §4.2), each line as the engine wrote it — part 5 designs them. */
function Brief({ brief }: { brief: StepBrief }) {
  const rows: [string, { text: string }[]][] = [
    ["What it does", brief.does ? [brief.does] : []],
    ["Why it's here", brief.why],
    ["What it makes", brief.makes],
    ["Check", brief.check ?? []],
  ];
  return (
    <dl data-testid="step-brief" className="m-0 mb-3 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1">
      {rows
        .filter(([, lines]) => lines.length > 0)
        .map(([label, lines]) => (
          <div key={label} className="contents">
            <dt className="font-data text-[10px] tracking-[.08em] uppercase text-ink-3 pt-[2px]">
              {label}
            </dt>
            <dd className="m-0 text-[12.5px] leading-[1.5] text-ink-2">
              {lines.map((line, i) => (
                <span key={i} className="block">{line.text}</span>
              ))}
            </dd>
          </div>
        ))}
    </dl>
  );
}
