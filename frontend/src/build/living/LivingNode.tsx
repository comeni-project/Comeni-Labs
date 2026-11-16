import type { PortView } from "../../api/types";
import { HEAD_H, NODE_W, PORT_GAP, heightOf, portOffset } from "../geometry";
import type { Author } from "./format";
import { processName } from "./format";
import { spelledStates } from "../../ui/spelled";

export type ReviewState = "reviewed" | "again" | "proposed" | "unknown";

/** The step's values by how they were decided: tiers 1–2 settled, tier 3 measured, tier 4 open. */
export type Counts = { settled: number; measured: number; open: number; optional?: number; read?: number };

/** One step on the living canvas — the 172×112 symbol every canvas in the product draws.
 *
 * **Geometry from `geometry.ts`, never a literal here.** A wire lands on a port because both read
 * one derivation; the 2026-08-30 walk found `NODE_W` at 232 in the browser and 172 in Python the
 * one time a component kept its own.
 *
 * **Outlined, never striped** (the *Build* and *Question* boards). How each value was decided is
 * the footer's — *1 measured · 13 settled*, each in its meaning's ink. A step with a value that
 * needs the person carries a red dot; one the AI chose and nobody reviewed carries a small *AI*
 * tag beside its name.
 */
export function LivingNode({
  id,
  at,
  author,
  ports,
  counts,
  reviewState = "unknown",
  aiChoice = false,
  selected = false,
  onSelect,
  perItem = false,
  takes,
  samples,
  version,
  does,
  className,
  delay,
  onAnimationEnd,
  onPointerDown,
  onPointerMove,
  onPointerUp,
  onMenu,
  progress,
}: {
  id: string;
  at: { x: number; y: number };
  /** Kept on the element for tests and tools; the node no longer draws it. */
  author: Author;
  ports: PortView[];
  /** **Absent when the frame carries no metadata**: a number a step does not have yet is the
   *  fastest way to make provisional read as committed. */
  counts?: Counts;
  /** Whether a review of this step holds, is asked for again, or is on offer now. */
  reviewState?: ReviewState;
  /** The AI chose this step or one of its values, and nobody has reviewed it as it now is (#463). */
  aiChoice?: boolean;
  selected?: boolean;
  onSelect?: () => void;
  /** Whether this step runs per item — its ports are drawn as the ribbon's tall marks. */
  perItem?: boolean;
  /** The samples this step takes, when each sample's tool is chosen per sample and only some come
   *  here (issue 466); the node says *some samples* and the sentence is its title. */
  takes?: string;
  /** How many samples the analysis keeps: a per-sample step reads ×N, a fan-in port *all N*. */
  samples?: number;
  /** The tool's version, from its contract id. */
  version?: string;
  /** What the step does, in a few words (its role's label): the node's first line. */
  does?: string | null;
  /** A motion class for a domain event (`motion.ts`), and the callback when it has played. */
  className?: string;
  /** When this step's reveal starts, for Spawn's staged arrival. */
  delay?: number;
  onAnimationEnd?: () => void;
  onPointerDown?: (e: React.PointerEvent) => void;
  onPointerMove?: (e: React.PointerEvent) => void;
  onPointerUp?: (e: React.PointerEvent) => void;
  /** Open the step's menu (#499): a right-click, or Shift+F10 and the menu key. */
  onMenu?: () => void;
  /** **On Run**: how far this step has got, drawn in place of the value counts (the board's
   *  bar and *14 of 24 · 2 running*). */
  progress?: StepProgress;
}) {
  // **Every port, each on its own row at its anchor** (#494): input *i* on the left and output
  // *i* on the right of row *i*, where both their marks sit; the node grows to hold them.
  const ins = ports.filter((p) => p.side === "in");
  const outs = ports.filter((p) => p.side === "out");
  const height = heightOf(ports);
  const rows = Array.from({ length: Math.max(ins.length, outs.length) }, (_, i) => [ins[i], outs[i]] as const);
  const edge = `1px solid ${selected ? "var(--now)" : "var(--node-line)"}`;

  return (
    <button
      type="button"
      data-node={id}
      data-testid={`living-node-${id}`}
      data-author={author}
      aria-pressed={selected}
      aria-label={processName(id)}
      onClick={onSelect}
      onContextMenu={onMenu && ((e) => { e.preventDefault(); onMenu(); })}
      onKeyDown={onMenu && ((e) => {
        if (e.key === "ContextMenu" || (e.key === "F10" && e.shiftKey)) { e.preventDefault(); onMenu(); }
      })}
      onAnimationEnd={onAnimationEnd}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
      className={`absolute flex flex-col text-left p-0 cursor-pointer touch-none focus-visible:shadow-[var(--ring)] ${className ?? ""}`}
      style={{
        left: at.x,
        top: at.y,
        width: NODE_W,
        height,
        background: "var(--node)",
        borderRadius: "var(--radius-button)",
        // Four longhands, never `border`: React cannot redraw a shorthand next to its own longhand,
        // and selecting a step changes them.
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
              data-optional={side === "in" && port.optional ? "true" : undefined}
              className="absolute"
              style={{
                left: side === "in" ? -Math.ceil(wide / 2) - 1 : NODE_W - Math.floor(wide / 2) - 2,
                top: portOffset(index) - tall / 2 - 1,
                width: wide,
                height: tall,
                // An optional input (issue 460) is hollow and dashed, as `Port` draws it.
                background: side === "in" && port.optional ? "transparent" : selected ? "var(--now)" : "var(--node)",
                border: `1px ${side === "in" && port.optional ? "dashed" : "solid"} ${selected ? "var(--now)" : "var(--port-line)"}`,
              }}
            />
          );
        }),
      )}
      <span
        className="flex flex-col justify-center gap-[2px] px-[10px] w-full shrink-0"
        style={{ height: HEAD_H, borderBottom: "1px solid var(--node-rule)" }}
      >
       {/* What the step does, then the tool that does it. */}
       <span className="flex items-center gap-2 min-w-0">
        <span className="text-[12.5px] font-semibold text-ink truncate"
              data-testid={does ? undefined : `node-name-${id}`}>{does ?? processName(id)}</span>
        {aiChoice && (
          <span data-testid={`node-ai-${id}`} title="Chosen by the AI and not reviewed yet: open the step to review it"
                className="shrink-0 px-[4px] rounded-control text-[9.5px] font-semibold leading-[15px]"
                style={{ background: "var(--now-soft)", color: "var(--now-ink)" }}>
            AI
          </span>
        )}
        {takes && (
          <span data-testid={`node-branch-${id}`} title={`takes only ${takes}`}
                className="ml-auto text-[10.5px] text-measured-ink whitespace-nowrap">some samples</span>
        )}
        {reviewState === "again" && (
          <span className={`${takes ? "" : "ml-auto"} text-[10.5px] font-semibold text-now-ink whitespace-nowrap`}>Review again</span>
        )}
        {(counts?.open ?? 0) > 0 && (
          <span aria-hidden data-testid={`node-open-${id}`}
                className={`${reviewState === "again" || takes ? "" : "ml-auto"} w-[8px] h-[8px] rounded-full shrink-0`}
                style={{ background: "var(--needs-you)" }} />
        )}
       </span>
       <span className="flex items-center gap-2 min-w-0">
        {/* Without a label, the first line is already the tool's name. */}
        {does && (
          <span className="font-data text-[10.5px] text-ink-2 truncate" data-testid={`node-name-${id}`}>
            {processName(id)}
          </span>
        )}
        {version && <span className="font-data text-[10px] text-ink-3 shrink-0">{version}</span>}
        {perItem && samples !== undefined && (
          <span className="ml-auto font-data text-[10px] font-semibold text-now-ink shrink-0">×{samples}</span>
        )}
       </span>
      </span>
      {rows.map(([input, output], i) => (
        <span key={`row-${i}`} data-port-row
              className="absolute left-0 right-0 flex items-center justify-between gap-2 px-[10px] font-data text-[10px] whitespace-pre"
              style={{ top: portOffset(i) - PORT_GAP / 2, height: PORT_GAP }}>
          <span className="min-w-0 truncate text-ink" title={input ? `${input.type_id}${spelledStates(input.states)}` : undefined}>
            {input && <><span className="text-ink-3">{"< "}</span>{input.name}</>}
            {input?.gathers && samples !== undefined && <span className="text-ink-3"> · <span>all {samples}</span></span>}
            {input?.optional && !input.met && <span className="text-now-ink"> · <span>connect</span></span>}
          </span>
          <span className="min-w-0 truncate text-ink-2 text-right" title={output ? `${output.type_id}${spelledStates(output.states)}` : undefined}>
            {output && <>{output.name}<span className="text-ink-3">{" >"}</span></>}
          </span>
        </span>
      ))}
      {progress && (
        <span
          data-testid={`node-progress-${id}`}
          data-state={progress.state}
          className="absolute left-0 right-0 bottom-0 h-[22px] flex items-center gap-2 px-[10px] text-[10.5px] whitespace-pre overflow-hidden"
          style={{ borderTop: "1px solid var(--node-rule)" }}
        >
          <span aria-hidden className="w-[7px] h-[7px] rounded-full shrink-0" style={{ background: PROGRESS_INK[progress.state] }} />
          <span className={progress.state === "failed" ? "font-semibold text-needs-you-ink" : "text-ink-2"}>{progress.label}</span>
          {progress.of > 1 && (
            <span aria-hidden className="ml-auto flex h-[4px] w-[48px] rounded-full overflow-hidden bg-line-soft shrink-0">
              <span style={{ width: `${(100 * progress.done) / progress.of}%`, background: "var(--done)" }} />
              <span style={{ width: `${(100 * progress.running) / progress.of}%`, background: "var(--now-mid)" }} />
            </span>
          )}
        </span>
      )}
      {counts && !progress && (
        <span
          data-testid={`node-footer-${id}`}
          className="absolute left-0 right-0 bottom-0 h-[22px] flex items-center px-[10px] text-[10.5px] whitespace-pre overflow-hidden"
          style={{ borderTop: "1px solid var(--node-rule)" }}
        >
          <CountWords counts={counts} />
        </span>
      )}
    </button>
  );
}

