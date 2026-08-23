import type { components } from "../api/schema";

type Wire = components["schemas"]["PlacedWire"];

const CORNER = 7;
/** `CR` in `dashboard.html`. Rounded so the graph reads as drawn rather than as a schematic. */

/** An orthogonal path with rounded corners, from the points the backend computed.
 *
 * **The corners are rounded here and the route is decided there.** `layout.py` returns corner
 * points, not an SVG `d` — how tightly a corner turns is presentation, and computing a path
 * string in the compiler would put rendering in a pure package.
 */
/** Where a wire runs once its ends have been dragged.
 *
 * **This is not layout, and the distinction matters.** `layout.py` decides where every node
 * belongs and this does not touch that: a drag is a temporary translation a person applies while
 * looking, and the two endpoints move with their nodes. The elbow is then the design's own rule
 * applied to the moved ends — vertical, across at the midpoint, vertical — because translating
 * the original corner points instead would leave a wire bent around a place its node no longer is.
 *
 * The alternative was leaving wires where the backend put them, which is what shipped first: a
 * dragged node detached from every line reaching it, so the graph broke the moment you touched
 * it. A graph you cannot rearrange is fine; one that lies when you do is not.
 */
function moved(wire: Wire, from: Offset, to: Offset): Wire {
  if (!from.x && !from.y && !to.x && !to.y) return wire;
  const points = wire.points;
  const start = { x: points[0].x + from.x, y: points[0].y + from.y };
  const end = {
    x: points[points.length - 1].x + to.x,
    y: points[points.length - 1].y + to.y,
  };
  const mid = Math.round((start.y + end.y) / 2);
  return {
    ...wire,
    points:
      start.x === end.x
        ? [start, end]
        : [start, { x: start.x, y: mid }, { x: end.x, y: mid }, end],
    label_at: { x: Math.round((start.x + end.x) / 2), y: mid - 6 },
  };
}

function d(wire: Wire): string {
  const p = wire.points;
  if (p.length < 3) return `M${p[0].x},${p[0].y} L${p[p.length - 1].x},${p[p.length - 1].y}`;

  let out = `M${p[0].x},${p[0].y}`;
  for (let i = 1; i < p.length - 1; i++) {
    const before = p[i - 1];
    const here = p[i];
    const after = p[i + 1];
    const r = Math.min(
      CORNER,
      Math.abs(here.x - before.x || here.y - before.y) / 2,
      Math.abs(after.x - here.x || after.y - here.y) / 2,
    );
    const inX = Math.sign(here.x - before.x);
    const inY = Math.sign(here.y - before.y);
    const outX = Math.sign(after.x - here.x);
    const outY = Math.sign(after.y - here.y);
    out += ` L${here.x - inX * r},${here.y - inY * r}`;
    out += ` Q${here.x},${here.y} ${here.x + outX * r},${here.y + outY * r}`;
  }
  const last = p[p.length - 1];
  return `${out} L${last.x},${last.y}`;
}

/** Every wire, plus the type each carries.
 *
 * **Orthogonal, not bezier** — `dashboard.md` §4, and the reason is crossings: two curves meeting
 * at a shallow angle are genuinely indistinguishable and you cannot tell which is which at the
 * intersection. Two right angles you can.
 *
 * The stroke says the tier of the step the wire *leaves*, so uncertainty propagates down the
 * graph rather than stopping at the node that introduced it.
 */
type Offset = { x: number; y: number };
const STILL: Offset = { x: 0, y: 0 };

export function Wires({
  wires,
  tierOf,
  offsets,
  width,
  height,
  onDetach,
}: {
  wires: Wire[];
  tierOf: (id: string) => number;
  offsets: Record<string, Offset>;
  width: number;
  height: number;
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
      {wires.map((original) => {
        const wire = moved(
          original,
          offsets[original.from_node] ?? STILL,
          offsets[original.to_node] ?? STILL,
        );
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
                d={d(wire)}
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
              d={d(wire)}
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
              x={wire.label_at.x}
              y={wire.label_at.y}
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
