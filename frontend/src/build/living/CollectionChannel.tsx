import type { Point } from "../geometry";
import { elbow, path } from "../geometry";
import { spelledStates } from "../../ui/spelled";
import { useTypeNames } from "./useTypeNames";

/** How many times a channel delivers, drawn **on the wire** — never as copies of a node.
 *
 * Three shapes, from the design canvas's collection grammar (`LivingCollect`):
 *
 * - **one** — a value for the whole study: one stroke, *read once per task*;
 * - **many** — a per-item channel: a three-strand ribbon, *once per item*;
 * - **gather** — the ribbon converges into a wide port: *collect all*.
 *
 * **Three strands whether N is 12 or 12,000.** The count lives on the source, never on the wire,
 * and it is only ever a number when a measurement supplied one — otherwise `×N items`. Nothing
 * here can draw a filename: the props hold a type, a grain and a count, and no field could carry
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
  pulse = false,
  pulseColour = "var(--path)",
  lit = false,
}: {
  from: Point;
  to: Point;
  flow: Flow;
  label?: string;
  className?: string;
  onDrawn?: () => void;
  dashed?: boolean;
  testId?: string;
  /** **Data moving along it**: dots that travel the wire, from its source to where it goes. For
   *  a lit path (Run → Outputs) now, and any canvas that wants to say "this way" later; still for
   *  anyone who asks the system for less motion. */
  pulse?: boolean;
  /** Live execution uses the running colour; output tracing keeps the path colour. */
  pulseColour?: string;
  /** **On the lit path**: drawn in the path colour (not a run state's), a little heavier, so the
   *  way reads even between pulses. */
  lit?: boolean;
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
            stroke={lit ? "var(--path)" : dashed ? "var(--now)" : "var(--port-line)"}
            strokeWidth={lit ? (flow === "one" ? 2 : 1.6) : flow === "one" ? 1.2 : 1}
            strokeDasharray={dashed ? "5 4" : undefined}
            className={className}
            onAnimationEnd={i === strands.length - 1 ? onDrawn : undefined}
          />
        );
      })}
      {pulse && (() => {
        const route = flow === "gather" ? [from, ...elbow({ x: Math.max(from.x, to.x - runway), y: from.y }, to)] : elbow(from, to);
        return <Pulses d={path(route)} length={lengthOf(route)} colour={pulseColour} />;
      })()}
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

/** How fast pulses move, and how far apart: the same on every wire, so a long wire is not
 *  faster than a short one (which would look like it meant something, walk 2026-11-17). */
export const PULSE_SPEED = 60; // px a second
export const PULSE_GAP = 70; // px between dots

/** Dots travelling a path at one speed, evenly apart: where data went. **Seeded**: each starts
 *  part-way through its trip (a negative begin), so a long wire shows its dots at once rather
 *  than looking empty until the first arrives. Hidden under reduced motion. `length` is the path's length in px, which sets how long a trip takes and how many. */
export function Pulses({ d, length, colour = "var(--path)" }: { d: string; length: number; colour?: string }) {
  const seconds = Math.max(length, 1) / PULSE_SPEED;
  const dots = Math.max(1, Math.round(length / PULSE_GAP));
  return (
    <g className="motion-reduce:hidden" aria-hidden="true">
      {Array.from({ length: dots }, (_, n) => (
        <circle key={n} data-pulse data-testid="pulse-dot" r={3} fill={colour} opacity={0}>
          <animateMotion dur={`${seconds}s`} begin={`${-(n * seconds) / dots}s`} repeatCount="indefinite"
                         path={d} calcMode="linear" keyPoints="0;1" keyTimes="0;1" />
          <animate attributeName="opacity" values="0;1;1;0" keyTimes="0;0.05;0.95;1" dur={`${seconds}s`}
                   begin={`${-(n * seconds) / dots}s`} repeatCount="indefinite" />
        </circle>
      ))}
    </g>
  );
}

/** A polyline's length: what a pulse travels. */
export function lengthOf(points: Point[]): number {
  return points.slice(1).reduce((sum, p, i) => sum + Math.hypot(p.x - points[i].x, p.y - points[i].y), 0);
}

export const SOURCE_W = 124;
export const SOURCE_H = 40;

/** A type's name as a chip says it: *Genome*, *Gene annotation*, *Sequencing reads* — the
 *  vocabulary's name without its format in brackets or a leading *reference*. */
export function chipName(name: string): string {
  const bare = name.replace(/\s*\(.*?\)\s*/g, " ").replace(/^reference\s+/i, "").trim();
  return bare ? bare[0].toUpperCase() + bare.slice(1) : name;
}

/** **An input, as the board draws it** (#511): a dashed chip with what it is and what answers it —
 *  the file Data gave it, or how many samples. A per-sample input is a stack. */
export function SourceNode({
  at,
  name,
  typeId,
  states,
  grain,
  count,
  given,
  drag,
}: {
  at: Point;
  name: string;
  typeId: string;
  states: string[];
  grain: "study" | "sample";
  count: number | null;
  /** The file Data answers it with, when Data has one (a reference's name). */
  given?: string;
  /** Pointer handlers that move it on its own (walk 2026-11-17); absent, it stays put. */
  drag?: React.HTMLAttributes<HTMLDivElement>;
}) {
  const typeName = useTypeNames();
  const what = chipName(typeName(typeId));
  const detail = given ?? (grain === "sample" ? (count === null ? "samples" : `${count} samples`) : "not given yet");
  return (
    <div
      data-testid={`living-source-${name}`}
      title={`${typeName(typeId)}${spelledStates(states)} · params.${name}`}
      data-chip=""
      {...drag}
      className={`absolute box-border flex flex-col justify-center gap-[1px] px-[10px] ${drag ? "cursor-grab touch-none active:cursor-grabbing" : ""}`}
      style={{
        left: at.x,
        top: at.y,
        width: SOURCE_W,
        height: SOURCE_H,
        borderRadius: "var(--radius-control)",
        background: "var(--now-soft)",
        border: "1px dashed var(--now-line)",
        boxShadow: grain === "sample" ? "4px 4px 0 -1px var(--surface), 4px 4px 0 0 var(--now-line)" : undefined,
      }}
    >
      <span className="text-[12px] font-semibold text-now-ink truncate">{what}</span>
      <span className={`font-data text-[10.5px] truncate ${given || grain === "sample" ? "text-now-ink" : "text-ink-3"}`}>{detail}</span>
    </div>
  );
}

/** **A result, as the board draws it**: a green chip after a step nothing else reads, with what it
 *  is and how much of it there is (*24 tables*, or on Run *14 of 24*). */
export function ResultNode({ at, name, detail, testId, drag }: {
  at: Point; name: string; detail: string; testId: string;
  /** Pointer handlers that move it on its own; absent, the pointer passes through it. */
  drag?: React.HTMLAttributes<HTMLDivElement>;
}) {
  return (
    <div data-testid={testId} data-chip="" {...drag}
         className={`absolute box-border flex flex-col justify-center gap-[1px] px-[10px] ${drag ? "cursor-grab touch-none active:cursor-grabbing" : "pointer-events-none"}`}
         style={{ left: at.x, top: at.y, width: SOURCE_W, height: SOURCE_H, borderRadius: "var(--radius-control)",
                  background: "var(--done-soft)", border: "1px solid var(--done-line)" }}>
      <span className="text-[12px] font-semibold text-done-ink truncate">{name}</span>
      <span className="font-data text-[10.5px] text-done-ink truncate">{detail}</span>
    </div>
  );
}