/** How far a step has got in a run: *done*, *running*, *waiting* or *failed*, with its words. */
export type StepProgress = {
  state: "done" | "running" | "waiting" | "failed";
  done: number;
  running: number;
  of: number;
  label: string;
};

const PROGRESS_INK: Record<StepProgress["state"], string> = {
  done: "var(--done)", running: "var(--now)", waiting: "var(--line-2)", failed: "var(--needs-you)",
};

/** *1 needs you · 3 measured · 1 optional · 13 settled*, each in its meaning's ink; a zero is not said. */
function CountWords({ counts }: { counts: Counts }) {
  const parts = [
    counts.open > 0 && <span key="open" className="font-semibold text-needs-you-ink">{counts.open} needs you</span>,
    counts.measured > 0 && <span key="measured" className="font-semibold text-measured-ink">{counts.measured} measured</span>,
    (counts.read ?? 0) > 0 && <span key="read" className="text-ink-2">{counts.read} read by AI</span>,
    (counts.optional ?? 0) > 0 && <span key="optional" className="text-ink-2">{counts.optional} optional</span>,
    counts.settled > 0 && <span key="settled" className="text-ink-2">{counts.settled} settled</span>,
  ].filter(Boolean) as React.ReactElement[];
  return <>{parts.flatMap((part, i) => (i ? [<span key={`dot-${i}`} className="text-ink-3"> · </span>, part] : [part]))}</>;
}
