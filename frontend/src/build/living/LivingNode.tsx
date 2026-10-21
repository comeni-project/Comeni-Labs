import type { PortView } from "../../api/types";
import { HEAD_H, NODE_H, NODE_W, PORT_ROW, portOffset } from "../geometry";
import type { Author } from "./format";
import { processName } from "./format";

export type ReviewState = "reviewed" | "again" | "proposed" | "unknown";

/** The step's values by how they were decided: tiers 1–2 settled, tier 3 measured, tier 4 open. */
export type Counts = { settled: number; measured: number; open: number };

/** One step on the living canvas — the 172×112 symbol every canvas in the product draws.
 *
 * **Geometry from `geometry.ts`, never a literal here.** A wire lands on a port because both read
 * one derivation; the 2026-08-30 walk found `NODE_W` at 232 in the browser and 172 in Python the
 * one time a component kept its own.
 *
 * **Outlined, never striped** (the *Build* and *Question* boards). How each value was decided is
 * the footer's — *1 measured · 13 settled*, each in its meaning's ink — and who chose the step is
 * the step line's, so neither paints the border any more. The step on offer is the selected
 * colour, dashed, and says *Proposed · not added yet*; a step with a value that needs the person
 * carries a red dot.
 */
export function LivingNode({
  id,
  at,
  author,
  ports,
  counts,
  reviewState = "unknown",
  ghost = false,
  selected = false,
  onSelect,
  perItem = false,
  className,
  delay,
  onAnimationEnd,
  onPointerDown,
  onPointerMove,
  onPointerUp,
}: {
  id: string;
  at: { x: number; y: number };
  /** Kept on the element for tests and tools; the node no longer draws it. */
  author: Author;
  ports: PortView[];
  /** **Absent on a ghost and when the frame carries no metadata**: a number a step does not have
   *  yet is the fastest way to make provisional read as committed. */
  counts?: Counts;
  /** Whether a review of this step holds, is asked for again, or is on offer now. */
  reviewState?: ReviewState;
  ghost?: boolean;
  selected?: boolean;
  onSelect?: () => void;
  /** Whether this step runs per item — its ports are drawn as the ribbon's tall marks. */
  perItem?: boolean;
  /** A motion class for a domain event (`motion.ts`), and the callback when it has played. */
  className?: string;
  /** When this step's reveal starts, for Spawn's staged arrival. */
  delay?: number;
  onAnimationEnd?: () => void;
  onPointerDown?: (e: React.PointerEvent) => void;
  onPointerMove?: (e: React.PointerEvent) => void;
  onPointerUp?: (e: React.PointerEvent) => void;
}) {
  const rows = ports.slice(0, Math.floor((NODE_H - HEAD_H - 24) / PORT_ROW));
  const edge = `1px ${ghost ? "dashed" : "solid"} ${selected || ghost ? "var(--now)" : "var(--node-line)"}`;

  return (
    <button
      type="button"
      data-node={id}
      data-testid={`living-node-${id}`}
      data-ghost={ghost || undefined}
      data-author={author}
      aria-pressed={selected}
      aria-label={`${processName(id)}${ghost ? ", proposed" : ""}`}
      onClick={onSelect}
      onAnimationEnd={onAnimationEnd}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
      className={`absolute flex flex-col text-left p-0 cursor-pointer touch-none focus-visible:shadow-[var(--ring)] ${className ?? ""}`}
      style={{
        left: at.x,
        top: at.y,
        width: NODE_W,
        height: NODE_H,
        background: "var(--node)",
        borderRadius: "var(--radius-button)",
        // Four longhands, never `border`: React cannot redraw a shorthand next to its own longhand,
        // and a ghost becoming placed changes them (it warned on every accept).
        borderTop: edge,
        borderRight: edge,
        borderBottom: edge,
        borderLeft: edge,
        boxShadow: selected ? "0 0 0 3px var(--now-soft)" : undefined,
        animationDelay: delay === undefined ? undefined : `${delay}ms`,
      }}
    >
      {/* **Ports, as the collection grammar draws them**: a square for a single value, a tall
          mark where a ribbon lands, and a wide one where a ribbon converges. Positions from
          `portOffset`, the one derivation. */}
      {(["in", "out"] as const).flatMap((side) =>
        ports.filter((p) => p.side === side).map((port, index) => {
          const gather = side === "in" && port.gathers;
          const tall = gather ? 29 : perItem ? 25 : 7;
          const wide = gather ? 12 : 7;
          return (
            <span
              key={`mark-${side}-${port.name}`}
              aria-hidden
              data-port-mark={gather ? "gather" : perItem ? "many" : "one"}
              className="absolute"
              style={{
                left: side === "in" ? -Math.ceil(wide / 2) - 1 : NODE_W - Math.floor(wide / 2) - 2,
                top: portOffset(index) - tall / 2 - 1,
                width: wide,
                height: tall,
                background: selected ? "var(--now)" : "var(--node)",
                border: `1px solid ${selected ? "var(--now)" : "var(--port-line)"}`,
              }}
            />
          );
        }),
      )}
      <span
        className="flex items-center gap-2 px-[10px] w-full shrink-0"
        style={{ height: HEAD_H, borderBottom: "1px solid var(--node-rule)" }}
      >
        <span className="font-data text-[11px] font-semibold text-ink truncate" data-testid={`node-name-${id}`}>
          {processName(id)}
        </span>
        {reviewState === "again" && (
          <span className="ml-auto text-[10.5px] font-semibold text-now-ink whitespace-nowrap">Review again</span>
        )}
        {(counts?.open ?? 0) > 0 && (
          <span aria-hidden data-testid={`node-open-${id}`}
                className={`${reviewState === "again" ? "" : "ml-auto"} w-[8px] h-[8px] rounded-full shrink-0`}
                style={{ background: "var(--needs-you)" }} />
        )}
      </span>
      {/* **No top padding, measured rather than read**: the first row's centre is the header rule
          plus half a row, which is where `portOffset` puts the port marks. */}
      <span className="flex-1 min-h-0 pb-[5px] w-full overflow-hidden">
        {rows.map((port) => (
          <span
            key={`${port.side}:${port.name}`}
            className="flex items-center px-[10px] font-data text-[10px] whitespace-pre"
            style={{ height: PORT_ROW }}
          >
            <span className="text-ink-3">{port.side === "in" ? "< " : "> "}</span>
            <span className={port.side === "in" ? "text-ink truncate" : "text-ink-2 truncate"}>
              {port.type_id}
              {port.states.length > 0 ? `[${port.states.join(", ")}]` : ""}
            </span>
          </span>
        ))}
      </span>
      {(ghost || counts) && (
        <span
          data-testid={`node-footer-${id}`}
          className="h-[24px] flex items-center px-[10px] w-full shrink-0 text-[10.5px] whitespace-pre overflow-hidden"
          style={{ borderTop: "1px solid var(--node-rule)" }}
        >
          {ghost ? (
            <span className="font-semibold text-now-ink">Proposed · not added yet</span>
          ) : counts && (
            <CountWords counts={counts} />
          )}
        </span>
      )}
    </button>
  );
}

/** *1 needs you · 3 measured · 13 settled*, each in its meaning's ink; a zero is not said. */
function CountWords({ counts }: { counts: Counts }) {
  const parts = [
    counts.open > 0 && <span key="open" className="font-semibold text-needs-you-ink">{counts.open} needs you</span>,
    counts.measured > 0 && <span key="measured" className="font-semibold text-measured-ink">{counts.measured} measured</span>,
    counts.settled > 0 && <span key="settled" className="text-ink-2">{counts.settled} settled</span>,
  ].filter(Boolean) as React.ReactElement[];
  return <>{parts.flatMap((part, i) => (i ? [<span key={`dot-${i}`} className="text-ink-3"> · </span>, part] : [part]))}</>;
}
