/** Where things are on the canvas, computed **in the browser**.
 *
 * **Why this exists, given that layout is Python's job.** It still is: `mendel_compiler.layout`
 * computes the canonical arrangement, and `CLAUDE.md`'s reason holds — the picture of a *built*
 * pipeline must be as deterministic as the emitted `.nf`, or two people reading the same
 * artifact see two different graphs.
 *
 * What is not Python's job is **where a box sits while you are dragging it**. Asking the server
 * to re-lay-out on every edit is what made the canvas flicker: a new query key per keystroke,
 * `data` undefined until it returned, and the whole graph unmounting and remounting in between.
 * It also made the arrangement jump under the hand — you drop a module and every other node
 * moves, because the server re-ranked the whole DAG.
 *
 * So: **the server seeds, the client owns.** A node the client has never placed takes the
 * server's coordinates; from the first drag it keeps the client's. `tidy()` throws the client's
 * positions away and takes the server's again, which is the deterministic arrangement on demand
 * rather than on every gesture.
 *
 * The constants below are `layout.py`'s, and that duplication is the cost of the split. It is
 * bounded — six numbers — and `test_the_canvas_and_the_layout_agree_on_geometry` holds them
 * together from the Python side rather than trusting the comment.
 */

/** `NODE_W` — **one symbol for every process, and its size is load-bearing.**
 *
 * `impl-geom` on the redesign canvas: *variable heights put a jog between every pair and the
 * whole thing reads sloppy again.* The height used to be computed from the port count. */
export const NODE_W = 172;
/** `NODE_H`. Every process node, always. */
export const NODE_H = 112;
/** `HEAD_H` — the node's title band, where the name and the `⋯` sit. */
export const HEAD_H = 28;
/** `PORT_ROW` — the height of one port row INSIDE a node. It no longer sizes the node. */
export const PORT_ROW = 19;
/** `PORT_GAP` — between one port and the next along an edge. */
export const PORT_GAP = 22;
/** `SPINE` — **every symbol connects here.** The one derivation, and `impl-geom`'s rule:
 *  *port positions are DERIVED from node geometry in one place. Never write a coordinate
 *  twice.* Writing an endpoint separately from the node it belongs to is what put every wire
 *  6px above its port on the 2026-08-29 walk. */
export const SPINE = 56;
/** `SECOND` — a secondary input, 22 below the spine. */
export const SECOND = 78;
/** `RANK_PITCH` — between one rank and the next, ALONG the flow. Left to right since phase 6. */
export const RANK_PITCH = 224;
/** `SIBLING_PITCH` — between two nodes sharing a rank, ACROSS the flow. */
export const SIBLING_PITCH = 170;
/** The radius of an elbow's rounded corner. */
export const CORNER = 7;

export type Point = { x: number; y: number };
export type Positions = Record<string, Point>;

/** Where a port sits along a node's edge, **from the node's own top-left.**
 *
 * `_port_offset` in `dag_core.layout`, and the whole of it: the first port is on the spine and
 * each one after it steps down by `PORT_GAP`.
 *
 * **It used to spread ports evenly across the edge**, which made a port's position depend on how
 * many siblings it had — so declaring one more input moved every wire already drawn. Anchoring
 * the first on the spine is what makes the main chain dead straight.
 */
export function portOffset(index: number): number {
  return SPINE + index * PORT_GAP;
}

/** One wire, as an orthogonal elbow between two points.
 *
 * `dag_core.layout` emits the same shape: **across, over at the midpoint, across** — H / V / H
 * since the flow turned left-to-right in phase 6. `impl-geom`: *right angles read engineered.*
 *
 * **A straight run is two points, not four** — when the ports line up the two corners are the
 * same coordinate, and emitting them anyway hands the renderer a zero-length segment to round,
 * which turns a 7px corner into a visible nick on a wire that should be straight.
 */
export function elbow(start: Point, end: Point): Point[] {
  const mid = Math.round((start.x + end.x) / 2);
  return start.y === end.y
    ? [start, end]
    : [start, { x: mid, y: start.y }, { x: mid, y: end.y }, end];
}

/** An SVG path for an elbow, with rounded corners. */
export function path(points: Point[]): string {
  if (points.length < 3) {
    return `M${points[0].x},${points[0].y} L${points[points.length - 1].x},${
      points[points.length - 1].y
    }`;
  }
  let out = `M${points[0].x},${points[0].y}`;
  for (let i = 1; i < points.length - 1; i += 1) {
    const before = points[i - 1];
    const here = points[i];
    const after = points[i + 1];
    const r = Math.min(
      CORNER,
      Math.abs(here.x - before.x || here.y - before.y) / 2,
      Math.abs(after.x - here.x || after.y - here.y) / 2,
    );
    const inX = Math.sign(here.x - before.x);
    const inY = Math.sign(here.y - before.y);
    const outX = Math.sign(after.x - here.x);
    const outY = Math.sign(after.y - here.y);
    out += ` L${here.x - inX * r},${here.y - inY * r}`;
    out += ` Q${here.x},${here.y} ${here.x + outX * r},${here.y + outY * r}`;
  }
  const last = points[points.length - 1];
  return `${out} L${last.x},${last.y}`;
}
