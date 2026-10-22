import { useId, useState } from "react";

import type { AuthoringProposal } from "../../../api/types";
import { useTiers } from "../../useTiers";
import { processName, type OfferProgress } from "../format";
import { Primary, Secondary } from "./parts";

/** The one step on offer: what it does, why it is here, and the real options for it.
 *
 * **The recommended option is said in words, never by colour alone**, and it is the blueprint's own
 * choice — `keep` — with every alternative the resolver itself listed beneath it. Selecting an
 * option is a radio choice; nothing is applied until **Add it**, which is the deterministic request.
 *
 * Hover *and* keyboard focus preview an option on the canvas; the preview is enrichment and never
 * the only way to learn what an option is — its label and note are on the card.
 *
 * **Drawn as the *Build* board draws it**, with two departures. The tier chip is the served
 * vocabulary's name (*forced* where the board says *required*): tier words are declared once and
 * read, never typed here. And there is no *Skip*: rejecting a step left the protocol (the walk's
 * projection has no hole to leave; removing a step is a structural edit after the walk).
 */
export function StepProposalCard({
  proposal,
  progress,
  showGapDetails = false,
  busy,
  onAccept,
  onPreview,
  pinned = null,
  previewable = [],
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
  onAccept: (option: string, value?: string | number | boolean) => void;
  /** Hover and focus look at an option for a moment; **Preview** pins it until pressed again,
   *  closed, or Escape. A moment's look never clears a pinned one. */
  onPreview: (option: string | null, mode: "temporary" | "pinned") => void;
  /** The option whose complete preview is pinned now, from the page that shows it. */
  pinned?: string | null;
  /** Alternatives with a saved complete preview; only these can be pinned. */
  previewable?: string[];
  /** Ask why this step is here — a real turn to the model, not a canned sentence. */
  onExplain: () => void;
  /** Focus this step on the canvas — selecting a card highlights its object. */
  onSelect: () => void;
}) {
  const block = proposal.block;
  const group = useId();
  const [chosen, setChosen] = useState("keep");
  const [told, setTold] = useState("");
  /** A fact with declared values is picked, not typed (issue 341). */
  const [pick, setPick] = useState<string | number | boolean | null>(null);
  const tiers = useTiers();
  if (block.kind !== "step_proposal") return null;


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
    ...facts.map((id) => ({ id, label: `Tell me the ${id.slice(FACT.length).replaceAll("_", " ")}`,
                            note: block.need?.fact_reasons?.[id.slice(FACT.length)]
                              ?? "the rule that picks this tool reads it",
                            recommended: false })),
  ];
  const fact = chosen.startsWith(FACT) ? chosen.slice(FACT.length) : null;
  const values = fact ? block.need?.fact_values?.[fact] ?? null : null;
  const answer = values ? pick : typed(told);
  const accept = () => onAccept(chosen, fact ? answer ?? undefined : undefined);
  const unresolved = block.unresolved_settings ?? [];

  // **The card leads in plain words** (issue 387): the tool's curated description when there is
  // one, and the engine's reason only when there is not. The brief does not say the lead again.
  const lead = block.brief?.does?.text ?? block.reason;
  const place = !progress ? "Step" : progress.again ? `Review step ${progress.position} again` : `Step ${progress.position}`;
  const title = `${place} · ${processName(block.node)}`;

  return (
    <section aria-label={title} className="rounded-panel border px-[16px] pt-[14px] pb-[16px]"
             style={{ borderColor: "var(--line)", background: "var(--surface-2)" }}>
      <header className="flex items-baseline gap-[10px] mb-[8px]">
        <h3 className="m-0 text-[15px] font-semibold text-ink min-w-0 truncate" title={title}>{title}</h3>
        <span data-testid="step-tier" className="ml-auto shrink-0 rounded-full border px-[9px] py-[1px] text-[11.5px]"
              style={CHIP[block.tier] ?? CHIP[1]}>
          {/* **Never "measured" for a rule's step** (issue 387, as issue 268 settled for the
              transcript): tier 3's premise may be measured, typed or read by a model, so the chip
              says what tier 3 asks of a reader — its served group — rather than its name. */}
          {(block.tier === 3 ? tiers.group(3) : tiers.name(block.tier)).toLowerCase()}
        </span>
      </header>
      <button type="button" data-testid="select-step" onClick={onSelect}
              className="block w-full text-left bg-transparent border-0 p-0 cursor-pointer rounded-control
                         focus-visible:shadow-[var(--ring)]">
        <span className="block m-0 mb-[8px] text-[13.5px] leading-[1.55] text-ink">{lead}</span>
        <span className="block m-0 mb-[12px] font-data text-[11px] text-ink-3">
          {(block.consumes ?? []).join(", ") || "nothing"} → {block.produces.join(", ") || "nothing"}
        </span>
      </button>
      {block.brief && <Brief brief={block.brief} lead={lead} />}
      {(showGapDetails ? (block.gaps ?? []).length : unresolved.length) > 0 && (
        <div data-testid="step-gaps" className="mb-3 px-[10px] py-2 border"
             style={{ borderColor: "var(--line-2)" }}>
          <p className="m-0 mb-1 text-label text-ink-2">
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
      {previewable.length === 0 && block.alternatives.some((o) => offered.has(o.id)) && (
        <p className="m-0 mb-2 font-data text-[10.5px] text-ink-3">Preview unavailable for this older offer</p>
      )}
      <div role="radiogroup" aria-label={`options for ${processName(block.node)}`}>
        {options.map((option) => {
          const picked = chosen === option.id;
          return (
            <label
              key={option.id}
              data-testid={`option-${option.id}`}
              onMouseEnter={() => onPreview(option.id, "temporary")}
              onMouseLeave={() => onPreview(null, "temporary")}
              className="flex items-start gap-[10px] px-[12px] py-[10px] mb-[8px] border rounded-button cursor-pointer
                         focus-within:shadow-[var(--ring)]"
              style={{
                borderColor: picked ? "var(--now)" : "var(--line-2)",
                background: picked ? "var(--now-soft)" : "var(--surface)",
              }}
            >
              {/* The native radio stays, for the keyboard and a screen reader; the board's ring is
                  what is drawn. */}
              <input
                type="radio"
                name={group}
                value={option.id}
                checked={picked}
                onChange={() => setChosen(option.id)}
                onFocus={() => onPreview(option.id, "temporary")}
                onBlur={() => onPreview(null, "temporary")}
                className="sr-only"
              />
              <span
                aria-hidden
                className="mt-[2px] shrink-0 w-[16px] h-[16px] rounded-full border"
                style={{
                  borderColor: picked ? "var(--now)" : "var(--line-2)",
                  background: picked ? "radial-gradient(circle, var(--now) 0 4px, var(--surface) 4.5px)" : "var(--surface)",
                }}
              />
              <span className="min-w-0 flex-1">
                <span className="flex items-baseline gap-3">
                  <span className="font-data text-[12.5px] font-semibold text-ink min-w-0 break-all">{option.label}</span>
                  {option.recommended && (
                    <span className="ml-auto shrink-0 text-[11.5px] font-semibold text-now-ink">suggested</span>
                  )}
                </span>
                {option.note && option.id !== "keep" && (
                  <span className="block mt-[3px] text-[12.5px] leading-[1.5] text-ink-2">{option.note}</span>
                )}
              </span>
              {previewable.includes(option.id) && (
                <button
                  type="button"
                  data-testid={`preview-${option.id}`}
                  aria-pressed={pinned === option.id}
                  aria-label={`preview ${option.label} on the canvas`}
                  onClick={(e) => {
                    e.preventDefault();
                    onPreview(option.id, "pinned");
                  }}
                  className={`shrink-0 self-center text-[12px] p-0 bg-transparent border-0 underline
                              underline-offset-2 cursor-pointer rounded-control focus-visible:shadow-[var(--ring)]
                              ${pinned === option.id ? "text-now-ink font-semibold" : "text-now-ink"}`}
                >
                  {pinned === option.id ? "Previewing" : "Preview"}
                </button>
              )}
            </label>
          );
        })}
      </div>
      {fact && values && (
        <div role="radiogroup" aria-label={fact.replaceAll("_", " ")} className="flex flex-wrap gap-2 mb-2">
          {values.map((value) => (
            <label key={String(value)}
                   className="flex items-center gap-[6px] px-[10px] py-1 border cursor-pointer font-data
                              text-[11px] text-ink focus-within:shadow-[var(--ring)]"
                   style={{ borderColor: pick === value ? "var(--now)" : "var(--line-2)" }}>
              <input type="radio" name={`${group}-${fact}`} className="sr-only"
                     aria-label={valueWords(value)} checked={pick === value}
                     onChange={() => setPick(value)} />
              {valueWords(value)}
            </label>
          ))}
        </div>
      )}
      {fact && !values && (
        <label className="block mb-2 text-[12px] text-ink-2">
          <span className="block mb-1 text-label text-ink-3">
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
      <div className="flex flex-wrap items-center gap-[8px] mt-[12px]">
        <Primary data-testid="accept-step" disabled={busy || (fact !== null && (values ? pick === null : told.trim() === ""))}
                 onClick={accept}>
          {busy ? "Working…" : fact ? "Use this answer" : "Add it"}
        </Primary>
        <Secondary data-testid="explain-step" onClick={onExplain}>
          Why this one?
        </Secondary>
        {onCorrectAnswers && <Secondary onClick={onCorrectAnswers} disabled={busy}>
          Correct current answers
        </Secondary>}
      </div>
    </section>
  );
}

/** The tier chip in its meaning's colour: forced and convention are settled, so outlined. */
const CHIP: Record<number, React.CSSProperties> = {
  1: { borderColor: "var(--line-2)", color: "var(--ink-2)", background: "var(--surface)" },
  2: { borderColor: "var(--line-2)", color: "var(--ink-2)", background: "var(--surface)" },
  3: { borderColor: "transparent", color: "var(--measured-ink)", background: "var(--measured-soft)" },
  4: { borderColor: "transparent", color: "var(--needs-you-ink)", background: "var(--needs-you-soft)" },
};

const FACT = "fact_";

/** A declared value as a person reads it: yes and no for a yes-or-no fact. */
function valueWords(value: string | number | boolean): string {
  return value === true ? "yes" : value === false ? "no" : String(value);
}

/** A typed fact as the server checks it: a number when it reads as one. */
function typed(text: string): string | number {
  const trimmed = text.trim();
  return /^-?\d+(\.\d+)?$/.test(trimmed) ? Number(trimmed) : trimmed;
}


type StepBrief = NonNullable<Extract<AuthoringProposal["block"], { kind: "step_proposal" }>["brief"]>;

/** The card's four fields (spec §4.2), each line as the engine wrote it — part 5 designs them.
 *  A line the card already leads with is not said twice. */
function Brief({ brief, lead }: { brief: StepBrief; lead: string }) {
  const rows: [string, { text: string }[]][] = ([
    ["What it does", brief.does ? [brief.does] : []],
    ["Why it's here", brief.why],
    ["What it makes", brief.makes],
    ["Check", brief.check ?? []],
  ] as [string, { text: string }[]][]).map(([label, lines]) => [label, lines.filter((line) => line.text !== lead)]);
  return (
    <dl data-testid="step-brief" className="m-0 mb-3 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1">
      {rows
        .filter(([, lines]) => lines.length > 0)
        .map(([label, lines]) => (
          <div key={label} className="contents">
            <dt className="text-label text-ink-3 pt-[2px]">
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
