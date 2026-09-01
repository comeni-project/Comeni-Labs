import { useQuery } from "@tanstack/react-query";

import { get } from "../wiener/api/client";
import { seconds } from "./units";

/** Where every attempt sat in time — Plan 6 phase 3, `.design/RunView.dc.html`'s timeline band.
 *
 * **Every rule about what to draw lives in `wiener_core.timeline`, not here.** How bars pack,
 * when the stack stops, what an open bar means — all of it is decided by a pure function that
 * reads no clock, so the picture is as deterministic as the emitted `.nf`. This file positions
 * rectangles.
 *
 * The one thing that IS this file's: **an open bar is extended to the right edge.** The verb
 * cannot do it, because `now` inside a pure fold makes the same events draw differently every
 * second — the rule `series.py` already keeps, and `curve.ts` already renders the other half
 * of.
 */

type Bar = {
  task_id: number; attempt: number; status: string;
  start_ms: number; end_ms: number | null; row: number;
};
type Lane = { process: string; declared: boolean; bars: Bar[]; rows: number; dense: number };
type TimelineData = { lanes: Lane[]; from_ms: number; to_ms: number; open: boolean };

const LABELS = 150;
const W = 1230;
const BAR = 5;
const GAP = 2;
const LANE_GAP = 8;

/** **Colour is status, never process** — the artboard, and the reason is recorded there: the
 *  first draft coloured by process and a finished STAR task was indistinguishable from a
 *  running one. The lane label already carries identity. */
/** Round intervals a person reads without converting — 10s, 30s, 1m, 5m … up to 12h.
 *
 *  **The ladder is the point.** A tick at 2343m is arithmetically correct and useless; a tick
 *  at 5m is what the artboard draws and what somebody can measure a bar against. The largest
 *  interval that yields at most six ticks wins, so a 40-second stub run and a two-day run both
 *  get an axis rather than one of them collapsing.
 */
const LADDER = [
  10_000, 30_000, 60_000, 5 * 60_000, 10 * 60_000, 30 * 60_000,
  3_600_000, 6 * 3_600_000, 12 * 3_600_000, 24 * 3_600_000,
];

function tickEvery(span: number): number[] {
  const step = LADDER.find((one) => span / one <= 6) ?? LADDER[LADDER.length - 1];
  const marks: number[] = [];
  for (let at = 0; at <= span; at += step) marks.push(at);
  return marks;
}

const COLOUR: Record<string, string> = {
  COMPLETED: "var(--pea)",
  CACHED: "var(--rail)",
  RUNNING: "var(--running)",
  FAILED: "var(--fault)",
  ABORTED: "var(--fault)",
  SUBMITTED: "var(--surface-2)",
};

