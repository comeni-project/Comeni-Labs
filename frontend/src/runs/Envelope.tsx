import { useQuery } from "@tanstack/react-query";

import { get } from "../wiener/api/client";
import { ceilingOf, stepPath, type Point } from "./curve";
import { bytes, shortBytes } from "./units";

type Curve = { name: string; kind: "exact" | "derived"; unit: string; points: Point[] };
type Series = {
  curves: Curve[];
  from_ms: number;
  to_ms: number;
  bin_ms: number;
  open: boolean;
  reported_resources: boolean;
};

const W = 620;
const H = 54;

/** How a curve's value is spelled on its own axis. `bytes/s` is a rate and gets its suffix. */
function spell(value: number, unit: string): string {
  if (unit === "bytes") return bytes(value);
  if (unit === "bytes/s") return `${shortBytes(value)}/s`;
  if (unit === "cpus") return `${Math.round(value * 10) / 10}`;
  return String(Math.round(value));
}

/** One curve, on its own y-axis, sharing the run's x-axis with every other row.
 *
 * **Its own axis, deliberately.** `cpus`, `bytes` and `bytes/s` do not share a scale, and
 * overlaying them would need a second axis nobody can read or a normalisation that makes every
 * curve look the same height. Stacked rows share the thing that actually matters — **time** —
 * so a spike in one row sits directly above the spike in another, which is the comparison the
 * artboard's overlay was for.
 */
function Row({ curve, series }: { curve: Curve; series: Series }) {
  const derived = curve.kind === "derived";
  const top = ceilingOf(curve.points);
  const scale = { xmin: series.from_ms, xmax: series.to_ms, ymax: top };
  const box = { x0: 0, y0: 0, w: W, h: H };

  const line = stepPath(curve.points, box, scale);
  const area = stepPath(curve.points, box, scale, { close: true });

  // **Where the curve stops knowing.** A derived curve is built from completed attempts only,
  // so its last point is the last completion — everything right of that is a window nothing
  // reported on, and it is HATCHED rather than drawn. An exact curve runs to the last recorded
  // boundary and only hatches when the run is still open, which is the other reason a right
  // edge can be high.
  const lastKnown = curve.points.length
    ? curve.points[curve.points.length - 1].at_ms
    : series.from_ms;
  const gap = derived || series.open
    ? ((series.to_ms - lastKnown) / Math.max(series.to_ms - series.from_ms, 1)) * W
    : 0;

  return (
    <div className="flex flex-col gap-1">
      <span className="flex items-baseline gap-2">
        <span className="text-secondary text-ink-2">{curve.name}</span>
        {/* **The label travels with the curve**, not only in a legend — a screenshot with the
            legend cropped off is the common way this page is shared, and `derived` is the word
            that stops somebody reading an invented shape as a measured one. */}
        {derived && (
          <span className="text-label text-ink-3 border border-line rounded-[3px] px-1.5
                           py-px leading-[1.4]"
                title="a per-task total spread uniformly over its window — the area is true and
                       the shape is invented">
            derived
          </span>
        )}
        <span className="ml-auto font-data text-label text-ink-3 tabular-nums">
          peak {spell(top, curve.unit)}
        </span>
      </span>

      {/* **`preserveAspectRatio="none"`, and without it the chart drew at half width.** The
          element is `width="100%"` over a fixed 620-wide viewBox, so the default `xMidYMid
          meet` scaled the drawing to fit the 54px HEIGHT and centred it — leaving a third of
          the panel empty on each side. Nothing in the code says 620px; it said *fit*, and fit
          against a fixed height means do not use the width.

          `none` distorts strokes horizontally, which `vector-effect: non-scaling-stroke` on
          the paths undoes. A step chart has only vertical and horizontal segments, so there is
          no diagonal to skew. */}
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" height={H} role="img"
           preserveAspectRatio="none"
           aria-label={`${curve.name}, ${curve.kind}`}
           data-testid={`curve-${curve.name.replace(/\s+/g, "-")}`}
           data-kind={curve.kind}
           data-path={line}
           style={{ display: "block", overflow: "visible" }}>
        <defs>
          <pattern id={`hatch-${curve.name.replace(/\s+/g, "-")}`} width="7" height="7"
                   patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
            <line x1="0" y1="0" x2="0" y2="7" stroke="var(--ink-3)" strokeWidth="1"
                  strokeOpacity=".26" />
          </pattern>
        </defs>

        {/* A derived curve is an AREA and an exact one is a LINE. Two different marks for two
            different claims — colour alone would not survive a monochrome print or a reader who
            never learned which hue meant what. */}
        {derived ? (
          <>
            <path vectorEffect="non-scaling-stroke" d={area} fill="var(--measured)" fillOpacity=".16" />
            <path vectorEffect="non-scaling-stroke" d={line} fill="none" stroke="var(--measured)" strokeWidth="1.25"
                  strokeOpacity=".55" strokeDasharray="4 3" />
          </>
        ) : (
          <>
            <path vectorEffect="non-scaling-stroke" d={area} fill="var(--pea)" fillOpacity=".07" />
            <path vectorEffect="non-scaling-stroke" d={line} fill="none" stroke="var(--pea)" strokeWidth="1.5" />
          </>
        )}

        {gap > 1 && (
          <>
            <rect x={W - gap} y="0" width={gap} height={H}
                  fill={`url(#hatch-${curve.name.replace(/\s+/g, "-")})`} />
            <line x1={W - gap} y1="0" x2={W - gap} y2={H} stroke="var(--ink-3)"
                  strokeWidth="1" strokeDasharray="3 3" />
          </>
        )}
      </svg>
    </div>
  );
}

