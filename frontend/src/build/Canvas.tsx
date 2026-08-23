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
  onDragOver,
  onDrop,
  children,
  footer,
}: {
  view: View;
  onWheel: (e: React.WheelEvent) => void;
  onPointerDown: (e: React.PointerEvent) => void;
  /** Dropping a module from the palette. Omitted where the canvas is read-only. */
  onDragOver?: (e: React.DragEvent) => void;
  onDrop?: (e: React.DragEvent) => void;
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
      onDragOver={onDragOver}
      onDrop={onDrop}
      // **`flex-1 min-h-0`, and both halves matter.** The canvas sits in a flex column under
      // the provenance bar, and everything inside it is absolutely positioned — so without
      // `flex-1` it sizes to its content, which is nothing, and the graph renders into a
      // zero-height box. `min-h-0` because a flex child's default `min-height:auto` refuses to
      // shrink below its content and would push the bar off instead of scrolling.
      // **`select-none`.** Dragging a node is a pointer drag over text, and without this the browser
      // treats it as a selection gesture — every label on the canvas highlights blue as you move
      // a box, and the highlight survives the drop.
      className="relative flex-1 min-h-0 overflow-hidden bg-paper select-none
                 cursor-grab active:cursor-grabbing
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
