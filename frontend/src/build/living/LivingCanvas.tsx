import { useRef, useState } from "react";

import type { components } from "../../api/schema";
import type { DraftEdge, DraftGraph, Step } from "../../api/types";
import { Canvas } from "../Canvas";
import { NODE_H, NODE_W, portOffset, SPINE, type Point, type Positions } from "../geometry";
import { place } from "../Sources";
import { useView } from "../useView";
import type { MotionEvent } from "./authoringReducer";
import { Flowline, flowLabel, flowTag, SOURCE_H, SOURCE_W, SourceNode, type Flow } from "./CollectionChannel";
import type { Author } from "./format";
import { LivingNode } from "./LivingNode";
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
  instead = null,
  events = [],
  onPlayed = () => undefined,
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
  /** An alternative being previewed for the ghost's slot — drawn *in* the slot, never beside it. */
  instead?: string | null;
  events?: MotionEvent[];
  onPlayed?: (event: MotionEvent) => void;
}) {
  const view = useView();
  const [moved, setMoved] = useState<Positions>({});
  const drag = useRef<{ id: string; from: Point; origin: Point; travelled: boolean } | null>(null);

  const at: Positions = { ...positions, ...moved };
  const ids = [...graph.nodes.map((n) => n.id), ...(ghost ? [ghost] : [])];
  const visible = new Set(ids);

  if (ids.length === 0) {
    return (
      <div className="relative flex-1 min-h-0 flex flex-col items-center justify-center text-center gap-2"
           data-testid="canvas-empty">
        <span className="font-data text-[9.5px] tracking-[.15em] uppercase text-ink-3">Nothing built yet</span>
        <span className="text-[12.5px] text-ink-2">
          Confirm the goal on the right and the steps arrive one at a time
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
      onClick={(e) => {
        if (!(e.target as HTMLElement).closest("[data-node]")) onSelect(null);
      }}
      footer={
        <>
          {footer}
          {Object.keys(moved).length > 0 && (
            <button type="button" data-testid="tidy" onClick={() => setMoved({})}
                    className="absolute right-5 bottom-5 font-data text-[11px] px-3 py-[6px] bg-transparent
                               text-ink-2 border cursor-pointer focus-visible:shadow-[var(--ring)]"
                    style={{ borderColor: "var(--line-2)" }}>
              Tidy
            </button>
          )}
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
                        label={selected === node ? flowLabel(flow, channel.count ?? null) : flowTag(flow)} />
            );
          }),
        )}
        {graph.edges.map((edge) => {
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
                          : flow === "one" ? undefined : flowTag(flow)
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
                      from={from} to={to} flow={flowOf(edge)} dashed />
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
        const runs =
          steps[id]?.runs === "per_item" ? `runs ${count === null ? "N" : count}×` : "runs once";
        return (
          <LivingNode
            key={id}
            id={id}
            at={at[id]}
            tier={steps[id]?.tier ?? 1}
            author={authors[id] ?? "resolver"}
            ports={steps[id]?.ports ?? []}
            settled={steps[id]?.settings.length}
            runs={steps[id] ? runs : undefined}
            perItem={steps[id]?.runs === "per_item"}
            ghost={isGhost}
            instead={isGhost ? instead : null}
            selected={selected === id}
            className={played?.className}
            onAnimationEnd={played ? () => onPlayed(played.event) : undefined}
            onSelect={() => {
              if (!drag.current?.travelled) onSelect(id);
            }}
            onPointerDown={(e) => {
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
