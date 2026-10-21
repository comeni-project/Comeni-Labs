import { useEffect, useRef, useState } from "react";

import type { components } from "../../api/schema";
import type { DraftEdge, DraftGraph, Step } from "../../api/types";
import { Canvas } from "../Canvas";
import { NODE_H, NODE_W, portOffset, SPINE, type Point, type Positions } from "../geometry";
import { place } from "../Sources";
import { useView } from "../useView";
import type { MotionEvent } from "./authoringReducer";
import { Flowline, flowLabel, SOURCE_H, SOURCE_W, SourceNode, type Flow } from "./CollectionChannel";
import { valuesOf } from "./values";
import type { Author } from "./format";
import { LivingNode, type ReviewState } from "./LivingNode";
import { motionFor, wireSubject } from "./motion";

type Channel = components["schemas"]["ChannelView"];

/** The accepted pipeline, the step on offer as a ghost, and how its data moves.
 *
 * **Draws; decides nothing.** Positions are the blueprint's `dag-core` layout, so a step appears
 * where it will stay; a hand-added step takes the drawn layout's. How many times each part runs is
 * the server's (`ChannelView.scope`, `PortView.gathers`, `StepView.runs`) — this only chooses a
 * stroke for it. Inputs are placed by `Sources.place`, the rule the existing canvas uses.
 *
 * **The client owns a position once somebody drags it**, and **Tidy** gives the server's layout
 * back — the escape hatch the manual builder has always had.
 */
const CONTROL = "px-[14px] py-[6px] rounded-button border border-line-2 bg-surface text-[13px] font-semibold "
  + "text-ink cursor-pointer hover:bg-[var(--hover)] focus-visible:shadow-[var(--ring)]";

/** What the canvas's colours mean, as the boards' legend says it. */
const LEGEND: [string, string][] = [
  ["settled", "var(--line-2)"], ["measured", "var(--measured)"], ["needs you", "var(--needs-you)"],
];

