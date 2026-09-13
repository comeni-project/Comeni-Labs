import type { Point } from "../geometry";
import { elbow, path } from "../geometry";

/** How many times a channel delivers, drawn **on the wire** — never as copies of a node.
 *
 * Three shapes, from the design canvas's collection grammar (`LivingCollect`):
 *
 * - **one** — a run-scoped value: one stroke, *read once per task*;
 * - **many** — a per-item channel: a three-strand ribbon, *once per item*;
 * - **gather** — the ribbon converges into a wide port: *collect all*.
 *
 * **Three strands whether N is 12 or 12,000.** The count lives on the source, never on the wire,
 * and it is only ever a number when a measurement supplied one — otherwise `×N items`. Nothing
 * here can draw a filename: the props hold a type, a scope and a count, and no field could carry
 * a path if somebody tried.
 */

export type Flow = "one" | "many" | "gather";

/** What a flow says on the wire at rest: **the behaviour, never the count.** The count is on the
 *  source box. The first render put the whole sentence here and a 90px gutter clipped it to
 *  `lue · read once pe` — the design note had already said the count belongs on the source. */
export function flowTag(flow: Flow): string {
  return flow === "one" ? "once per task" : flow === "gather" ? "collect all" : "once per item";
}

/** What a flow says in full, when either end is selected. */
export function flowLabel(flow: Flow, count: number | null): string {
  const many = count === null ? "×N items" : `×${count} samples`;
  if (flow === "one") return "one value · read once per task";
  if (flow === "gather") return `${count === null ? "×N" : `×${count}`} · collect all`;
  return `${many} · once per item`;
}

/** The count as the source box and a step's footer say it. */
export function multiplicity(count: number | null): string {
  return count === null ? "×N items" : `×${count} samples`;
}

const STRAND = 3; // px between strands

export function Flowline({
  from,
  to,
  flow,
  label,
  className,
  onDrawn,
  dashed = false,
  testId,
}: {
  from: Point;
  to: Point;
  flow: Flow;
  label?: string;
  className?: string;
  onDrawn?: () => void;
  dashed?: boolean;
  testId?: string;
}) {
  const strands = flow === "one" ? [0] : [-STRAND, 0, STRAND];
  const runway = 72; // the design's convergence runway, before a gathering port
  const mid = { x: Math.round((from.x + to.x) / 2), y: from.y };

  return (
    <g data-testid={testId} data-flow={flow}>
      {strands.map((offset, i) => {
        const start = { x: from.x, y: from.y + offset };
        // A gathering ribbon runs parallel to the runway, then every strand meets at one port.
        const points =
          flow === "gather"
            ? (() => {
                const runwayAt = { x: Math.max(start.x, to.x - runway), y: start.y };
                return [start, ...elbow(runwayAt, to)];
              })()
            : elbow(start, { x: to.x, y: to.y + offset });
        return (
          <path
            key={i}
            data-strand={i}
            d={path(points)}
            pathLength={className ? 1 : undefined}
            fill="none"
            stroke="var(--port-line)"
            strokeWidth={flow === "one" ? 1.2 : 1}
            strokeDasharray={dashed ? "4 4" : undefined}
            className={className}
            onAnimationEnd={i === strands.length - 1 ? onDrawn : undefined}
          />
        );
      })}
      {/* Only where it fits. Two adjacent steps leave 52px between them, and a tag drawn there was
          clipped to `ollect al` — a clipped word is worse than none; the full sentence is on
          selection and the count is on the source. */}
      {label && to.x - from.x >= label.length * 5.4 + 16 && (
        <text
          x={mid.x}
          y={mid.y - 10}
          textAnchor="middle"
          className="font-data"
          style={{ fontSize: 8.5, fill: "var(--ink-3)" }}
        >
          {label}
        </text>
      )}
    </g>
  );
}

export const SOURCE_W = 120;
export const SOURCE_H = 80;

/** An input where it enters the pipeline: a type, a scope, and a count only if one was measured. */
export function SourceNode({
  at,
  name,
  typeId,
  states,
  scope,
  count,
}: {
  at: Point;
  name: string;
  typeId: string;
  states: string[];
  scope: "run" | "sample";
  count: number | null;
}) {
  return (
    <div
      data-testid={`living-source-${name}`}
      className="absolute flex flex-col justify-center px-[10px]"
      style={{
        left: at.x,
        top: at.y,
        width: SOURCE_W,
        height: SOURCE_H,
        background: "var(--paper-2)",
        border: "1px dashed var(--line-2)",
        borderLeft: "3px solid var(--link)",
      }}
    >
      <span className="font-data text-[8px] tracking-[.15em] uppercase text-link">input</span>
      <span className="font-data text-[11px] text-ink">{name}</span>
      <span className="font-data text-[8.5px] text-ink-3 truncate">
        {typeId}
        {states.length > 0 ? `[${states.join(", ")}]` : ""}
      </span>
      {scope === "sample" && (
        <span className="font-data text-[8.5px] text-link">{multiplicity(count)}</span>
      )}
    </div>
  );
}
