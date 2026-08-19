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
    <div className="flex items-baseline gap-4 py-2">
      <span
        aria-hidden
        data-testid="ground"
        className={`w-10 shrink-0 self-center border-t-2 ${STROKE[ground]}`}
        data-ground={ground}
      />
      <b className="font-data text-body text-ink tabular-nums">{count}</b>
      <span className="text-body text-ink-2">{label}</span>
      {note && <span className="ml-auto text-label text-ink-3">{note}</span>}
    </div>
  );
}

/** What the registry holds — the half a dashboard usually omits.
 *
 * Not what it needs: that is the other half of the page. This is what makes a front door a
 * place rather than an inbox.
 */
export function StandingBlock({ standing }: { standing: Standing }) {
  return (
    <div>
      <Row
        count={standing.matching}
        label="contracts agree with the module they describe"
        ground="checked"
      />
      {standing.drifted > 0 && (
        <Row
          count={standing.drifted}
          label="no longer do"
          ground="broken"
          note="was true once"
        />
      )}
      {standing.unverifiable > 0 && (
        <Row
          count={standing.unverifiable}
          label="have no source that can re-read them"
          ground="unchecked"
          note="not checked, not agreeing"
        />
      )}
      <Row
        count={standing.types}
        label="declared types, across a closed vocabulary"
        ground="checked"
      />
      <Row
        count={standing.rules}
        label={standing.rules === 1 ? "rule reads measured data" : "rules read measured data"}
        ground="measured"
        note="the design expects many"
      />
      <Row
        count={standing.undrafted}
        label="tools a source can read that nobody has drafted"
        ground="undrawn"
      />
    </div>
  );
}
