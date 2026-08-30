import { useRef } from "react";

import { Field } from "../ui/Field";
import { type View } from "./useView";

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
      className="relative flex-1 min-h-0 overflow-hidden bg-paper select-none
                 cursor-grab active:cursor-grabbing"
      style={{ boxShadow: "var(--well)" }}
    >
      {/* ── 1. THE FIELD. Anchored to the FRAME, and it does not pan. ──────────────────────
          `impl-geom` keeps the three layers apart on purpose: *the arc field is anchored to the
          VIEWPORT and does not pan. It is ambience.* Panning it would make it a very large
          picture behind the graph rather than the light the graph sits in. */}
      <Field origin="corner" within />

      {/* ── 2. THE GRID. Pans WITH the nodes, and exists only while one is moving. ────────
          `impl-geom` again: *the millimetre grid pans WITH the nodes. It is a measuring
          surface.* And `n-bcanvas`: *a permanent grid is the loudest hobby-editor signal there
          is* — so it fades in on pointer-down and out on release.

          **Three rulings at 1:5:10 — 8 / 40 / 80** — which is what makes it read as a measuring
          surface rather than as wallpaper. It was a single ruling of DOTS: one spacing carries
          no sense of scale, and dots cannot show an alignment, which is the only thing a grid
          is for during a drag. The opacities are the artboard's, and the coarsest is loudest so
          the eye lands on the 80s first and reads the 8s only when it needs them. */}
      <div
        data-testid="grid"
        aria-hidden
        className="absolute inset-0 pointer-events-none transition-opacity"
        style={{
          opacity: grid ? 1 : 0,
          transitionDuration: "var(--t)",
          backgroundImage: [
            "linear-gradient(var(--grid-1) 1px, transparent 1px)",
            "linear-gradient(90deg, var(--grid-1) 1px, transparent 1px)",
            "linear-gradient(var(--grid-2) 1px, transparent 1px)",
            "linear-gradient(90deg, var(--grid-2) 1px, transparent 1px)",
            "linear-gradient(var(--grid-3) 1px, transparent 1px)",
            "linear-gradient(90deg, var(--grid-3) 1px, transparent 1px)",
          ].join(", "),
          backgroundSize: [80, 80, 40, 40, 8, 8]
            .map((n, i) => `${n * view.k}px ${[80, 80, 40, 40, 8, 8][i] * view.k}px`)
            .join(", "),
          backgroundPosition: `${view.x}px ${view.y}px`,
        }}
      />

      <div
        data-testid="stage"
        className="absolute top-0 left-0 origin-top-left"
        style={{ transform: `translate(${view.x}px, ${view.y}px) scale(${view.k})` }}
      >
        {children}
      </div>

      {/* ── 3. THE REGISTRATION MARKS. Fixed to the frame's bounds. ───────────────────────
          Sixteen pixels in from each corner, and they are the third of `impl-geom`'s three
          layers — the one that says where the instrument's frame is. They belong to the frame
          rather than to the content, so they do not pan and do not scale. */}
      {([["left", "top"], ["right", "top"], ["left", "bottom"], ["right", "bottom"]] as const)
        .map(([x, y]) => (
          <div key={`${x}-${y}`} aria-hidden data-testid="registration"
               className="absolute w-4 h-4 pointer-events-none"
               style={{
                 [x]: 16, [y]: 16,
                 [`border${x === "left" ? "Left" : "Right"}Width`]: 1,
                 [`border${x === "left" ? "Left" : "Right"}Style`]: "solid",
                 [`border${x === "left" ? "Left" : "Right"}Color`]: "var(--mark)",
                 [`border${y === "top" ? "Top" : "Bottom"}Width`]: 1,
                 [`border${y === "top" ? "Top" : "Bottom"}Style`]: "solid",
                 [`border${y === "top" ? "Top" : "Bottom"}Color`]: "var(--mark)",
               } as React.CSSProperties}
          />
        ))}

      {footer}
    </div>
  );
}
