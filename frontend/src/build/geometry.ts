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

/** `NODE_W` in `layout.py`. */
export const NODE_W = 232;
/** `HEAD_H` — the node's title band, above any ports. */
export const HEAD_H = 34;
/** `PORT_ROW` — how much height one row of ports needs. */
export const PORT_ROW = 22;
/** `MIN_H` — a node is never shorter than this. */
export const MIN_H = 56;
/** `COL_PITCH` — horizontal spacing when the client has to place a node itself. */
export const COL_PITCH = 276;
/** `ROW_PITCH` — vertical spacing for the same. */
export const ROW_PITCH = 128;
/** The radius of an elbow's rounded corner. */
export const CORNER = 7;

export type Point = { x: number; y: number };
export type Positions = Record<string, Point>;

/** How tall a node with this many ports must be.
 *
 * `layout.py::_height`, and it counts **declared** ports — the bug the operator found was this
 * counting wired ones, which left a node sized for one port row with three chevrons on it.
 */
export function heightFor(ins: number, outs: number): number {
  return Math.max(MIN_H, HEAD_H + Math.max(ins, outs, 1) * PORT_ROW);
}

/** Where a port sits along a node's edge.
 *
 * `portX(count, i) = NODE_W * (i + 1) / (count + 1)` — the same formula in `layout.py`,
 * `dashboard.html` and `Port.tsx`. All three must agree or a wire misses its chevron.
 */
export function portX(width: number, count: number, index: number): number {
  return (width * (index + 1)) / (count + 1);
}


/** One wire, as an orthogonal elbow between two points.
 *
 * `layout.py` emits the same shape: down, across at the midpoint, down. **A straight drop is two
 * points, not four** — when the ports line up the two corners are the same coordinate, and
 * emitting them anyway hands the renderer a zero-length segment to round, which turns a 7px
 * corner into a visible nick on a wire that should be plumb.
 */
export function elbow(start: Point, end: Point): Point[] {
  const mid = Math.round((start.y + end.y) / 2);
  return start.x === end.x
    ? [start, end]
    : [start, { x: start.x, y: mid }, { x: end.x, y: mid }, end];
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
