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

  const ticks = 5;
  const marks = Array.from({ length: ticks + 1 }, (_, n) => data.from_ms + (span * n) / ticks);

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
          {marks.map((ms, n) => (
            <g key={n}>
              <line x1={LABELS + x(ms)} y1={0} x2={LABELS + x(ms)} y2={total}
                    stroke="var(--line)" strokeWidth={1} />
              <text x={LABELS + x(ms)} y={total + 18} fill="var(--ink-4)" fontSize={9}
                    textAnchor="middle" className="font-data">
                {seconds(ms - data.from_ms)}
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
