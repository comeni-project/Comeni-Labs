import { useRef } from "react";

import { GRID, type View } from "./useView";

/** The surface. Pan by dragging empty space, wheel to zoom toward the cursor.
 *
 * **The dot grid scales with the view**, which is `dashboard.html`'s `applyView` — a grid that
 * stayed fixed while the content moved would read as a backdrop behind the graph rather than as
 * the surface the graph sits on, and the whole feel of a canvas is that difference.
 *
 * Phase 3 renders nothing inside it. That is the deliverable, not an omission.
 */
export function Canvas({
  view,
  onWheel,
  onPointerDown,
  children,
  footer,
}: {
  view: View;
  onWheel: (e: React.WheelEvent) => void;
  onPointerDown: (e: React.PointerEvent) => void;
  children?: React.ReactNode;
  footer?: React.ReactNode;
}) {
  const box = useRef<HTMLDivElement>(null);

  return (
    <div
      ref={box}
      data-testid="canvas"
      onWheel={onWheel}
      onPointerDown={onPointerDown}
      className="relative overflow-hidden bg-paper cursor-grab active:cursor-grabbing
                 [background-image:radial-gradient(var(--line)_1px,transparent_1px)]"
      style={{
        backgroundSize: `${GRID * view.k}px ${GRID * view.k}px`,
        backgroundPosition: `${view.x}px ${view.y}px`,
      }}
    >
      <div
        data-testid="stage"
        className="absolute top-0 left-0 origin-top-left"
        style={{ transform: `translate(${view.x}px, ${view.y}px) scale(${view.k})` }}
      >
        {children}
      </div>
      {footer}
    </div>
  );
}
