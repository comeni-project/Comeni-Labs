import type { DraftEdge, DraftGraph, Step } from "../../api/types";
import { Canvas } from "../Canvas";
import { elbow, NODE_W, path, portOffset, SPINE, type Positions } from "../geometry";
import { useView } from "../useView";
import type { Author } from "./format";
import { LivingNode } from "./LivingNode";

/** The accepted pipeline, and the one step on offer as a ghost. **Draws; decides nothing.**
 *
 * Positions are the blueprint's (`placement`) — the finished pipeline's layout from `dag-core` —
 * so a step appears where it will stay and the graph never re-lays itself out as it grows. A node
 * with no blueprint position was added by hand and takes the drawn layout's, which is the same
 * implementation. Nothing here computes a layout of its own.
 */
export function LivingCanvas({
  graph,
  ghost,
  ghostEdges = [],
  positions,
  steps,
  authors,
  selected,
  onSelect,
  footer,
  instead = null,
}: {
  graph: DraftGraph;
  /** The node id of the step on offer, when there is one. */
  ghost: string | null;
  ghostEdges?: DraftEdge[];
  positions: Positions;
  /** Ports and tiers, from the drawn view of the graph plus its ghost. */
  steps: Record<string, Step>;
  authors: Record<string, Author>;
  selected: string | null;
  onSelect: (node: string | null) => void;
  footer?: React.ReactNode;
  /** An alternative being previewed for the ghost's slot — drawn *in* the slot, never beside it. */
  instead?: string | null;
}) {
  const view = useView();
  const ids = [...graph.nodes.map((n) => n.id), ...(ghost ? [ghost] : [])];

  const ends = (edge: DraftEdge) => {
    const from = positions[edge.from_node];
    const to = positions[edge.to_node];
    if (!from || !to) return null;
    const outs = (steps[edge.from_node]?.ports ?? []).filter((p) => p.side === "out").map((p) => p.name);
    const ins = (steps[edge.to_node]?.ports ?? []).filter((p) => p.side === "in").map((p) => p.name);
    const o = outs.indexOf(edge.from_port);
    const i = ins.indexOf(edge.to_port);
    return path(
      elbow(
        { x: from.x + NODE_W, y: from.y + (o < 0 ? SPINE : portOffset(o)) },
        { x: to.x, y: to.y + (i < 0 ? SPINE : portOffset(i)) },
      ),
    );
  };

  const width = Math.max(0, ...ids.map((id) => (positions[id]?.x ?? 0) + NODE_W + 40));
  const height = Math.max(0, ...ids.map((id) => (positions[id]?.y ?? 0) + 160));

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

  return (
    <Canvas
      view={view.view}
      onWheel={view.onWheel}
      onPointerDown={view.onPointerDown}
      onClick={(e) => {
        if (!(e.target as HTMLElement).closest("[data-node]")) onSelect(null);
      }}
      footer={footer}
    >
      <svg aria-hidden width={width} height={height} className="absolute left-0 top-0 overflow-visible">
        {graph.edges.map((edge) => {
          const d = ends(edge);
          return d ? (
            <path key={`${edge.from_node}.${edge.from_port}-${edge.to_node}.${edge.to_port}`}
                  data-testid="living-wire" d={d} fill="none" stroke="var(--port-line)"
                  strokeWidth={1.2} />
          ) : null;
        })}
        {ghostEdges.map((edge) => {
          const d = ends(edge);
          return d ? (
            <path key={`ghost-${edge.from_node}-${edge.to_node}-${edge.to_port}`}
                  data-testid="living-wire-ghost" d={d} fill="none" stroke="var(--port-line)"
                  strokeWidth={1.2} strokeDasharray="4 4" opacity={0.6} />
          ) : null;
        })}
      </svg>
      {ids.map((id) =>
        positions[id] ? (
          <LivingNode
            key={id}
            id={id}
            at={positions[id]}
            tier={steps[id]?.tier ?? 1}
            author={authors[id] ?? "resolver"}
            ports={steps[id]?.ports ?? []}
            settled={steps[id]?.settings.length}
            ghost={id === ghost}
            instead={id === ghost ? instead : null}
            selected={selected === id}
            onSelect={() => onSelect(id)}
          />
        ) : null,
      )}
    </Canvas>
  );
}
