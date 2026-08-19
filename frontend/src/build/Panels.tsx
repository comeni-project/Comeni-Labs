import { useCallback, useRef, useState } from "react";

/** A side panel that drags to resize and collapses to a rail.
 *
 * **The ranges are `dashboard.md` §4's, not defaults**: 190–430 left, 280–560 right, collapsing
 * to a 42px stub with a vertical label. A panel draggable to 40px is a panel draggable into
 * uselessness, which is why the clamp is part of the design rather than a nicety.
 *
 * **The collapsed stub keeps its count.** That is the design's own rule and the reason this
 * component takes a `badge`: hiding the panel must never hide what is blocking your run.
 */
export const RAIL = 42;

export function useWidth(initial: number, min: number, max: number) {
  const [width, setWidth] = useState(initial);
  const [collapsed, setCollapsed] = useState(false);
  const from = useRef({ x: 0, w: initial });

  const onPointerDown = useCallback(
    (e: React.PointerEvent, side: "left" | "right") => {
      e.preventDefault();
      from.current = { x: e.clientX, w: width };
      const move = (ev: PointerEvent) => {
        const delta = side === "left" ? ev.clientX - from.current.x : from.current.x - ev.clientX;
        setWidth(Math.min(max, Math.max(min, from.current.w + delta)));
      };
      const up = () => {
        window.removeEventListener("pointermove", move);
        window.removeEventListener("pointerup", up);
      };
      window.addEventListener("pointermove", move);
      window.addEventListener("pointerup", up);
    },
    [width, min, max],
  );

  return { width, collapsed, setCollapsed, onPointerDown };
}

/** The drag handle. **Keyboard-operable**, because `dashboard.md` §9 says the accessibility
 * floor is met and a resizer nobody can reach by tab would drop below it. */
export function Grip({
  side,
  onPointerDown,
  onCollapse,
  onNudge,
}: {
  side: "left" | "right";
  onPointerDown: (e: React.PointerEvent) => void;
  onCollapse: () => void;
  onNudge: (by: number) => void;
}) {
  return (
    <div
      data-testid={`resize-${side}`}
      role="separator"
      aria-orientation="vertical"
      tabIndex={0}
      onPointerDown={onPointerDown}
      onDoubleClick={onCollapse}
      onKeyDown={(e) => {
        if (e.key === "ArrowLeft") onNudge(side === "left" ? -16 : 16);
        if (e.key === "ArrowRight") onNudge(side === "left" ? 16 : -16);
      }}
      className="w-[5px] shrink-0 cursor-col-resize bg-transparent hover:bg-line-2
                 focus-visible:bg-pea focus-visible:outline-none transition-colors"
    />
  );
}
