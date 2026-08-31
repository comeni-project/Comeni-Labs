import type { components } from "../api/schema";

type Wire = components["schemas"]["PlacedWire"];

import { elbow, NODE_W, path, portOffset, SPINE, type Point, type Positions }
  from "./geometry";

/** Which ports a node declares, in the order the canvas draws them. */
export type PortIndex = Record<string, { ins: string[]; outs: string[]; width: number }>;

/** Where a wire starts and ends, **computed from where the boxes are right now.**
 *
 * It used to render the points the server sent. That is correct for a pipeline nobody is
 * touching and wrong the instant somebody drags: the wire stayed where the server had put it
 * until a round trip came back, so the graph came apart under the hand and snapped together
 * afterwards. Positions are the client's, so the geometry that depends on them is too.
 */
function ends(
  wire: { from_node: string; from_port: string; to_node: string; to_port: string },
  at: Positions,
  ports: PortIndex,
): [Point, Point] | null {
  const from = at[wire.from_node];
  const to = at[wire.to_node];
  const source = ports[wire.from_node];
  const target = ports[wire.to_node];
  if (!from || !to || !source || !target) return null;

  // A port the graph names but the contract does not anchors mid-edge rather than vanishing —
  // `validate` reports that as MD0501, and a picture is not the place to refuse a graph.
  const outAt = source.outs.indexOf(wire.from_port);
  const inAt = target.ins.indexOf(wire.to_port);
  // **Out of the right edge, into the left edge**, and the offset along the edge is
  // `portOffset` — the single derivation `impl-geom` names. Nothing here recomputes a node's
  // size, which is what put every wire 6px above its port on the walk.
  return [
    { x: from.x + NODE_W, y: from.y + (outAt < 0 ? SPINE : portOffset(outAt)) },
    { x: to.x, y: to.y + (inAt < 0 ? SPINE : portOffset(inAt)) },
  ];
}

export function Wires({
  wires,
  at,
  ports,
  width,
  height,
  pending,
  onDetach,
}: {
  wires: Wire[];
  /** Where every node is, right now. The client owns these. */
  at: Positions;
  /** What each node declares, so a wire lands on the chevron the canvas drew. */
  ports: PortIndex;
  width: number;
  height: number;
  /** The wire being dragged right now, if one is. Drawn to the cursor rather than to a port,
   *  because there is no port yet — that is the whole point of showing it. */
  pending?: { from: Point; to: Point } | null;
  /** Remove this wire. Omitted where the canvas is read-only. */
  onDetach?: (wire: {
    from_node: string;
    from_port: string;
    to_node: string;
    to_port: string;
  }) => void;
}) {
  return (
    <svg
      className="absolute top-0 left-0 overflow-visible pointer-events-none"
      width={width}
      height={height}
      aria-hidden
    >
      {/* **The line you are dragging.** Without it a wire drag is an invisible gesture: you
          press on a port, move, and nothing on the screen says anything is happening until you
          land. Dashed and in the undecided colour, because it is not a wire until it is
          dropped and validated — the same reading a tier-4 wire gets. */}
      {pending && (
        <path
          data-testid="pending-wire"
          d={path(elbow(pending.from, pending.to))}
          fill="none"
          stroke="var(--undecided)"
          strokeWidth={1.5}
          strokeDasharray="4 4"
          pointerEvents="none"
        />
      )}

      {wires.map((wire) => {
        const pair = ends(wire, at, ports);
        if (pair === null) return null;
        const points = elbow(pair[0], pair[1]);
        return (
          <g
            key={`${wire.from_node}.${wire.from_port}-${wire.to_node}.${wire.to_port}`}
            className={onDetach ? "pointer-events-auto group" : undefined}
          >
            {/* **A fat invisible path under the visible one.** A 1.5px stroke is a 1.5px hit
                target, which is not a thing a hand can hit. 14px is roughly a finger's worth of
                slop and costs nothing, because it paints nothing. */}
            {onDetach && (
              <path
                data-testid="wire-hit"
                d={path(points)}
                fill="none"
                stroke="transparent"
                strokeWidth={14}
                className="cursor-pointer"
                onClick={() =>
                  onDetach({
                    from_node: wire.from_node,
                    from_port: wire.from_port,
                    to_node: wire.to_node,
                    to_port: wire.to_port,
                  })
                }
              >
                <title>
                  {`${wire.from_node}.${wire.from_port} → ${wire.to_node}.${wire.to_port}` +
                    " — click to detach"}
                </title>
              </path>
            )}
            <path
              data-testid="wire"
              d={path(points)}
              fill="none"
              strokeWidth={1.5}
              // **A wire has no tier.** It was drawn in the colour of the node it leaves —
              // so a graph drawn by hand, where every step exits at tier 4, was a web of red
              // dashes with the nodes' own red edges lost inside it. `impl-inv`: *colour where
              // something needs you, nowhere else*, and a wire is not a decision anybody has
              // to make. Every artboard draws them as one thin neutral line.
              stroke="var(--line-2)"
              // Thickens under the cursor so the thing you are about to remove is the thing
              // you can see you are about to remove.
              className={onDetach ? "group-hover:[stroke-width:3] transition-[stroke-width]" : undefined}
            />
            {/* **No label on the wire.** Every artboard draws the graph with bare wires and
                puts the type on the NODE, in its port rows — `n-bcanvas`: *types on the node*.
                A label at each wire's midpoint put `alignment.bam` across the box the wire was
                heading into, clipped by the next node and unreadable at any zoom; on a
                left-to-right graph the midpoint of a short rank hop is inside the gap between
                two nodes, which is 52px wide.

                The wire keeps its `<title>`, so hovering still names both ends — the
                information is not lost, only the thing that was drawing over the graph. */}
          </g>
        );
      })}
    </svg>
  );
}
