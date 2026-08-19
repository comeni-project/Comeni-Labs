import { useState } from "react";

import type { components } from "../api/schema";

type PortView = components["schemas"]["PortView"];

/** A port, and which way it points.
 *
 * **Inputs and outputs are different shapes**, at the operator's request on 2026-08-19. The
 * design gives both the same circle and distinguishes them only by which edge they sit on — which
 * works on a mock where you already know the graph, and asks you to infer direction from position
 * on a real one you are reading for the first time.
 *
 * - **input** — a chevron pointing *into* the node. The graph flows down, so it sits on the top
 *   edge and points the way the data goes.
 * - **output** — a circle on the bottom edge, where a wire leaves.
 *
 * **The two binary channels from `dashboard.md` §3 survive unchanged**, because each means
 * something a reader acts on: **hollow** is a required input nothing feeds, **filled** is met.
 * The five-shape family code the design removed is not coming back — that was an encoding needing
 * a permanent legend, which is a lookup with extra steps. Two shapes for two *directions* is not
 * that: direction is not a lookup, it is the thing the shape is.
 *
 * **A port is not draggable yet, and the cursor no longer says it is.** `cursor-crosshair` and an
 * `onStartWire` that was declared and never passed promised a drag-to-connect that does not
 * exist — the design lists it as a gap and this plan did not close it. A promise nothing keeps
 * costs more than an absence.
 *
 * **Hover names it on the canvas**, rather than only in a `title`. A native tooltip waits a
 * second, renders outside the design, and cannot be read at a glance while tracing a wire.
 */
export function Port({
  port,
  x,
}: {
  port: PortView;
  x: number;
}) {
  const [over, setOver] = useState(false);
  const size = 16;
  const c = size / 2;
  const r = size * 0.28;
  const inbound = port.side === "in";

  return (
    <button
      data-testid="port"
      data-side={port.side}
      data-met={port.met}
      aria-label={`${inbound ? "Input" : "Output"} ${port.name}: ${port.type_id}${
        port.met ? "" : " — nothing feeds this"
      }`}
      onPointerDown={(e) => e.stopPropagation()}
      onMouseEnter={() => setOver(true)}
      onMouseLeave={() => setOver(false)}
      onFocus={() => setOver(true)}
      onBlur={() => setOver(false)}
      style={{ left: x - size / 2, [inbound ? "top" : "bottom"]: -8 }}
      className={`absolute w-4 h-4 p-0 border-0 bg-transparent leading-none cursor-help z-10
                  ${port.met ? "text-ink-3" : "text-[var(--undecided)]"}
                  hover:[&>svg]:scale-125 focus-visible:[&>svg]:scale-125`}
    >
      <svg
        width={size}
        height={size}
        viewBox={`0 0 ${size} ${size}`}
        aria-hidden
        className="transition-transform"
      >
        {inbound ? (
          // A chevron pointing down — into the node, the way the graph flows.
          <path
            d={`M${c - r - 1},${c - r} L${c},${c + r} L${c + r + 1},${c - r}`}
            fill={port.met ? "currentColor" : "var(--surface)"}
            stroke="currentColor"
            strokeWidth={1.6}
            strokeLinejoin="round"
          />
        ) : (
          <circle
            cx={c}
            cy={c}
            r={r}
            fill="currentColor"
            stroke="currentColor"
            strokeWidth={1.5}
          />
        )}
      </svg>

      {over && (
        <span
          data-testid="port-label"
          style={{ [inbound ? "bottom" : "top"]: "18px" }}
          className="absolute left-1/2 -translate-x-1/2 z-20 whitespace-nowrap rounded-r
                     border border-line bg-surface px-2 py-1 font-data text-label
                     text-ink shadow-[0_2px_8px_var(--shadow)] pointer-events-none"
        >
          <b className="font-semibold">{port.name}</b>
          <span className="text-ink-3"> · {port.type_id}</span>
          {!port.met && <span className="text-[var(--undecided)]"> · nothing feeds this</span>}
        </span>
      )}
    </button>
  );
}

/** Ports spread evenly across a node's edge — `portX(count, i) = NW * (i + 1) / (count + 1)`,
 *  the same formula `layout.py` uses to anchor wires, so a wire lands on its dot. */
export function portX(width: number, count: number, index: number): number {
  return (width * (index + 1)) / (count + 1);
}
