import { useCallback, useRef, useState } from "react";

/** Pan and zoom, ported from `docs/design/dashboard.html` rather than reinvented.
 *
 * **Every constant here is the design's.** `0.3`–`2.2` clamp, `deltaY * 0.0016` per wheel notch,
 * a 22px dot grid that scales with the view so the surface reads as a surface rather than a
 * backdrop. Picking my own would have made this a different canvas that happened to look similar.
 *
 * `zoomAt` keeps the point under the cursor fixed — that is what makes a wheel feel like zooming
 * rather than like scaling — and it is three lines because the design already worked them out.
 */
export const MIN_K = 0.3;
export const MAX_K = 2.2;

export type View = { x: number; y: number; k: number };

/** **The canvas opens with room for what feeds the pipeline.**
 *
 * `dag-core` lays the graph out from x≈40, and an input socket is drawn to the LEFT of the step
 * it feeds — at roughly x = −200, which is off-screen at `x: 0`. The pipeline looked complete and
 * its inputs were simply not on the canvas; the only hint was a dashed line disappearing at the
 * left edge, which is worse than drawing nothing.
 *
 * A pan offset rather than a layout change: an entry channel is not a node, and giving one a
 * position in `dag-core` would make the canvas and the emitted `.nf` disagree about what a step
 * is. This moves the camera, which is what was wrong.
 *
 * 250 = the socket's 150 plus its 90 gap, plus a little air. `reset` returns here, not to
 * origin, so the same thing is true after somebody presses it.
 */
const START: View = { x: 250, y: 20, k: 1 };

export function useView() {
  const [view, setView] = useState<View>(START);
  const panning = useRef(false);

  const zoomAt = useCallback((cx: number, cy: number, next: number) => {
    setView((v) => {
      const k = Math.min(MAX_K, Math.max(MIN_K, next));
      return { x: cx - (cx - v.x) * (k / v.k), y: cy - (cy - v.y) * (k / v.k), k };
    });
  }, []);

  const onWheel = useCallback(
    (e: React.WheelEvent) => {
      const r = e.currentTarget.getBoundingClientRect();
      setView((v) => {
        const k = Math.min(MAX_K, Math.max(MIN_K, v.k * (1 - e.deltaY * 0.0016)));
        const cx = e.clientX - r.left;
        const cy = e.clientY - r.top;
        return { x: cx - (cx - v.x) * (k / v.k), y: cy - (cy - v.y) * (k / v.k), k };
      });
    },
    [],
  );

  const onPointerDown = useCallback((e: React.PointerEvent) => {
    // Only empty space pans. A node drag and a canvas pan are different gestures and the design
    // separates them by target, not by modifier.
    if ((e.target as HTMLElement).closest("[data-node],[data-zoomer]")) return;
    panning.current = true;
    const sx = e.clientX;
    const sy = e.clientY;
    let origin: View | null = null;
    setView((v) => {
      origin = v;
      return v;
    });
    const move = (ev: PointerEvent) => {
      if (!panning.current || !origin) return;
      setView((v) => ({ ...v, x: origin!.x + ev.clientX - sx, y: origin!.y + ev.clientY - sy }));
    };
    const up = () => {
      panning.current = false;
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  }, []);

  const reset = useCallback(() => setView(START), []);
  const nudge = useCallback((by: number) => setView((v) => {
    const k = Math.min(MAX_K, Math.max(MIN_K, v.k + by));
    return { ...v, k };
  }), []);

  /** Fit the graph in the viewport, with a margin, never zoomed past 1. */
  const fit = useCallback((w: number, h: number, vw: number, vh: number) => {
    if (!w || !h || !vw || !vh) return;
    const k = Math.min(1, Math.max(MIN_K, Math.min((vw - 48) / w, (vh - 48) / h)));
    setView({ k, x: (vw - w * k) / 2, y: 24 });
  }, []);

  return { view, onWheel, onPointerDown, zoomAt, reset, nudge, fit };
}
