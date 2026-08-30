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
  onPointerMove,
  onClick,
  onContextMenu,
  children,
  footer,
  grid = false,
}: {
  view: View;
  onWheel: (e: React.WheelEvent) => void;
  onPointerDown: (e: React.PointerEvent) => void;
  /** Tracked only while a wire is being dragged, so a still canvas costs nothing. */
  onPointerMove?: (e: React.PointerEvent) => void;
  /** A click that reached the canvas rather than a node — the caller decides what that means. */
  onClick?: (e: React.MouseEvent) => void;
  /** Dropping a module from the palette. Omitted where the canvas is read-only. */
  /** Right-click on empty canvas. **The place you would reach for *add a step here* had
   *  nothing** — nodes had a menu and the canvas did not (the 2026-08-29 walk). */
  onContextMenu?: (e: React.MouseEvent) => void;
  children?: React.ReactNode;
  footer?: React.ReactNode;
  /** The dotted surface. **A measuring surface, and it exists only while something is being
   *  moved** — `impl-geom`: *a permanent grid is the loudest hobby-editor signal there is.*
   *
   *  It defaulted to `true`, and this docstring argued for that: *it is an invitation; a grid
   *  says things can be placed here, which is true of the builder and false of a finished run.*
   *  The invitation is real and it belongs to the **gesture** rather than to the resting screen.
   *  The builder passes `grid={moving}`; the run graph passes nothing and still gets none. */
  grid?: boolean;
}) {
  const box = useRef<HTMLDivElement>(null);

  return (
    <div
      ref={box}
      data-testid="canvas"
      onWheel={onWheel}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onClick={onClick}
      onContextMenu={onContextMenu}
      // **`flex-1 min-h-0`, and both halves matter.** The canvas sits in a flex column under
      // the provenance bar, and everything inside it is absolutely positioned — so without
      // `flex-1` it sizes to its content, which is nothing, and the graph renders into a
      // zero-height box. `min-h-0` because a flex child's default `min-height:auto` refuses to
      // shrink below its content and would push the bar off instead of scrolling.
      // **`select-none`.** Dragging a node is a pointer drag over text, and without this the browser
      // treats it as a selection gesture — every label on the canvas highlights blue as you move
      // a box, and the highlight survives the drop.
      className={`relative flex-1 min-h-0 overflow-hidden bg-paper select-none
                  cursor-grab active:cursor-grabbing
                  ${grid
                    ? "[background-image:radial-gradient(var(--line)_1px,transparent_1px)]"
                    : ""}`}
      style={grid
        ? { backgroundSize: `${GRID * view.k}px ${GRID * view.k}px`,
            backgroundPosition: `${view.x}px ${view.y}px` }
        // The artboard insets the graph rather than tiling it — a figure in a well.
        : { boxShadow: "var(--well)" }}
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
