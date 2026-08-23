import type { components } from "../api/schema";

type Wire = components["schemas"]["PlacedWire"];

import { elbow, heightFor, path, portX, type Point, type Positions } from "./geometry";

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
  return [
    {
      x: from.x + (outAt < 0 ? source.width / 2 : portX(source.width, source.outs.length, outAt)),
      y: from.y + heightFor(source.ins.length, source.outs.length),
    },
    {
      x: to.x + (inAt < 0 ? target.width / 2 : portX(target.width, target.ins.length, inAt)),
      y: to.y,
    },
  ];
}

export function Wires({
  wires,
  tierOf,
  at,
  ports,
  width,
  height,
  pending,
  onDetach,
}: {
  wires: Wire[];
  tierOf: (id: string) => number;
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
        const label = {
          x: Math.round((pair[0].x + pair[1].x) / 2),
          y: Math.round((pair[0].y + pair[1].y) / 2) - 6,
        };
        const tier = tierOf(wire.from_node);
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
              stroke={
                tier === 4
                  ? "var(--undecided)"
                  : tier === 3
                    ? "var(--measured)"
                    : "var(--line-2)"
              }
              strokeDasharray={tier === 4 ? "3 8" : tier === 3 ? "5 4" : undefined}
              // Thickens under the cursor so the thing you are about to remove is the thing
              // you can see you are about to remove.
              className={onDetach ? "group-hover:[stroke-width:3] transition-[stroke-width]" : undefined}
            />
            <text
              x={label.x}
              y={label.y}
              textAnchor="middle"
              className="font-data"
              fontSize="10"
              fill="var(--ink-3)"
            >
              {wire.type_id}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
