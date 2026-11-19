import type { PortView } from "../../api/types";
import { MEASURE_H, MEASURE_W, NODE_W, PORT_GAP, heightOf, portOffset } from "../geometry";
import type { Author } from "./format";
import { processName } from "./format";
import { spelledStates } from "../../ui/spelled";

export type ReviewState = "reviewed" | "again" | "proposed" | "unknown";

/** The step's values by how they were decided: tiers 1–2 settled, tier 3 measured, tier 4 open. */
export type Counts = { settled: number; measured: number; open: number; optional?: number; read?: number };

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

/** An output's triangle: its base on the card's edge, its tip `OUT_W - 1` beyond it, where the wire
 *  leaves. */
export const OUT_W = 8;
export const OUT_H = 10;

/** The row a measured value takes under the ports (`sa_index_nbases 8`), and Run's progress row. */
export const SET_ROW = 26;
export const PROGRESS_ROW = 22;

/** The row the *+N optional* mark takes under the ports. */
export const MORE_ROW = 16;

/** Whether an optional input is in use: connected, or switched on for every run or some. */
const inUse = (p: PortView) => p.met || p.state === "optional" || p.state === "required";

/** **The ports a card draws** (#511): every required input, the optional ones in use, and every
 *  output except those only an unused optional input would make. A tool with fifteen optional
 *  inputs still draws as the few it uses; the rest are one *+N optional* mark. */
export function shownPorts(ports: PortView[]): PortView[] {
  const unused = ports.filter((p) => p.side === "in" && p.optional && !inUse(p));
  const unmade = new Set(unused.flatMap((p) => p.adds ?? []));
  return ports.filter((p) => (p.side === "in" ? !(p.optional && !inUse(p)) : !unmade.has(p.name)));
}

/** How many optional inputs a card folds into its *+N optional* mark. */
export function foldedInputs(ports: PortView[]): number {
  return ports.filter((p) => p.side === "in" && p.optional && !inUse(p)).length;
}

/** A step's drawn height: its shown ports, then the *+N optional* row, a measured value's row and
 *  Run's progress row. */
export function cardHeight(ports: PortView[], { measures = false, setRow = false, progress = false, more = false } = {}): number {
  if (measures) return MEASURE_H;
  return heightOf(shownPorts(ports)) + (more ? MORE_ROW : 0) + (setRow ? SET_ROW : 0) + (progress ? PROGRESS_ROW : 0);
}

/** Where a port sits on a card: on the spine and below for a step, the middle of a measuring pill. */
export function anchorOf(measures: boolean, index: number): number {
  return measures ? Math.round(MEASURE_H / 2) : portOffset(index);
}

