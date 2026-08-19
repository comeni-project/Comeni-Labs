import { useState } from "react";

import type { components } from "../api/schema";

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
}: {
  placed: Placed;
  step: Step | undefined;
  zoom: number;
  dim?: boolean;
  selected: boolean;
  onSelect: () => void;
}) {
  const [nudge, setNudge] = useState({ x: 0, y: 0 });

  const onPointerDown = (e: React.PointerEvent) => {
    e.stopPropagation();
    const sx = e.clientX;
    const sy = e.clientY;
    const from = nudge;
    const move = (ev: PointerEvent) =>
      // **Divided by the zoom**, or a node at 50% travels twice as far as the cursor.
      setNudge({ x: from.x + (ev.clientX - sx) / zoom, y: from.y + (ev.clientY - sy) / zoom });
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
        left: `${Math.round(placed.x + nudge.x)}px`,
        top: `${Math.round(placed.y + nudge.y)}px`,
        width: placed.width,
      }}
      className="absolute flex rounded-r border border-line-2 border-l-0 bg-surface
                 cursor-grab active:cursor-grabbing
                 hover:shadow-[0_2px_10px_var(--shadow)]
                 data-[selected]:shadow-[0_0_0_2px_var(--ink)]
                 data-[dim]:opacity-20 transition-[box-shadow,opacity]"
    >
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
            <span className="text-secondary text-ink-2">
              {step.settings.length} {step.settings.length === 1 ? "setting" : "settings"}
            </span>
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
