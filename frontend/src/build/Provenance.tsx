import type { components } from "../api/schema";
import { useTiers } from "./useTiers";

type Built = components["schemas"]["BuiltPipeline"];

/** The fill for each tier, by **token name from the API** rather than by a table here.
 *
 * The names come over the wire; only the mapping from a token name to a Tailwind class stays,
 * because that is a rendering detail and `tokens.css` is where the palette lives.
 */
const FILL: Record<string, string> = {
  pea: "bg-pea",
  "pea-soft": "bg-pea opacity-[.42]",
  measured: "bg-[var(--measured)]",
  undecided: "bg-[var(--undecided)]",
  "line-2": "bg-line-2",
};

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
  const words = useTiers();
  const total = Object.values(data.provenance).reduce((a, b) => a + b, 0);
  const bands = words.tiers
    .map((card) => String(card.tier))
    .filter((tier) => (data.provenance[tier] ?? 0) > 0);
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
        {/* **"steps", because the band beside this counts DECISIONS.** `needs_review` is a
            list of nodes and `provenance` is a tally of decisions, so a pipeline reads
            `6 Undecided` on the bar and `5 steps` here — both true, six tier-4 decisions
            spread over five steps. Unlabelled they look like the same number disagreeing
            with itself, which is how this was first reported as a defect. */}
        {undecided > 0 && (
          <span data-testid="undecided" className="text-body text-[var(--undecided)]">
            · <b className="font-data">{undecided}</b>{" "}
            {undecided === 1 ? "step needs" : "steps need"} your decision
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
            aria-label={`${data.provenance[tier]} ${words.name(Number(tier))}`}
            title={`${data.provenance[tier]} of ${total} — ${words.what(Number(tier))}`}
            onClick={() => onIsolate(isolated === tier ? null : tier)}
            style={{ flexGrow: data.provenance[tier] }}
            className={`h-full rounded-[1px] border-0 p-0 cursor-pointer transition-opacity
                        ${FILL[words.colour(Number(tier))] ?? ""}
                        ${isolated && isolated !== tier ? "opacity-25" : ""}`}
          />
        ))}
      </div>

      <div className="flex flex-wrap gap-x-5 gap-y-1 mt-2 text-secondary text-ink-2">
        {bands.map((tier) => (
          <span key={tier} className="flex items-baseline gap-2">
            <span className={`w-2 h-2 self-center rounded-[1px] ${FILL[words.colour(Number(tier))] ?? ""}`} />
            <b className="font-data">{data.provenance[tier]}</b> {words.name(Number(tier))}
          </span>
        ))}
      </div>
    </div>
  );
}
