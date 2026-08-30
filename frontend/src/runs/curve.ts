/** A `Series` curve as an SVG path — **stepped, always.**
 *
 * ═══ THE RULE THIS FILE EXISTS FOR ══════════════════════════════════════════════════════
 *
 * **Smoothness is the visual grammar of *I measured this*.** `wiener_core.series` decides which
 * curves are honest and labels them `exact` or `derived`; this is where that labelling either
 * survives contact with a renderer or is quietly lost. A `derived` curve is a per-task total
 * spread uniformly over its window — area-true and **shape-false** — so drawing it as a smooth
 * spline is a picture of measurements nobody took.
 *
 * The failure mode is one line of somebody else's library. `curveMonotoneX` is the default in
 * most chart wrappers, it looks better, and it converts an honest label into a lie without
 * touching the data. `curve.test.ts` refuses a path containing a bezier command.
 *
 * **The exact curves are steps too**, and not as a house style: a reservation genuinely *is* a
 * step function. Four cpus are held, then twelve, then four — there is no instant at which six
 * were reserved, and a line sloping between them draws one.
 *
 * ═══ AND THE SWEEP IS NOT RE-DONE HERE ═════════════════════════════════════════════════
 *
 * `Series.points` is already exact at every breakpoint — `+delta`, `−delta`, sort, prefix-sum,
 * in a pure package. **Binning is the renderer's job and it happens after**, never before: bin
 * first and the exactness the pure layer went to trouble for is gone, and no test in phase 4
 * would notice. `Series.bin_ms` is sized off the run's own recorded span for exactly this, and
 * nothing here needs it yet — the point count of a real run is small enough to draw whole.
 */

export type Point = { at_ms: number; value: number };

/** The step path for a curve, in an `x0 y0 w h` box.
 *
 * `H` then `V`: hold the value across the interval, then jump at the boundary. That is the
 * shape of the thing being drawn, not a rendering preference.
 *
 * `close` adds the baseline return that makes it fillable as an area, ending at `xend` — which
 * is what lets a derived curve stop at the last completion rather than run to the right edge
 * pretending to know something about the gap.
 */
export function stepPath(
  points: Point[],
  box: { x0: number; y0: number; w: number; h: number },
  scale: { xmax: number; ymax: number; xmin?: number },
  options: { close?: boolean; xend?: number } = {},
): string {
  if (points.length === 0) return "";

  const xmin = scale.xmin ?? 0;
  const span = Math.max(scale.xmax - xmin, 1);
  const top = Math.max(scale.ymax, Number.EPSILON);
  const X = (at: number) => box.x0 + ((at - xmin) / span) * box.w;
  const Y = (value: number) => box.y0 + box.h - (value / top) * box.h;

  let path = `M${X(points[0].at_ms).toFixed(1)} ${Y(points[0].value).toFixed(1)}`;
  for (let i = 1; i < points.length; i += 1) {
    // Hold, then jump. Never interpolate between two breakpoints — the value did not pass
    // through the space in between.
    path += `H${X(points[i].at_ms).toFixed(1)}V${Y(points[i].value).toFixed(1)}`;
  }

  const last = options.xend ?? points[points.length - 1].at_ms;
  path += `H${X(last).toFixed(1)}`;
  if (options.close) path += `V${(box.y0 + box.h).toFixed(1)}H${X(points[0].at_ms).toFixed(1)}Z`;
  return path;
}

/** The largest value a curve reaches, with a floor so a flat-zero curve still has an axis. */
export function ceilingOf(points: Point[]): number {
  return points.reduce((top, point) => Math.max(top, point.value), 0) || 1;
}
