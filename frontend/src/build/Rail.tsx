import { useState } from "react";

import type { components } from "../api/schema";
import { Settings } from "./Settings";

type Built = components["schemas"]["BuiltPipeline"];

/** **Two tabs, not three.**
 *
 * `dashboard.md` §6 designs a rail of three and the third is *Ask Mendel* — a chat whose reply is
 * an editable goal card. That is **door 1**, the prompt door, and the interface spec §3C says
 * plainly that AI is not in 3C: #69 first, then the tier-4 resolver, both after the builder can
 * show a pipeline it already resolves deterministically. The design is not wrong; it is ahead.
 *
 * **One tab at a time**, which the design arrived at by removing a permanently pinned review
 * strip — two jobs in one column read as clutter, and review became a tab with its count as a
 * badge that hides at zero.
 */
export function Rail({
  data,
  selected,
  onSelect,
  onCollapse,
}: {
  data: Built;
  selected: string | null;
  onSelect: (id: string | null) => void;
  onCollapse: () => void;
}) {
  const [tab, setTab] = useState<"ask" | "step" | "review">("review");
  const step = data.steps.find((s) => s.id === selected);

  const open = data.steps.flatMap((s) =>
    s.settings
      .filter((setting) => setting.tier >= 3)
      .map((setting) => ({ step: s, setting })),
  );

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-1 px-3 py-2 border-b border-line">
        {(["ask", "step", "review"] as const).map((one) => (
          <button
            key={one}
            data-testid={`tab-${one}`}
            data-active={tab === one || undefined}
            onClick={() => setTab(one)}
            className="px-2 py-1 rounded-r bg-transparent border-0 cursor-pointer
                       text-secondary text-ink-3 hover:text-ink
                       data-[active]:text-ink data-[active]:font-semibold
                       data-[active]:shadow-[inset_0_-2px_0_var(--pea)]"
          >
            {one === "ask" ? "Ask" : one === "step" ? "Step" : "Review"}
            {one === "review" && open.length > 0 && (
              // Hidden at zero — `dashboard.md` §6. A badge showing 0 is a badge that has
              // stopped meaning anything.
              <span className="ml-2 font-data text-[var(--measured)]">{open.length}</span>
            )}
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
                    one place in the product where free text enters. It is deliberately not wired:
                    the interface spec says AI is not in 3C, and #69 comes first. The tab exists
                    because the design has three and because a rail that gains a tab later moves
                    everything a person had learned the position of. */}
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
            <Settings step={step} onClose={() => onSelect(null)} />
          ) : (
            <p className="p-4 text-body text-ink-2 m-0">
              Click a step on the canvas to see what it takes, what it gives, and how every
              parameter was settled.
            </p>
          ))}

        {tab === "review" &&
          (open.length === 0 ? (
            <p className="p-4 text-body text-ink-2 m-0">
              Nothing needs checking. Every value was forced by the inputs or is documented
              practice.
            </p>
          ) : (
            <div>
              {/* **Red first, then yellow** — `dashboard.md` §6, and it is the queue's
                  consequence order in a second place rather than a new idea. */}
              {[4, 3].map((tier) =>
                open
                  .filter((row) => row.setting.tier === tier)
                  .map((row) => (
                    <button
                      key={`${row.step.id}.${row.setting.name}`}
                      data-testid="review-row"
                      data-tier={tier}
                      onClick={() => {
                        onSelect(row.step.id);
                        setTab("step");
                      }}
                      className="w-full text-left px-4 py-3 border-b border-line bg-transparent
                                 border-x-0 border-t-0 cursor-pointer hover:bg-surface-2"
                    >
                      <div className="flex items-baseline gap-2">
                        <span
                          className="w-2 h-2 self-center rounded-full shrink-0"
                          style={{
                            background:
                              tier === 4 ? "var(--undecided)" : "var(--measured)",
                          }}
                        />
                        <span className="font-data text-body text-ink">{row.setting.name}</span>
                        <span className="ml-auto font-data text-label text-ink-3">
                          {row.step.process}
                        </span>
                      </div>
                      <div className="text-secondary text-ink-2 mt-1">{row.setting.reason}</div>
                    </button>
                  )),
              )}
            </div>
          ))}
      </div>
    </div>
  );
}