export function LivingCanvas({
  graph,
  ghost,
  ghostProposal = null,
  ghostEdges = [],
  positions,
  steps,
  channels = [],
  authors,
  selected,
  onSelect,
  footer,
  readOnly = false,
  events = [],
  onPlayed = () => undefined,
  reveal = {},
  empty,
  stale = false,
  reviews = {},
  working = false,
  focus = null,
}: {
  graph: DraftGraph;
  /** The node id of the step on offer, when there is one. */
  ghost: string | null;
  /** The proposal that put it there — what its `proposal_shown` event is about. */
  ghostProposal?: string | null;
  ghostEdges?: DraftEdge[];
  positions: Positions;
  steps: Record<string, Step>;
  channels?: Channel[];
  authors: Record<string, Author>;
  selected: string | null;
  onSelect: (node: string | null) => void;
  footer?: React.ReactNode;
  /** A complete preview: nothing here can be moved, selected or changed. */
  readOnly?: boolean;
  events?: MotionEvent[];
  onPlayed?: (event: MotionEvent) => void;
  /** Spawn's first-arrival reveal: a delay per step, in ms. Empty on reload. */
  reveal?: Record<string, number>;
  /** What the empty canvas says instead of the invitation — after an honest stop, why. */
  empty?: string;
  /** The frame is the last pipeline built, and answers have changed since: said, never hidden. */
  stale?: boolean;
  /** Whether each drawn step's review still holds — said in words, never by repainting its tier. */
  reviews?: Record<string, ReviewState>;
  /** A decision is on its way: the last complete frame stays, marked as being updated. */
  working?: boolean;
  /** The step the engine or the person is looking at — brought on screen when it changes. */
  focus?: string | null;
}) {
  const view = useView();
  const probe = useRef<HTMLSpanElement>(null);
  const [moved, setMoved] = useState<Positions>({});
  const drag = useRef<{ id: string; from: Point; origin: Point; travelled: boolean } | null>(null);

  const at: Positions = { ...positions, ...moved };

  // **The canvas follows the engine**: when the step in focus changes, or the server places it,
  // it is brought on screen. Read from the server's placement, not a drag's, so moving a step by
  // hand never pans the canvas under the pointer.
  const target = focus ? positions[focus] : undefined;
  const bringIntoView = view.reveal;
  useEffect(() => {
    const frame = probe.current?.closest<HTMLElement>("[data-testid='canvas']");
    if (!target || !frame) return;
    const rect = frame.getBoundingClientRect();
    bringIntoView({ x: target.x, y: target.y, w: NODE_W, h: NODE_H }, { w: rect.width, h: rect.height });
    // eslint-disable-next-line react-hooks/exhaustive-deps -- a step moves by its coordinates, not its object
  }, [focus, target?.x, target?.y, bringIntoView]);
  // **Each step once.** A frame's graph already holds the step on offer; the ghost names which one
  // it is, and its wires are drawn dashed, not also solid.
  const ids = [...new Set([...graph.nodes.map((n) => n.id), ...(ghost ? [ghost] : [])])];
  const visible = new Set(ids);
  const wireKey = (e: DraftEdge) => `${e.from_node}.${e.from_port}>${e.to_node}.${e.to_port}`;
  const dashed = new Set(ghostEdges.map(wireKey));
  const solid = graph.edges.filter((e) => !dashed.has(wireKey(e)));

  if (ids.length === 0) {
    return (
      <div className="relative flex-1 min-h-0 flex flex-col items-center justify-center text-center gap-2"
           data-testid="canvas-empty">
        <span className="text-label text-ink-3">Nothing built yet</span>
        <span className="text-[12.5px] text-ink-2">
          {empty ?? "Confirm the goal on the right and the steps arrive one at a time"}
        </span>
        {footer}
      </div>
    );
  }

  const count = channels.find((c) => c.scope === "sample")?.count ?? null;
  const portsOf = (node: string, side: "in" | "out") =>
    (steps[node]?.ports ?? []).filter((p) => p.side === side);
  const tipIn = (node: string, port: string): Point | null => {
    const box = at[node];
    if (!box) return null;
    const index = portsOf(node, "in").findIndex((p) => p.name === port);
    return { x: box.x, y: box.y + (index < 0 ? SPINE : portOffset(index)) };
  };
  const tipOut = (node: string, port: string): Point | null => {
    const box = at[node];
    if (!box) return null;
    const index = portsOf(node, "out").findIndex((p) => p.name === port);
    return { x: box.x + NODE_W, y: box.y + (index < 0 ? SPINE : portOffset(index)) };
  };
  const gathers = (node: string, port: string) =>
    portsOf(node, "in").some((p) => p.name === port && p.gathers);

  /** One stroke, a ribbon, or a converging ribbon — from server facts, never from a type name. */
  const flowOf = (edge: DraftEdge): Flow =>
    gathers(edge.to_node, edge.to_port) ? "gather"
      : steps[edge.from_node]?.runs === "per_item" ? "many" : "one";

  // ── inputs, placed where they enter ────────────────────────────────────────────────────
  /** Whether the gutter to the left of a node is empty — `place`'s own reason for a left-hand
   *  socket is that *it overlaps nothing*, so that is what is asked. **Not "is this the leftmost
   *  column"**: the first render put both sources of the collection board below their consumers
   *  and on top of the next node, because their column was not the leftmost although its gutter
   *  was empty. */
  const gutterClear = (anchor: Point, index: number) => {
    const box = place("Input", anchor, index, true, { w: SOURCE_W, h: SOURCE_H }).box;
    return ids.every((id) => {
      const other = at[id];
      if (!other || other === anchor) return true;
      return (
        box.x + SOURCE_W <= other.x || other.x + NODE_W <= box.x ||
        box.y + SOURCE_H <= other.y || other.y + NODE_H <= box.y
      );
    });
  };
  const perNode = new Map<string, number>();
  const sources = channels.flatMap((channel) => {
    const feeds = channel.ports.map((key) => key.split(".")).filter(([node]) => visible.has(node));
    if (feeds.length === 0 || !at[feeds[0][0]]) return [];
    const anchor = at[feeds[0][0]];
    const index = perNode.get(feeds[0][0]) ?? 0;
    perNode.set(feeds[0][0], index + 1);
    const geometry = place("Input", anchor, index, gutterClear(anchor, index), { w: SOURCE_W, h: SOURCE_H });
    return [{ channel, box: geometry.box, edge: geometry.edge, feeds }];
  });

  const drawn = ids.filter((id) => id !== ghost).length;
  /** Fit the whole drawing, inputs included, in the frame the probe sits in. */
  const fitView = () => {
    const frame = probe.current?.closest<HTMLElement>("[data-testid='canvas']");
    if (!frame) return;
    const xs = [...ids.map((id) => at[id]?.x ?? 0), ...sources.map((s) => s.box.x)];
    const ys = [...ids.map((id) => at[id]?.y ?? 0), ...sources.map((s) => s.box.y)];
    const left = Math.min(...xs), top = Math.min(...ys);
    const right = Math.max(...ids.map((id) => (at[id]?.x ?? 0) + NODE_W));
    const bottom = Math.max(...ids.map((id) => (at[id]?.y ?? 0) + NODE_H), ...sources.map((s) => s.box.y + SOURCE_H));
    const rect = frame.getBoundingClientRect();
    view.fit(right - left, bottom - top, rect.width, rect.height - 96, { x: left, y: top - 40 });
  };
  const width = Math.max(0, ...ids.map((id) => (at[id]?.x ?? 0) + NODE_W + 80));
  const height = Math.max(
    0,
    ...ids.map((id) => (at[id]?.y ?? 0) + 200),
    ...sources.map((s) => s.box.y + SOURCE_H + 20),
  );

  return (
    <Canvas
      view={view.view}
      onWheel={view.onWheel}
      onPointerDown={view.onPointerDown}
      dots
      onClick={(e) => {
        if (!(e.target as HTMLElement).closest("[data-node]")) onSelect(null);
      }}
      footer={
        <>
          <span ref={probe} hidden />
          {/* **The boards' frame**: what is drawn and over how many samples, along the top; the
              view's controls bottom-left, what the colours mean bottom-right. */}
          <div className="absolute left-4 right-4 top-3 flex items-baseline gap-3 pointer-events-none">
            <span data-testid="canvas-caption" className="text-[13px] text-ink-2">
              {drawn} {drawn === 1 ? "step" : "steps"} · {sources.length} {sources.length === 1 ? "input" : "inputs"}
            </span>
            {(stale || working) && (
              <span role="status" data-testid={stale ? "canvas-stale" : "canvas-working"}
                    className="text-[12.5px] text-ink-2">
                {stale ? "Outdated — the last pipeline built" : "Updating…"}
              </span>
            )}
            {count !== null && (
              <span data-testid="canvas-samples" className="ml-auto text-[13px] text-ink-2">
                {count} samples, one task each
              </span>
            )}
          </div>
          <div className="absolute left-4 bottom-4 flex gap-2">
            <button type="button" onClick={fitView} className={CONTROL}>Fit</button>
            {footer}
            {Object.keys(moved).length > 0 && (
              <button type="button" data-testid="tidy" onClick={() => setMoved({})} className={CONTROL}>
                Tidy
              </button>
            )}
          </div>
          <ul aria-label="legend" className="absolute right-4 bottom-4 m-0 flex items-center gap-3 px-3 py-[6px]
                                             rounded-button border border-line bg-surface text-[12.5px] text-ink-2">
            {LEGEND.map(([word, colour]) => (
              <li key={word} className="list-none flex items-center gap-[6px]">
                <span aria-hidden className="w-[10px] h-[5px] rounded-full" style={{ background: colour }} />
                {word}
              </li>
            ))}
          </ul>
        </>
      }
    >
      <svg aria-hidden width={width} height={height} className="absolute left-0 top-0 overflow-visible">
        {sources.flatMap(({ channel, edge, feeds }) =>
          feeds.map(([node, port]) => {
            const tip = tipIn(node, port);
            if (!tip) return null;
            const flow: Flow =
              gathers(node, port) ? "gather" : channel.scope === "sample" ? "many" : "one";
            return (
              <Flowline key={`src-${channel.name}-${node}-${port}`} testId={`flow-${channel.name}-${node}`}
                        from={edge} to={tip} flow={flow}
                        label={selected === node ? flowLabel(flow, channel.count ?? null) : undefined} />
            );
          }),
        )}
        {solid.map((edge) => {
          const from = tipOut(edge.from_node, edge.from_port);
          const to = tipIn(edge.to_node, edge.to_port);
          if (!from || !to) return null;
          const flow = flowOf(edge);
          const played = motionFor(events, ["edge_committed"], wireSubject(edge));
          return (
            <Flowline key={`${edge.from_node}.${edge.from_port}-${edge.to_node}.${edge.to_port}`}
                      testId={`wire-${edge.from_node}-${edge.to_node}`} from={from} to={to} flow={flow}
                      label={
                        selected === edge.from_node || selected === edge.to_node
                          ? flowLabel(flow, count)
                          : undefined
                      }
                      className={played?.className}
                      onDrawn={played ? () => onPlayed(played.event) : undefined} />
          );
        })}
        {ghostEdges.map((edge) => {
          const from = tipOut(edge.from_node, edge.from_port);
          const to = tipIn(edge.to_node, edge.to_port);
          return from && to ? (
            <Flowline key={`ghost-${edge.from_node}-${edge.to_node}-${edge.to_port}`}
                      testId={`ghost-wire-${edge.from_node}-${edge.to_node}`}
                      from={from} to={to} flow="one" dashed />
          ) : null;
        })}
      </svg>

      {sources.map(({ channel, box }) => (
        <SourceNode key={channel.name} at={box} name={channel.name} typeId={channel.type_id}
                    states={channel.states} scope={channel.scope} count={channel.count ?? null} />
      ))}

      {ids.map((id) => {
        if (!at[id]) return null;
        const isGhost = id === ghost;
        const played = isGhost
          ? (ghostProposal ? motionFor(events, ["proposal_shown"], ghostProposal) : null)
          : motionFor(events, ["proposal_accepted"], id);
        return (
          <LivingNode
            key={id}
            id={id}
            at={at[id]}
            author={authors[id] ?? "resolver"}
            ports={steps[id]?.ports ?? []}
            counts={steps[id] && !isGhost ? valuesOf([steps[id]]) : undefined}
            reviewState={isGhost ? (reviews[id] === "again" ? "again" : "proposed") : reviews[id] ?? "unknown"}
            perItem={steps[id]?.runs === "per_item"}
            ghost={isGhost}
            selected={selected === id}
            className={id in reveal ? "living-reveal" : played?.className}
            delay={reveal[id]}
            onAnimationEnd={played ? () => onPlayed(played.event) : undefined}
            onSelect={() => {
              if (!readOnly && !drag.current?.travelled) onSelect(id);
            }}
            onPointerDown={(e) => {
              if (readOnly) return;
              drag.current = { id, from: { x: e.clientX, y: e.clientY }, origin: at[id], travelled: false };
              (e.target as Element).setPointerCapture?.(e.pointerId);
            }}
            onPointerMove={(e) => {
              const d = drag.current;
              if (!d || d.id !== id) return;
              const dx = (e.clientX - d.from.x) / view.view.k;
              const dy = (e.clientY - d.from.y) / view.view.k;
              if (!d.travelled && Math.abs(dx) + Math.abs(dy) < 3) return;
              d.travelled = true;
              setMoved((m) => ({ ...m, [id]: { x: Math.round(d.origin.x + dx), y: Math.round(d.origin.y + dy) } }));
            }}
            onPointerUp={() => {
              // **A macrotask, not a microtask.** The click that ends a drag is dispatched after this
              // handler returns, and a microtask would clear the drag before it — so dragging a
              // node would also select it.
              setTimeout(() => {
                drag.current = null;
              }, 0);
            }}
          />
        );
      })}
    </Canvas>
  );
}