/** One step on the canvas, as the board draws it (#511, `Build.dc.html`): a compact card with what
 *  the step does, its tool and version, its ports as dots on the edges, and its marks.
 *
 * **Geometry from `geometry.ts`, never a literal here.** A wire lands on a port because both read
 * one derivation.
 *
 * - A per-sample step is a stack of cards with *×N*; a measuring step is a small pill in the
 *   measured colour, hung under the step it measures.
 * - A value measured from the data shows as one row under the ports (`sa_index_nbases 8`).
 * - *AI* and *N open* are tags on the top edge; nothing is striped or filled for its source.
 * - Port names show when the rail's *Input and output names* is on and a side has more than one.
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
  tool,
  does,
  measures = false,
  setRow,
  showTool = true,
  showPorts = true,
  className,
  delay,
  onAnimationEnd,
  onPointerDown,
  onPointerMove,
  onPointerUp,
  onMenu,
  progress,
  running = false,
  onHover,
  broken = [],
}: {
  id: string;
  at: { x: number; y: number };
  /** Kept on the element for tests and tools; the card does not draw it. */
  author: Author;
  ports: PortView[];
  counts?: Counts;
  reviewState?: ReviewState;
  /** The AI chose this step or one of its values, and nobody has reviewed it as it now is (#463). */
  aiChoice?: boolean;
  selected?: boolean;
  onSelect?: () => void;
  /** Whether this step runs per item: a stack of cards, and *×N*. */
  perItem?: boolean;
  /** The samples this step takes, when only some come here (issue 466). */
  takes?: string;
  /** How many samples the analysis keeps: a per-sample step reads ×N. */
  samples?: number;
  /** The tool's version, from its contract id. */
  version?: string;
  /** The tool, in words (`star align`), shown before the version. */
  tool?: string;
  /** What the step does, in a few words (its role's label): the card's first line. */
  does?: string | null;
  /** A measuring step (#517): drawn as a pill. */
  measures?: boolean;
  /** A value measured from the data and the setting it set (`sa_index_nbases 8`). */
  setRow?: string;
  /** The rail's *On the steps* switches. */
  showTool?: boolean;
  showPorts?: boolean;
  className?: string;
  delay?: number;
  onAnimationEnd?: () => void;
  onPointerDown?: (e: React.PointerEvent) => void;
  onPointerMove?: (e: React.PointerEvent) => void;
  onPointerUp?: (e: React.PointerEvent) => void;
  /** Open the step's menu (#499): a right-click, or Shift+F10 and the menu key. */
  onMenu?: () => void;
  /** **On Run**: how far this step has got, in a row under the ports. */
  progress?: StepProgress;
  /** A live task, rather than progress retained from an ended run. */
  running?: boolean;
  /** The pointer came onto the card, or left it: the canvas shows the step's details beside it. */
  onHover?: (on: boolean) => void;
  /** The tool's rules this setup breaks, in a few words each (*needs fasta*): red tags. */
  broken?: string[];
}) {
  const shown = shownPorts(ports);
  const folded = foldedInputs(ports);
  const ins = shown.filter((p) => p.side === "in");
  const outs = shown.filter((p) => p.side === "out");
  const rows = Math.max(1, ins.length, outs.length);
  const height = cardHeight(ports, { measures, setRow: !!setRow, progress: !!progress, more: folded > 0 && !measures });
  const width = measures ? MEASURE_W : NODE_W;
  const labelled = showPorts && !measures && (ins.length > 1 || outs.length > 1);
  const edge = selected ? "var(--now)" : measures ? "var(--measured)" : "var(--line-2)";
  // A measuring step is named for what it measures (*Genome length*), from its output.
  const measured = measures ? outs[0]?.name.replaceAll("_", " ") : undefined;
  const name = measured ? measured[0].toUpperCase() + measured.slice(1) : does ?? processName(id);
  const toolLine = [tool, version].filter(Boolean).join(" ");
  const tags = [
    ...broken.map((words, i) => ({ key: `broken-${i}`, words, testId: `node-rule-${id}-${i}`, title: words,
                                   style: { color: "var(--needs-you-ink)", background: "var(--needs-you-soft)", borderColor: "var(--needs-you-line)" } })),
    aiChoice && { key: "ai", words: "AI", testId: `node-ai-${id}`, title: "Chosen by the AI and not reviewed yet: open the step to review it",
                  style: { color: "var(--ai)", background: "var(--ai-soft)", borderColor: "var(--ai-line)" } },
    (counts?.open ?? 0) > 0 && { key: "open", words: `${counts!.open} open`, testId: `node-open-${id}`, title: "A value here needs you",
                                 style: { color: "var(--needs-you-ink)", background: "var(--needs-you-soft)", borderColor: "var(--needs-you-line)" } },
    reviewState === "again" && { key: "again", words: "Review again", testId: `node-again-${id}`, title: "Changed since it was reviewed",
                                 style: { color: "var(--now-ink)", background: "var(--now-soft)", borderColor: "var(--now-line)" } },
    takes && { key: "takes", words: "some samples", testId: `node-branch-${id}`, title: `takes only ${takes}`,
               style: { color: "var(--measured-ink)", background: "var(--measured-soft)", borderColor: "var(--measured-line)" } },
  ].filter(Boolean) as { key: string; words: string; testId: string; title: string; style: React.CSSProperties }[];

  return (
    <button
      type="button"
      data-node={id}
      data-testid={`living-node-${id}`}
      data-author={author}
      data-measures={measures ? "true" : undefined}
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
      onPointerEnter={onHover && (() => onHover(true))}
      onPointerLeave={onHover && (() => onHover(false))}
      onFocus={onHover && (() => onHover(true))}
      onBlur={onHover && (() => onHover(false))}
      className={`absolute block text-left p-0 cursor-pointer touch-none focus-visible:shadow-[var(--ring)] ${className ?? ""}`}
      style={{
        left: at.x,
        top: at.y,
        width,
        height,
        background: measures ? "var(--measured-soft)" : "var(--surface)",
        borderRadius: measures ? "calc(var(--radius-panel) * 2)" : "var(--radius-button)",
        // Four longhands, never `border`: React cannot redraw a shorthand next to its own longhand.
        borderTop: `1px solid ${edge}`,
        borderRight: `1px solid ${edge}`,
        borderBottom: `1px solid ${edge}`,
        borderLeft: `1px solid ${edge}`,
        boxShadow: [
          perItem && !measures && "4px 4px 0 -1px var(--surface), 4px 4px 0 0 var(--line-2), 8px 8px 0 -1px var(--surface), 8px 8px 0 0 var(--line-2)",
          selected && "0 0 0 3px var(--now-soft)",
        ].filter(Boolean).join(", ") || undefined,
        animationDelay: delay === undefined ? undefined : `${delay}ms`,
      }}
    >
      <span className="absolute flex flex-col gap-[2px] min-w-0"
            style={measures ? { left: 14, right: 14, top: 0, bottom: 0, justifyContent: "center" } : { left: 11, right: 11, top: 8 }}>
        <span className={`truncate ${measures ? "text-[12px] font-semibold text-measured-ink" : "text-[13px] font-semibold text-ink"}`}
              data-testid={`node-name-${id}`}>{name}</span>
        {/* A measuring pill says only what it measures; its tool is in the hover card. */}
        {showTool && toolLine && !measures && (
          <span className={`font-data text-[10.5px] truncate ${measures ? "text-measured-ink" : "text-ink-3"}`}
                data-testid={`node-tool-${id}`}>{toolLine}</span>
        )}
      </span>
      {/* **Ports, as dots on the edges** at `anchorOf`, the one derivation the wires read. */}
      {(["in", "out"] as const).flatMap((side) =>
        (side === "in" ? ins : outs).map((port, index) => {
          const gather = side === "in" && port.gathers;
          const optional = side === "in" && port.optional;
          const tall = gather ? 16 : 8;
          if (side === "out") {
            // **An output is a triangle** pointing along the flow; its wire leaves from the tip.
            const ink = selected ? "var(--now)" : "var(--mark)";
            return (
              <svg key={`mark-out-${port.name}`} aria-hidden data-port-mark={perItem ? "many" : "one"} data-shape="triangle"
                   width={OUT_W} height={OUT_H} className="absolute overflow-visible"
                   style={{ left: width - 1, top: anchorOf(measures, index) - OUT_H / 2 }}>
                <polygon points={`0.8,0.8 ${OUT_W - 0.8},${OUT_H / 2} 0.8,${OUT_H - 0.8}`}
                         fill={selected ? "var(--now)" : "var(--surface)"} stroke={ink} strokeWidth={1.6} strokeLinejoin="round" />
              </svg>
            );
          }
          return (
            <span key={`mark-${side}-${port.name}`} aria-hidden data-shape="circle"
                  data-port-mark={gather ? "gather" : perItem ? "many" : "one"}
                  data-optional={optional ? "true" : undefined}
                  className="absolute box-border rounded-full"
                  style={{
                    left: side === "in" ? -5 : width - 4,
                    top: anchorOf(measures, index) - tall / 2,
                    width: 8,
                    height: tall,
                    background: selected ? "var(--now)" : "var(--surface)",
                    border: `1.6px ${optional ? "dashed" : "solid"} ${selected ? "var(--now)" : "var(--mark)"}`,
                  }} />
          );
        }),
      )}
      {labelled && (["in", "out"] as const).flatMap((side) =>
        (side === "in" ? ins : outs).map((port, index) => (
          <span key={`label-${side}-${port.name}`} data-port-row
                title={`${port.type_id}${spelledStates(port.states)}`}
                className={`absolute font-data text-[10px] whitespace-nowrap ${side === "in" && port.optional ? "text-ink-3" : "text-ink-2"}`}
                style={{ [side === "in" ? "left" : "right"]: 9, top: portOffset(index) - 7, lineHeight: "14px",
                         maxWidth: NODE_W / 2 - 12, overflow: "hidden", textOverflow: "ellipsis" }}>
            {port.name}
            {side === "in" && port.gathers && samples !== undefined && <span className="text-ink-3"> · all {samples}</span>}
            {side === "in" && port.optional && !port.met && <span className="text-ink-3"> · optional</span>}
          </span>
        )),
      )}
      {folded > 0 && !measures && (
        <span data-testid={`node-folded-${id}`} title="Optional inputs not in use: open the step to switch one on"
              className="absolute font-data text-[10px] text-ink-3 whitespace-nowrap"
              style={{ left: 9, top: portOffset(rows - 1) + PORT_GAP - 6, lineHeight: "12px" }}>
          +{folded} optional
        </span>
      )}
      {setRow && !measures && (
        <span data-testid={`node-set-${id}`}
              className="absolute truncate rounded-xs px-[6px] py-[3px] font-data text-[10.5px] text-measured-ink bg-measured-soft"
              style={{ left: 8, right: 8, top: portOffset(rows - 1) + PORT_GAP - 6 + (folded > 0 ? MORE_ROW : 0) }}>
          {setRow}
        </span>
      )}
      {progress && !measures && (
        <span data-testid={`node-progress-${id}`} data-state={progress.state}
              className="absolute left-[10px] right-[10px] flex items-center gap-[6px] text-[10.5px] whitespace-nowrap overflow-hidden"
              style={{ bottom: 8 }}>
          <span aria-hidden className={`w-[7px] h-[7px] rounded-full shrink-0 ${running ? "run-status-pulse" : ""}`} style={{ background: PROGRESS_INK[progress.state] }} />
          <span className={progress.state === "failed" ? "font-semibold text-needs-you-ink" : "text-ink-2"}>{progress.label}</span>
          {progress.of > 1 && (
            <span aria-hidden className="ml-auto flex h-[4px] w-[40px] rounded-full overflow-hidden bg-line-soft shrink-0">
              <span style={{ width: `${(100 * progress.done) / progress.of}%`, background: "var(--done)" }} />
              <span style={{ width: `${(100 * progress.running) / progress.of}%`, background: "var(--now-mid)" }} />
            </span>
          )}
        </span>
      )}
      {progress && measures && (
        <span aria-hidden className={`absolute w-[7px] h-[7px] rounded-full ${running ? "run-status-pulse" : ""}`} data-testid={`node-progress-${id}`}
              data-state={progress.state} style={{ right: 12, top: MEASURE_H / 2 - 4, background: PROGRESS_INK[progress.state] }} />
      )}
      {perItem && samples !== undefined && !measures && (
        <span className="absolute z-[1] rounded-xs px-[5px] text-[10px] font-bold leading-[14px] text-now-ink bg-now-soft border border-now-line"
              style={{ right: 12, bottom: -9 }}>×{samples}</span>
      )}
      {tags.length > 0 && (
        <span className="absolute flex gap-1" style={{ right: 10, top: -9 }}>
          {tags.map((tag) => (
            <span key={tag.key} data-testid={tag.testId} title={tag.title}
                  className="rounded-xs px-[5px] py-[1px] text-[10px] font-bold tracking-[.04em] border whitespace-nowrap"
                  style={tag.style}>
              {tag.words}
            </span>
          ))}
        </span>
      )}
    </button>
  );
}
