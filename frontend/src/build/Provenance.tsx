import type { components } from "../api/schema";

type Built = components["schemas"]["BuiltPipeline"];

/** What each tier is called, in the words a person would use.
 *
 * **Not "tier 3".** `dashboard.md` §7's copy rule and `CLAUDE.md`'s own table: a tier is a
 * mechanism and a reader needs the consequence. *Check the premise* is what yellow means.
 */
const BAND: Record<string, { name: string; fill: string }> = {
  "1": { name: "Forced by inputs", fill: "bg-pea" },
  "2": { name: "Standard practice", fill: "bg-pea opacity-[.42]" },
  "3": { name: "Check the premise", fill: "bg-[var(--measured)]" },
  "4": { name: "Needs your decision", fill: "bg-[var(--undecided)]" },
};

const ORDER = ["1", "2", "3", "4"];

/** How Mendel decided — **the product thesis compressed into one element** (`dashboard.md` §4).
 *
 * A 10px strip segmented proportionally by tier, headlined with the share settled *without
 * judgement*. Clicking a band isolates those steps.
 *
 * **Tier 3 is not in that share, and that is the whole honesty of the bar.** A rule matched
 * measured data, which is the machinery working — and the premise behind the measurement still
 * needs a person. Counting it as settled would turn the one element that carries the product's
 * claim into the one element that overstates it.
 */
export function Provenance({
  data,
  isolated,
  onIsolate,
}: {
  data: Built;
  isolated: string | null;
  onIsolate: (tier: string | null) => void;
}) {
  const total = Object.values(data.provenance).reduce((a, b) => a + b, 0);
  const bands = ORDER.filter((tier) => (data.provenance[tier] ?? 0) > 0);
  const undecided = data.needs_review.length;

  return (
    <div className="px-6 pt-3 pb-4 bg-surface border-b border-line">
      <div className="flex items-baseline gap-3">
        <h2 className="m-0 text-label uppercase tracking-[.13em] font-semibold text-ink-3">
          How Mendel decided
        </h2>
        <span data-testid="settled" className="text-body text-ink">
          <b className="font-data">{Math.round(data.settled_share * 100)}%</b> settled without
          judgement
        </span>
        {undecided > 0 && (
          <span data-testid="undecided" className="text-body text-[var(--undecided)]">
            · <b className="font-data">{undecided}</b> needs your decision
          </span>
        )}
        <span className="ml-auto text-secondary text-ink-3">
          {isolated ? "Click again to show every step" : "Click a band to isolate those steps"}
        </span>
      </div>

      <div
        role="group"
        aria-label="Decisions by how they were made"
        className="flex gap-[2px] h-[10px] mt-2"
      >
        {bands.map((tier) => (
          <button
            key={tier}
            data-testid="band"
            data-tier={tier}
            aria-label={`${data.provenance[tier]} ${BAND[tier].name}`}
            title={`${data.provenance[tier]} of ${total} — ${BAND[tier].name}`}
            onClick={() => onIsolate(isolated === tier ? null : tier)}
            style={{ flexGrow: data.provenance[tier] }}
            className={`h-full rounded-[1px] border-0 p-0 cursor-pointer transition-opacity
                        ${BAND[tier].fill}
                        ${isolated && isolated !== tier ? "opacity-25" : ""}`}
          />
        ))}
      </div>

      <div className="flex flex-wrap gap-x-5 gap-y-1 mt-2 text-secondary text-ink-2">
        {bands.map((tier) => (
          <span key={tier} className="flex items-baseline gap-2">
            <span className={`w-2 h-2 self-center rounded-[1px] ${BAND[tier].fill}`} />
            <b className="font-data">{data.provenance[tier]}</b> {BAND[tier].name}
          </span>
        ))}
      </div>
    </div>
  );
}
