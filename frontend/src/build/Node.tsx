import type { components } from "../api/schema";
import { Port, portX } from "./Port";

type Placed = components["schemas"]["PlacedNode"];
type Step = components["schemas"]["StepView"];

/** The tier rail — 4px down the left edge, and the only thing on a node that is not text.
 *
 * **Certainty drawn as stroke**, which is `dashboard.md` §1's governing idea and the same
 * language `Standing` uses on the front door. Solid pea for a forced choice, faded pea for a
 * convention, dashed amber for a rule that read measured data, gapped coral for one nobody
 * judged. The treatments are the design's, gradient stops included: 5-on-4-off at tier 3,
 * 3-on-8-off at tier 4, so the gappier a rail looks the less settled the decision is.
 */
const RAIL: Record<number, string> = {
  1: "bg-pea",
  2: "bg-pea opacity-[.42]",
  3: "bg-[repeating-linear-gradient(to_bottom,var(--measured)_0_5px,transparent_5px_9px)]",
  4: "bg-[repeating-linear-gradient(to_bottom,var(--undecided)_0_3px,transparent_3px_11px)]",
};

/** One step on the canvas.
 *
 * **Dragged in the view only.** Nothing persists a node position and 3C is not the phase to add
 * somewhere to put one — the layout is deterministic precisely so that it does not need to be
 * stored. A drag is a person looking closer, not an edit.
 */
export function Node({
  placed,
  step,
  zoom,
  dim = false,
  selected,
  onSelect,
  onOpenSettings,
  offset,
  onDrag,
  dragging,
  onStartWire,
  onFinishWire,
  verdictFor,
}: {
  placed: Placed;
  step: Step | undefined;
  zoom: number;
  dim?: boolean;
  selected: boolean;
  onSelect: () => void;
  onOpenSettings?: () => void;
  offset: { x: number; y: number };
  onDrag: (by: { x: number; y: number }) => void;
  /** Which output a wire is being dragged from, anywhere on the canvas. `null` most of the
   *  time, and when it is null every port renders exactly as it did before this existed. */
  dragging?: { node: string; port: string } | null;
  onStartWire?: (port: string) => void;
  onFinishWire?: (port: string) => void;
  /** How an input port should look during someone else's drag. A lookup into the server's
   *  compatibility index — never a decision made here. */
  verdictFor?: (port: string) => "yes" | "conventional-no" | "no" | undefined;
}) {

  const onPointerDown = (e: React.PointerEvent) => {
    e.stopPropagation();
    const sx = e.clientX;
    const sy = e.clientY;
    const from = offset;
    const move = (ev: PointerEvent) =>
      // **Divided by the zoom**, or a node at 50% travels twice as far as the cursor.
      // **Reported upward, not kept here.** It was local state, which meant a dragged node left
      // its wires behind — the graph broke the moment you touched it, which is worse than a
      // graph you cannot rearrange.
      onDrag({ x: from.x + (ev.clientX - sx) / zoom, y: from.y + (ev.clientY - sy) / zoom });
    const up = () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  };

  return (
    <div
      data-node
      data-testid="node"
      data-id={placed.id}
      data-tier={placed.tier}
      data-selected={selected || undefined}
      data-dim={dim || undefined}
      onPointerDown={onPointerDown}
      onClick={onSelect}
      style={{
        left: `${Math.round(placed.x + offset.x)}px`,
        top: `${Math.round(placed.y + offset.y)}px`,
        width: placed.width,
      }}
      className="absolute flex rounded-r border border-line-2 border-l-0 bg-surface
                 cursor-grab active:cursor-grabbing
                 hover:shadow-[0_2px_10px_var(--shadow)]
                 data-[selected]:shadow-[0_0_0_2px_var(--ink)]
                 data-[dim]:opacity-20 transition-[box-shadow,opacity]"
    >
      {/* Ports sit on the node's edges, spread by the same formula that anchors the wires —
          so a wire lands on its dot rather than near it. */}
      {(["in", "out"] as const).map((side) => {
        const ports = (step?.ports ?? []).filter((port) => port.side === side);
        return ports.map((port, i) => (
          <Port
            verdict={
              // A port only colours during a drag, and never the one being dragged FROM.
              dragging && port.side === "in" ? verdictFor?.(port.name) : undefined
            }
            onStartWire={port.side === "out" ? () => onStartWire?.(port.name) : undefined}
            onFinishWire={port.side === "in" ? () => onFinishWire?.(port.name) : undefined}
            key={`${side}.${port.name}`}
            port={port}
            x={portX(placed.width, ports.length, i)}
          />
        ));
      })}

      <div className={`w-1 shrink-0 rounded-l-r ${RAIL[placed.tier] ?? "bg-line-2"}`} />
      <div className="flex-1 min-w-0 p-[10px]">
        <div className="font-data text-body font-semibold tracking-[-.01em] text-ink truncate">
          {step?.process ?? placed.id}
        </div>
        <div className="text-label text-ink-3 mt-[2px] truncate">
          {step?.contract_id ?? ""}
        </div>
        {step && step.settings.length > 0 && (
          <div className="mt-2 flex items-baseline gap-2">
            <button
              data-testid="open-settings"
              onPointerDown={(e) => e.stopPropagation()}
              onClick={(e) => {
                e.stopPropagation();
                onOpenSettings?.();
              }}
              className="text-secondary text-ink-2 bg-transparent border-0 p-0 cursor-pointer
                         underline decoration-dotted underline-offset-2 hover:text-ink"
            >
              {step.settings.length} {step.settings.length === 1 ? "setting" : "settings"}
            </button>
            {/* **The worst tier among its parameters, on the node.** `dashboard.html` does the
                same: a step can be settled and still hold a parameter nobody judged, and a
                reader scanning the canvas has to be able to see that without opening a card. */}
            {step.settings.some((s) => s.tier === 4) ? (
              <span className="text-label uppercase tracking-[.1em] text-[var(--undecided)]">
                needs your decision
              </span>
            ) : step.settings.some((s) => s.tier === 3) ? (
              <span className="text-label uppercase tracking-[.1em] text-[var(--measured)]">
                check the premise
              </span>
            ) : null}
          </div>
        )}
      </div>
    </div>
  );
}
