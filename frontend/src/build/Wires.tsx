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
export function Wires({
  wires,
  tierOf,
  width,
  height,
}: {
  wires: Wire[];
  tierOf: (id: string) => number;
  width: number;
  height: number;
}) {
  return (
    <svg
      className="absolute top-0 left-0 overflow-visible pointer-events-none"
      width={width}
      height={height}
      aria-hidden
    >
      {wires.map((wire) => {
        const tier = tierOf(wire.from_node);
        return (
          <g key={`${wire.from_node}.${wire.from_port}-${wire.to_node}.${wire.to_port}`}>
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