/** What this run held over time — and only the curves the record can honestly support.
 *
 * **`wiener_core.series` decides what is drawable; this decides how.** The split matters: every
 * judgement about whether a scalar distributes over its window lives in a pure package with a
 * test suite, and none of it is re-litigated here. There is no memory-over-time curve because
 * the API does not offer one — summing peaks across live attempts describes an instant that
 * never happened — and this component has no way to invent it.
 */
export function Envelope({ runId, live }: { runId: string; live: boolean }) {
  const series = useQuery({
    queryKey: ["series", runId],
    queryFn: () => get<Series>(`/api/runs/${runId}/series`),
    refetchInterval: live ? 6_000 : false,
  });

  if (series.isPending || series.isError) return null;
  const data = series.data;

  // **Absence is absence.** A run launched without `trace.enabled` recorded no resource fields
  // at all (§4.3 finding 6), and four empty charts would claim a run that used nothing. One
  // sentence, and the countable curve — which is still exact and still honest — stays.
  // `?.` rather than `.`: a panel that throws during render takes the WHOLE run page with it,
  // and there is no error boundary above this. Nothing to draw is a legitimate answer and a
  // shape this component does not recognise reaches the same one — the header, the failure
  // banner and every tab stay up.
  if (!data?.curves?.length) return null;

  return (
    <section className="bg-panel border border-line rounded-[var(--r)] shadow-e2 p-4
                        flex flex-col gap-4">
      <span className="flex items-baseline gap-3">
        <h2 className="text-body font-semibold text-ink m-0">what this run held</h2>
        {data.open && (
          // **The right edge means two different things.** A curve ending high because work is
          // in flight reads identically to one ending high because the run stopped badly, and
          // only this says which.
          <span className="text-label text-ink-3">
            still in flight — the right edge is not an ending
          </span>
        )}
      </span>

      {!data.reported_resources && (
        <p className="text-secondary text-ink-3 m-0">
          This run reported no resource figures. It was launched without Nextflow's
          <code className="font-data mx-1">trace.enabled</code>, so nothing recorded what any
          task reserved or touched — which is different from a run that used nothing.
        </p>
      )}

      {data.curves.map((curve) => (
        <Row key={curve.name} curve={curve} series={data} />
      ))}
    </section>
  );
}
