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
 * **Since Plan 4 phase 6 it is the artboard's square** — `.port { width:7px; height:7px }`,
 * sitting ON the edge at `left:-4px` or `right:-4px`. The graph flows LEFT TO RIGHT, so an
 * input is on the left edge and an output on the right, and *direction is where it is* rather
 * than something a shape has to encode. The chevron and the circle are gone with the downward
 * flow that made them mean anything.
 *
 * The direction is still drawn, once, **inside** the node: `◀ fastq.reads` on a port row. That
 * is `n-bcanvas`'s *types on the node*, and it puts the arrow beside the word it describes.
 *
 * **The two binary channels from `dashboard.md` §3 survive unchanged**, because each means
 * something a reader acts on: **hollow** is a required input nothing feeds, **filled** is met.
 * The five-shape family code the design removed is not coming back — that was an encoding needing
 * a permanent legend, which is a lookup with extra steps. Two shapes for two *directions* is not
 * that: direction is not a lookup, it is the thing the shape is.
 *
 * **A port is draggable now, and the cursor says so again.** Plan 3C removed `cursor-crosshair`
 * and an `onStartWire` that was declared and never passed, on the grounds that a promise nothing
 * keeps costs more than an absence. That was right then. This closes the gap rather than
 * re-opening the promise: `onStartWire` and `onFinishWire` are passed, and `verdict` colours the
 * port during someone else's drag.
 *
 * **The colour is a lookup, not a judgement.** `useCompatibility.accepts` intersects two lists
 * the server computed; nothing here decides whether a BAM can feed featureCounts. Green is legal
 * and conventional, amber is legal and not (which `MD0507` will say on drop), and a greyed port
 * is one the server would refuse. `validate` on drop is still the authority — this is only how
 * the wire looks while your mouse is moving.
 *
 * **Hover names it on the canvas**, rather than only in a `title`. A native tooltip waits a
 * second, renders outside the design, and cannot be read at a glance while tracing a wire.
 */
export function Port({
  port,
  side,
  y,
  verdict,
  onStartWire,
  onExplore,
  onFinishWire,
}: {
  port: PortView;
  /** Which edge it sits on. The graph flows left to right, so this IS the direction. */
  side: "in" | "out";
  /** Where along the edge, from `portOffset`. Never computed here. */
  y: number;
  /** How this port looks while a wire is being dragged from somewhere else. `undefined` when
   *  nothing is being dragged, which is most of the time. */
  verdict?: "yes" | "conventional-no" | "no";
  onStartWire?: () => void;
  /** Open the picker for this port — what could sit on the other end of a wire. */
  onExplore?: () => void;
  onFinishWire?: () => void;
}) {
  const [over, setOver] = useState(false);
  const inbound = side === "in";

  return (
    <button
      data-testid="port"
      data-side={side}
      data-met={port.met}
      aria-label={`${inbound ? "Input" : "Output"} ${port.name}: ${port.type_id}${
        port.met ? "" : " — nothing feeds this"
      }`}
      data-verdict={verdict ?? ""}
      onPointerDown={(e) => {
        e.stopPropagation();
        // An output starts a wire; an input cannot. The direction is the port's, not the
        // gesture's, which is what makes MD0502 unreachable from the canvas rather than merely
        // reported by it.
        if (!inbound) onStartWire?.();
      }}
      onPointerUp={(e) => {
        e.stopPropagation();
        if (inbound) onFinishWire?.();
      }}
      onDoubleClick={(e) => {
        e.stopPropagation();
        onExplore?.();
      }}
      onMouseEnter={() => setOver(true)}
      onMouseLeave={() => setOver(false)}
      onFocus={() => setOver(true)}
      onBlur={() => setOver(false)}
      // **On the edge, at the one derivation.** `y` is `portOffset(index)` — the caller does not
      // compute it and neither does this component, which is `impl-geom`'s *never write a
      // coordinate twice*. `-4px` centres a 7px square on a 1px border.
      style={{ top: y - 3.5, [inbound ? "left" : "right"]: -4 }}
      className={`absolute w-[7px] h-[7px] p-0 leading-none z-10 transition-transform
                  ${onStartWire || onFinishWire ? "cursor-crosshair" : "cursor-help"}
                  hover:scale-150 focus-visible:scale-150`}
    >
      <span aria-hidden className="block w-full h-full" style={{
        // `.port` is a filled square with a 1px stroke; `.port.on` swaps both for `--link`. An
        // unmet input is the one that spends `--undecided`, because it is the one that needs
        // somebody — invariant 6, on the smallest element that can carry it.
        background: verdict === "yes" || verdict === "conventional-no"
          ? "var(--link-soft)"
          : "var(--node)",
        border: `1px solid ${
          verdict === "no"
            ? "var(--port-line)"
            : verdict === "conventional-no"
              ? "var(--measured)"
              : verdict === "yes"
                ? "var(--link)"
                : port.met
                  ? "var(--port-line)"
                  : "var(--undecided)"
        }`,
        opacity: verdict === "no" ? 0.25 : 1,
      }} />

      {over && (
        <span
          data-testid="port-label"
          style={{ [inbound ? "right" : "left"]: "12px" }}
          className="absolute top-1/2 -translate-y-1/2 z-20 whitespace-nowrap
                     border border-line bg-surface px-2 py-1 font-data text-label
                     text-ink shadow-e2 pointer-events-none"
        >
          <b className="font-semibold">{port.name}</b>
          <span className="text-ink-3"> · {port.type_id}</span>
          {!port.met && <span className="text-[var(--undecided)]"> · nothing feeds this</span>}
        </span>
      )}
    </button>
  );
}

