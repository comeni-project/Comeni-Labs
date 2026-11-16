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
export const NODE_W = 145;
/** `NODE_H` — a step card with one port a side; a card with more grows (`nodeHeight`). */
export const NODE_H = 64;
/** `HEAD_H` — the node's title band: what the step does, then its tool and version. */
export const HEAD_H = 44;
/** `PORT_ROW` — the height of one port row INSIDE a node. It no longer sizes the node. */
export const PORT_ROW = 19;
/** `PORT_GAP` — between one port and the next along an edge. */
export const PORT_GAP = 18;
/** `SPINE` — **every symbol connects here.** The one derivation, and `impl-geom`'s rule:
 *  *port positions are DERIVED from node geometry in one place. Never write a coordinate
 *  twice.* Writing an endpoint separately from the node it belongs to is what put every wire
 *  6px above its port on the 2026-08-29 walk. */
export const SPINE = 50;
/** `SECOND` — a secondary input, 22 below the spine. */
export const SECOND = 68;
/** `RANK_PITCH` — between one rank and the next, ALONG the flow. Left to right since phase 6. */
export const RANK_PITCH = 200;
/** `SIBLING_PITCH` — between two nodes sharing a rank, ACROSS the flow. */
export const SIBLING_PITCH = 120;
/** The radius of an elbow's rounded corner. */
export const CORNER = 7;
/** Between a step and the measuring step hung under it (#517). */
export const HANG_GAP = 24;
/** A measuring step's pill (#517, the board's *Genome length*): its size, and its ports at its middle. */
export const MEASURE_W = 140;
export const MEASURE_H = 42;
/** How far a hung step's wire runs out before it turns, and in before its port. */
export const HANG_REACH = 14;

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

/** **A node's height for its larger side's port count** (#494): every port's row, at its
 *  anchor, inside the node above the footer. `node_height` in `dag_core.layout`, read off this
 *  source by `test_the_canvas_and_the_layout_agree_on_a_steps_height`. */
export function nodeHeight(ports: number): number {
  return Math.max(NODE_H, 64 + PORT_GAP * (ports - 1));
}

/** A step's height from its ports, as the canvas draws it. */
export function heightOf(ports: { side: string }[]): number {
  const ins = ports.filter((p) => p.side === "in").length;
  return nodeHeight(Math.max(1, ins, ports.length - ins));
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
  // **The turn sits in the gap before the target's column** (issue 388). Between neighbouring
  // columns that is the midpoint; a wire passing a column turned at its midpoint, inside a step,
  // and its riser showed above and below that step as a line joining two unrelated steps.
  if (end.x <= start.x) {
    // **Into a step hung under its source** (#517): out to the right, down into the gap above
    // the hung step, back along it, and into the port from the left. `hung_wire` in dag_core.
    const below = end.y - Math.round(MEASURE_H / 2) - HANG_GAP / 2;
    const out = start.x + HANG_REACH;
    const back = end.x - HANG_REACH;
    return [start, { x: out, y: start.y }, { x: out, y: below }, { x: back, y: below }, { x: back, y: end.y }, end];
  }
  const mid = Math.max(Math.round((start.x + end.x) / 2), end.x - (RANK_PITCH - NODE_W) / 2);
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
