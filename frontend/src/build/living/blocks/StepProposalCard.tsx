import { useId, useState } from "react";

import type { AuthoringProposal } from "../../../api/types";
import { processName } from "../format";
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
  position,
  busy,
  onAccept,
  onReject,
  onPreview,
  onExplain,
  onSelect,
}: {
  proposal: AuthoringProposal;
  /** `4` in *step 4*. */
  position: number;
  busy: boolean;
  onAccept: (option: string) => void;
  onReject: () => void;
  onPreview: (option: string | null) => void;
  /** Ask why this step is here — a real turn to the model, not a canned sentence. */
  onExplain: () => void;
  /** Focus this step on the canvas — selecting a card highlights its object. */
  onSelect: () => void;
}) {
  const block = proposal.block;
  const group = useId();
  const [chosen, setChosen] = useState("keep");
  const [previewing, setPreviewing] = useState<string | null>(null);
  if (block.kind !== "step_proposal") return null;

  /** Touch has no hover, so a preview is an explicit press — and pressing it again clears it. */
  const togglePreview = (option: string) => {
    const next = previewing === option ? null : option;
    setPreviewing(next);
    onPreview(next);
  };

  const options = [
    { id: "keep", label: processName(block.node), note: block.reason, recommended: true },
    ...block.alternatives.map((option) => ({
      id: option.id,
      label: option.label,
      note: option.note ?? "",
      recommended: false,
    })),
  ];

  return (
    <BlockFrame
      label={`step ${position}: ${processName(block.node)}`}
      title={`Step ${position} — ${processName(block.node)}`}
      aside={`tier ${block.tier}`}
      actions={
        <>
          <Primary data-testid="accept-step" disabled={busy} onClick={() => onAccept(chosen)}>
            {busy ? "Adding…" : "Add it"}
          </Primary>
          <Secondary data-testid="explain-step" onClick={onExplain}>
            Show me why
          </Secondary>
          <Secondary data-testid="reject-step" disabled={busy} onClick={onReject}>
            Skip
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
      <div role="radiogroup" aria-label={`options for step ${position}`}>
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
              {option.id !== "keep" && (
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
    </BlockFrame>
  );
}
