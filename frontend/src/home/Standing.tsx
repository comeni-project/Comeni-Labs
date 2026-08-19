import type { components } from "../api/schema";

type Standing = components["schemas"]["Standing"];

/** How well-founded a thing is, drawn rather than labelled.
 *
 * **This is the product's own governing idea, reused.** `dashboard.md` §1: *certainty is a
 * property of how a thing is drawn, not a label attached to it* — the canvas draws a tier-3
 * node's rail dashed and a tier-4 node's gapped, and wires inherit their source's treatment so
 * uncertainty propagates visually down the graph.
 *
 * The same three strokes say the same thing about the registry itself, so a visitor who later
 * opens a pipeline has already been taught to read them. That is the strongest justification a
 * signature element can have, and it is why this is not a chart.
 *
 * **No legend.** `forge-review.md` cut the builder's five port shapes because *"an encoding that
 * needs its legend on screen at all times is a lookup with extra steps"*. Each row says in words
 * what it is; the stroke adds how sure we are, and a reader who ignores it loses nothing.
 */
type Ground = "checked" | "unchecked" | "broken" | "measured" | "undrawn";

const STROKE: Record<Ground, string> = {
  // solid: read against its module and agreeing.
  checked: "border-solid border-[var(--pea)]",
  // dashed, muted: nothing could re-read it. A contract nothing checks is not a contract
  // that agrees — the distinction phase 4 shipped wrong once and corrected.
  unchecked: "border-dashed border-[var(--ink-3)]",
  // gapped, coral: it was true and now is not. Coral rather than red, because an undecided
  // thing is not a build failure — `--fault` is kept separate for exactly that reason.
  broken: "border-dotted border-[var(--undecided)]",
  // dashed, amber: a rule is only as good as the measurement behind it. Tier 3 is yellow on
  // the canvas for the same reason: the machinery worked, check the premise.
  measured: "border-dashed border-[var(--measured)]",
  // no rule at all: the line is not drawn yet.
  undrawn: "border-none",
};

function Row({
  count,
  label,
  ground,
  note,
}: {
  count: number;
  label: string;
  ground: Ground;
  note?: string;
}) {
  return (
    <div className="flex items-baseline gap-5 py-2.5 border-b border-line last:border-b-0">
      <span
        aria-hidden
        data-testid="ground"
        className={`w-12 shrink-0 self-center border-t-2 ${STROKE[ground]}`}
        data-ground={ground}
      />
      <b className="font-data text-object text-ink tabular-nums w-9 shrink-0 text-right">
        {count}
      </b>
      <span className="text-body text-ink-2">{label}</span>
      {note && (
        <span className="ml-auto shrink-0 text-label text-ink-3 uppercase tracking-[.1em]">
          {note}
        </span>
      )}
    </div>
  );
}

/** What the system **knows** — not what state it is in.
 *
 * **Narrowed in Plan 3D phase 6, and the narrowing is the point.** This used to say
 * *10 agree with their module · 2 have no source that can re-read them · 0 no longer do* — which
 * is now exactly what the Tools board says, better, on the screen where you can act on it. Two
 * places answering one question is how a number goes stale in one of them, and the front door
 * would have been the one nobody corrected.
 *
 * What survives is the half no working screen answers: **how much vocabulary exists**. A
 * stranger's question is *what does this thing know*, and a curator's is *is anything wrong* —
 * the board owns the second now, so this owns the first cleanly instead of half of each.
 *
 * **The undrafted row went too**, and for a different reason: it said the same number as *What
 * needs you* two blocks above, on one screen. Between an inventory line and a call to act on the
 * same fact, the call wins.
 *
 * `undrawn` therefore has no row today. **The strokes serve the content, not the reverse** —
 * keeping a row alive to exhibit a stroke would be the legend problem `forge-review.md` cut the
 * port shapes over.
 */
export function StandingBlock({ standing }: { standing: Standing }) {
  return (
    <div>
      <Row
        count={standing.contracts}
        label="tools have a contract saying what they take and give"
        ground="checked"
      />
      <Row
        count={standing.types}
        label="declared types, across a closed vocabulary"
        ground="checked"
        note="a contract naming an undeclared one will not load"
      />
      <Row
        count={standing.measurements}
        label="measurements a rule may read about the data"
        ground="measured"
      />
      <Row
        count={standing.rules}
        label={standing.rules === 1 ? "rule reads them" : "rules read them"}
        ground="measured"
        note="the design expects many"
      />
    </div>
  );
}
