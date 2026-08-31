import { useState } from "react";

import type { Answered, AnsweredStep } from "./useBuilder";
import { open as isOpen } from "./useBuilder";

/** **The rail is about the CHOICE. The card on the node is about the VALUES.**
 *
 * `impl-settled` is explicit, and this file is where it lands:
 *
 * > SETTINGS LIVE IN THE CARD ON THE NODE, not the rail. The rail is about the CHOICE — what
 * > this step is, why this tool, swap it. The card is about the VALUES. Two lists of the same
 * > thing is what we just removed.
 *
 * It shipped rendering `<Settings>` inside the Step tab **and** a Review tab listing every open
 * value across every step — so a parameter appeared in three places, and the two in here were
 * the ones nobody could act on without scrolling away from the node they were about. Both are
 * gone. What replaced the Review tab is not nothing: **invariant 6's four places are the node,
 * the status line, the settings card and the run sheet** (`impl-inv`), and the rail is not among
 * them. A red left edge on the canvas says which step, the status line says how many, and the
 * card says which values — each answering a different question rather than three answering one.
 *
 * **Two tabs, and the second is the assistant.** `dashboard.md` §6 designed three; the artboard
 * draws two, because the third *was* the review list. The Assistant tab is **door 1**, the
 * prompt door — unwired, and saying so, because the slot is the honest place to record that it
 * opens after #69 and a rail that gains a tab later moves every position a person had learned.
 */
export function Rail({
  steps,
  selected,
  onSwap,
  onOpenSettings,
  onCollapse,
}: {
  steps: AnsweredStep[];
  selected: string | null;
  /** Offer to replace this step. The rail is where a CHOICE is questioned. */
  onSwap?: (id: string) => void;
  /** Open the settings card on the node. The rail points at it; it never draws it. */
  onOpenSettings?: (id: string) => void;
  onCollapse: () => void;
}) {
  const [tab, setTab] = useState<"ask" | "step">("step");
  const step = steps.find((s) => s.id === selected);

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-0.5 px-4 pt-3.5 border-b border-line">
        {(["ask", "step"] as const).map((one) => (
          <button
            key={one}
            data-testid={`tab-${one}`}
            data-active={tab === one || undefined}
            onClick={() => setTab(one)}
            className="font-data text-label uppercase tracking-[.09em] px-[11px] py-1.5
                       bg-transparent border-0 cursor-pointer text-ink-3 hover:text-ink
                       data-[active]:text-ink
                       data-[active]:shadow-[inset_0_-2px_0_var(--link)]"
          >
            {one === "ask" ? "Assistant" : "Step"}
          </button>
        ))}
        <button
          data-testid="collapse-right"
          onClick={onCollapse}
          className="ml-auto text-secondary text-ink-3 bg-transparent border-0 cursor-pointer p-0"
        >
          collapse
        </button>
      </div>

      <div className="flex-1 min-h-0 overflow-auto">
        {tab === "ask" && (
          <div data-testid="ask" className="p-4">
            <p className="text-body text-ink m-0">
              Describe an analysis and Mendel turns it into a <b className="font-normal">goal</b>
              {" "}— have, want, samples, organism — which you correct before anything runs.
            </p>
            <div className="mt-4 rounded-r border border-dashed border-line-2 p-4">
              <p className="text-secondary text-ink-2 m-0">
                {/* **The slot, not the thing.** This is door 1, the prompt door, and it is the
                    one place in the product where free text enters. It is deliberately not
                    wired: AI is not in this plan, and #69 comes first. */}
                Not wired yet. The prompt door is the first of Mendel&rsquo;s three AI points and
                it opens after{" "}
                <a
                  href="https://github.com/comeni-project/Comeni-Labs/issues/69"
                  className="text-pea"
                >
                  #69
                </a>
                .
              </p>
              <p className="text-secondary text-ink-3 mt-3 mb-0">
                What arrives here is an <b className="font-normal text-ink-2">editable goal
                card</b>, never a chat bubble — the model&rsquo;s only job is prose to typed goal,
                and rendering it as conversation would hide the seam that makes the answer
                checkable.
              </p>
            </div>
          </div>
        )}

        {tab === "step" &&
          (step ? (
            <div className="px-[18px] pt-5">
              <div className="settle">
                <div className="font-data text-object font-medium text-ink">{step.process}</div>
                <div className="font-data text-label text-ink-4 pt-1">{step.contract_id}</div>
              </div>

              <div className="settle pt-5" style={{ animationDelay: "40ms" }}>
                <div className="text-label font-data uppercase tracking-[.15em] text-ink-3
                                pb-[9px]">
                  Why this tool
                </div>
                {/* **The resolver's own sentence, not a rewrite of it.** `reason` is what the
                    ladder recorded when it chose this contract; anything composed here would be
                    a second author for a decision that already has one. */}
                <div className="text-secondary text-ink-2 leading-[1.55]">
                  {step.reason || "No reason recorded — this step was drawn by hand."}
                </div>
                <button
                  type="button"
                  data-testid="open-swap"
                  onClick={() => onSwap?.(step.id)}
                  className="mt-3 border border-line-2 px-3 py-2 text-body text-link
                             bg-transparent cursor-pointer lift"
                >
                  Swap for something else
                </button>
              </div>

              <div className="settle pt-6" style={{ animationDelay: "80ms" }}>
                <div className="text-label font-data uppercase tracking-[.15em] text-ink-3
                                pb-[11px]">
                  Values
                </div>
                <Values step={step} />
                <button
                  type="button"
                  data-testid="open-settings"
                  onClick={() => onOpenSettings?.(step.id)}
                  className="font-data text-secondary text-link pt-2.5 bg-transparent border-0
                             cursor-pointer p-0 lift"
                >
                  open on the node ⋯
                </button>
              </div>
            </div>
          ) : (
            <p className="p-4 text-body text-ink-2 m-0">
              Click a step on the canvas to see what it is, why this tool, and what it is set to.
            </p>
          ))}
      </div>
    </div>
  );
}

/** One sentence about a step's parameters, and a dot in the colour of the worst of them.
 *
 * **A count, not a list** — the list is the card's. What this has to get right is the *claim*:
 * `14 settings, all settled` is a strong statement and it must not be made while two of them
 * are open, which is exactly the direction invariant 6 protects.
 */
function Values({ step }: { step: AnsweredStep }) {
  const open = step.settings.filter(isOpen).length;
  const measured = step.settings.filter((one: Answered) => one.tier === 3).length;
  const total = step.settings.length;

  const worst = open > 0 ? "var(--undecided)" : measured > 0 ? "var(--measured)" : "var(--pea)";
  const said =
    total === 0
      ? "no parameters — everything is forced by the module"
      : open > 0
        ? `${total} settings, ${open} need you`
        : measured > 0
          ? `${total} settings, ${measured} measured`
          : `${total} settings, all settled`;

  return (
    <div data-testid="values-line" className="flex items-baseline gap-[9px]">
      <span className="text-[8px] leading-none" style={{ color: worst }}>
        ●
      </span>
      <span className="text-secondary text-ink-2">{said}</span>
    </div>
  );
}