export function Timeline({ runId, live, onPickLane }: {
  runId: string; live: boolean;
  /** **Drill down in place** — the artboard's rule, and the reason the band knows nothing about
   *  the table: it reports which lane was picked and the page decides what that means. */
  onPickLane?: (process: string) => void;
}) {
  const query = useQuery({
    queryKey: ["timeline", runId],
    queryFn: () => get<TimelineData>(`/api/runs/${runId}/timeline`),
    refetchInterval: live ? 6_000 : false,
  });

  // `?.` throughout, for the reason `Envelope` records: a panel that throws during render takes
  // the whole run page with it and there is no error boundary above this.
  if (query.isPending || query.isError) return null;
  const data = query.data;
  if (!data?.lanes?.length) return null;

  const drawn = data.lanes.filter((lane) => lane.bars.length > 0);
  if (drawn.length === 0) return null;

  // **The right edge.** A run with something still open runs to the clock; a finished one stops
  // at its last recorded boundary. This is the only place a clock touches the timeline.
  const to = data.open ? Math.max(data.to_ms, Date.now()) : data.to_ms;
  const span = Math.max(1, to - data.from_ms);
  const x = (ms: number) => ((ms - data.from_ms) / span) * W;

  let y = 0;
  const placed = data.lanes.map((lane) => {
    const top = y;
    const height = Math.max(1, lane.rows) * (BAR + GAP);
    y += height + LANE_GAP;
    return { lane, top, height };
  });
  const total = Math.max(1, y);

  // **Round ticks, not five equal slices.** The artboard's axis reads `0m 5m 10m 15m 20m`;
  // dividing the span by five gave `0m 2343m 39s 4687m 17s …`, which is a number nobody can
  // size at a glance — the one job an axis label has. So the *interval* is chosen from a
  // human ladder and the ticks fall on multiples of it.
  const marks = tickEvery(span);

  return (
    <section data-testid="band-timeline"
             className="bg-surface border border-line rounded-[var(--r)] shadow-e2
                        flex flex-col overflow-hidden">
      <div className="shrink-0 flex items-center gap-3 px-4 py-[9px]
                      border-b border-line bg-surface-2">
        <span className="text-label uppercase tracking-[.08em] text-ink-3">timeline</span>
        <span className="ml-auto font-data text-label text-ink-3">
          {drawn.reduce((n, lane) => n + lane.bars.length, 0)} attempts ·{" "}
          {seconds(span)}
          {data.open && " · running"}
        </span>
      </div>

      <div className="p-4 overflow-x-auto">
        <svg viewBox={`0 0 ${LABELS + W} ${total + 26}`} width="100%"
             height={total + 26} role="img" aria-label="when each attempt ran">
          {marks.map((offset) => (
            <g key={offset}>
              <line x1={LABELS + x(data.from_ms + offset)} y1={0}
                    x2={LABELS + x(data.from_ms + offset)} y2={total}
                    stroke="var(--line)" strokeWidth={1} />
              <text x={LABELS + x(data.from_ms + offset)} y={total + 18} fill="var(--ink-4)"
                    fontSize={9} textAnchor="middle" className="font-data">
                {offset === 0 ? "0" : seconds(offset)}
              </text>
            </g>
          ))}

          {placed.map(({ lane, top, height }) => (
            <g key={lane.process}>
              {/* **A lane exists before the run reaches it** — the artboard's own rule, and it
                  is why an unreached process is drawn greyed rather than omitted. */}
              <text x={LABELS - 10} y={top + 8} textAnchor="end" fontSize={10}
                    className="font-data"
                    data-testid={`lane-${lane.process}`}
                    role={onPickLane && lane.bars.length ? "button" : undefined}
                    style={onPickLane && lane.bars.length ? { cursor: "pointer" } : undefined}
                    onClick={lane.bars.length ? () => onPickLane?.(lane.process) : undefined}
                    fill={lane.bars.length ? "var(--ink-2)" : "var(--ink-4)"}>
                {lane.process}
              </text>
              {lane.bars.map((bar) => {
                const end = bar.end_ms ?? to;
                return (
                  <rect
                    key={`${bar.task_id}.${bar.attempt}`}
                    data-testid={`bar-${bar.task_id}-${bar.attempt}`}
                    x={LABELS + x(bar.start_ms)}
                    y={top + bar.row * (BAR + GAP)}
                    width={Math.max(1, x(end) - x(bar.start_ms))}
                    height={BAR}
                    fill={COLOUR[bar.status] ?? "var(--surface-2)"}
                    fillOpacity={0.62}
                    stroke={COLOUR[bar.status] ?? "var(--line)"}
                    strokeOpacity={0.75}
                    strokeWidth={1}
                  >
                    <title>
                      {`task ${bar.task_id}`}
                      {bar.attempt > 1 && ` · try ${bar.attempt}`}
                      {` · ${bar.status.toLowerCase()}`}
                      {bar.end_ms == null
                        ? " · still running"
                        : ` · ${seconds(bar.end_ms - bar.start_ms)}`}
                    </title>
                  </rect>
                );
              })}
              {/* **Never dropped silently.** The stack stops above 40 concurrent and the lane
                  says how many did not fit — a chart that omits 4,960 bars without saying so
                  is a chart that lies about a run. */}
              {lane.dense > 0 && (
                <text x={LABELS + 6} y={top + height - 1} fontSize={9} className="font-data"
                      fill="var(--measured)" data-testid={`dense-${lane.process}`}>
                  +{lane.dense} more, too concurrent to stack
                </text>
              )}
            </g>
          ))}
        </svg>
      </div>
    </section>
  );
}
