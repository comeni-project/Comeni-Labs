import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { get } from "../wiener/api/client";
import type { components } from "../wiener/api/schema";
import { Failed, Loading } from "../ui/States";
import { TaskHeader, TaskRow, type TaskView } from "./TaskRow";
import { ABSENT, pair, percent, seconds, shortBytes } from "./units";

type TasksPage = { tasks: TaskView[]; total: number };

export type Row = components["schemas"]["ProcessRowOut"];
export type OverviewData = components["schemas"]["OverviewOut"];

/** A bar whose length means something only because its column shares a scale.
 *
 * **Length encodes quantity, on an identical scale down each column** — §4. That is what makes
 * a column a small multiple rather than seven unrelated bars, and comparison is the entire
 * reason the numbers are worth putting in a row. A bar scaled to its own row says nothing
 * about the row above it.
 *
 * `value === null` draws **nothing at all** and the figure reads `—`. A zero-length bar and a
 * zero are the same picture, and one of them is a lie.
 */
function Bar({ testId, figureId, value, ceiling, label, tint = "var(--pea)" }: {
  testId: string; figureId: string; value: number | null; ceiling: number | null;
  label: string; tint?: string;
}) {
  const width = value !== null && ceiling ? Math.min(100, (value / ceiling) * 100) : null;
  return (
    <span className="flex flex-col gap-1 min-w-0">
      <span data-testid={figureId}
            className="font-data text-secondary text-ink-2 tabular-nums truncate">{label}</span>
      <span
        className="block h-1 rounded-full overflow-hidden"
        style={{ background: "var(--line)", boxShadow: "var(--well)" }}
      >
        {width !== null && (
          <span
            data-testid={testId}
            className="block h-full"
            style={{ width: `${Math.max(1, width)}%`, background: tint,
                     transition: `width var(--t)` }}
          />
        )}
      </span>
    </span>
  );
}

/** How many tasks, said absolutely — §5.
 *
 * **No total is claimed while a process is live.** Nextflow discovers tasks as channels emit,
 * so `3 / 12` asserts a denominator nobody can source. `3 done · 9 more seen` is two facts
 * about what has been reported, and neither is a prediction.
 */
function Count({ row }: { row: Row }) {
  const outstanding = row.tasks - row.done;
  return (
    <span data-testid={`count-${row.process}`}
          className="font-data text-secondary tabular-nums text-ink-2">
      {row.reached ? (
        <>
          {row.done} done
          {outstanding > 0 && <span className="text-ink-3"> · {outstanding} more seen</span>}
          {row.failed > 0 && (
            <span className="text-[var(--undecided)]"> · {row.failed} failed</span>
          )}
        </>
      ) : (
        <span className="text-ink-3">not started</span>
      )}
    </span>
  );
}

/** The ceilings every column shares. Computed once over the visible rows, because a scale
 *  derived per row is not a scale. */
function ceilings(rows: Row[]) {
  const most = (pick: (row: Row) => number | null | undefined) =>
    rows.reduce<number | null>((worst, row) => {
      const value = pick(row);
      return value === null || value === undefined ? worst : Math.max(worst ?? 0, value);
    }, null);
  return {
    time: most((row) => row.realtime_ms),
    io: most((row) => (row.read_bytes ?? 0) + (row.write_bytes ?? 0)),
  };
}

/** What one process did — fetched **only while it is open**.
 *
 * `enabled` is the whole of the cost argument: a run with forty processes must not open forty
 * queries to draw a table nobody has clicked. This is §6's first question — *what did this
 * process do* — and the Tasks tab is the second.
 */
function Expanded({ runId, process }: { runId: string; process: string }) {
  const { data, isPending } = useQuery({
    queryKey: ["tasks", runId, process],
    queryFn: () => get<TasksPage>(
      `/api/runs/${runId}/tasks?process=${encodeURIComponent(process)}&sort=-peak_rss_bytes`,
    ),
  });
  if (isPending) return <p className="px-8 py-2 text-secondary text-ink-3">Reading tasks…</p>;
  if (!data?.tasks.length) {
    return <p className="px-8 py-2 text-secondary text-ink-3">No task has been reported.</p>;
  }
  return (
    <div className="bg-paper">
      <TaskHeader showProcess={false} />
      {data.tasks.map((task, index) => (
        <TaskRow key={task.task_id} task={task} showProcess={false} worst={index === 0} />
      ))}
      {data.total > data.tasks.length && (
        <p className="px-4 py-1.5 text-label text-ink-3">
          {data.total - data.tasks.length} more — open the Tasks tab
        </p>
      )}
    </div>
  );
}

export function Table({ data, runId, openOn }: {
  data: OverviewData; runId?: string; openOn?: string;
}) {
  const rows = data.rows;
  const top = ceilings(rows);
  // `openOn` is the failed process, expanded from the start — §9: the comparison is
  // the diagnosis, so the siblings have to be on screen without a click.
  const [open, setOpen] = useState<string | null>(openOn ?? null);

  return (
    <div>
      <div className="grid grid-cols-[13rem_8rem_7rem_1fr_1fr_1fr_1fr] gap-4 px-4 py-2
                      border-b border-line bg-surface-2 shadow-e1
                      font-ui text-label uppercase tracking-[.14em] font-semibold text-ink-3">
        <span>process</span><span>tasks</span><span>progress</span>
        <span>memory peak / asked</span><span>cpu used / asked</span>
        <span>worst realtime</span><span>read / written</span>
      </div>

      {rows.map((row) => {
        const io = row.read_bytes === null && row.write_bytes === null
          ? null : (row.read_bytes ?? 0) + (row.write_bytes ?? 0);
        return (
          <div key={row.process}>
          <div
            data-testid={`row-${row.process}`}
            className={`grid grid-cols-[13rem_8rem_7rem_1fr_1fr_1fr_1fr] gap-4 px-4 py-2.5
                        items-center border-b border-line last:border-b-0
                        hover:bg-[var(--hover)] ${row.reached ? "" : "opacity-55"}`}
            style={{ transition: "background-color var(--t)" }}
          >
            <span className="flex items-baseline gap-2 min-w-0">
              {/* The caret is at rest rather than on hover: a control that only exists under
                  the pointer cannot be found by somebody looking for it. */}
              <button
                type="button"
                data-testid={`expand-${row.process}`}
                aria-expanded={open === row.process}
                aria-label={`tasks of ${row.process}`}
                disabled={!row.reached || !runId}
                onClick={() => setOpen(open === row.process ? null : row.process)}
                className="shrink-0 bg-transparent border-0 p-0 cursor-pointer text-ink-3
                           hover:text-ink disabled:opacity-30 disabled:cursor-default"
                style={{ transition: `transform var(--t), color var(--t)`,
                         transform: open === row.process ? "rotate(90deg)" : "none" }}
              >
                ›
              </button>
              <span className="font-data text-body text-ink truncate">{row.process}</span>
              {row.attempts_max > 1 && (
                <span title={`a task of this process retried — ${row.attempts_max} attempts`}
                      className="shrink-0 font-data text-secondary text-[var(--measured)]">
                  ↻{row.attempts_max}
                </span>
              )}
              {!row.declared && (
                <span title="the run ran this and the artifact does not describe it"
                      className="shrink-0 text-label text-ink-3">undeclared</span>
              )}
            </span>

            <Count row={row} />

            {/* **Done over tasks SEEN**, which is a fact about what has been reported rather
                than a claim about what is coming (§5). It is not a percentage of the work. */}
            <Bar
              testId={`bar-progress-${row.process}`} figureId={`progress-${row.process}`}
              value={row.reached ? row.done : null} ceiling={row.tasks || null}
              label={row.reached ? `${row.done}/${row.tasks}` : ABSENT}
            />

            {/* Memory and cpu are their own ceiling: what was ASKED FOR is the scale, so a
                nearly-full bar is the next exit 137 and an almost-empty one is capacity
                nobody needed. §9.3's comparison, drawn. */}
            <Bar
              testId={`bar-mem-${row.process}`} figureId={`mem-${row.process}`}
              value={row.memory_peak_bytes} ceiling={row.memory_asked_bytes}
              tint="var(--measured)"
              label={pair(row.memory_peak_bytes, row.memory_asked_bytes)}
            />
            <Bar
              testId={`bar-cpu-${row.process}`} figureId={`cpu-${row.process}`}
              value={row.cpu_used_pct} ceiling={row.cpus_asked ? row.cpus_asked * 100 : null}
              tint="var(--measured)"
              label={row.cpu_used_pct !== null && row.cpus_asked
                ? percent(row.cpu_used_pct / row.cpus_asked)
                : ABSENT}
            />
            <Bar
              testId="bar-time" figureId={`time-${row.process}`}
              value={row.realtime_ms} ceiling={top.time}
              label={seconds(row.realtime_ms)}
            />
            <Bar
              testId={`bar-io-${row.process}`} figureId={`io-${row.process}`}
              value={io} ceiling={top.io}
              label={io === null
                ? ABSENT
                : `${shortBytes(row.read_bytes)} / ${shortBytes(row.write_bytes)}`}
            />
          </div>
          {open === row.process && runId && (
            <Expanded runId={runId} process={row.process} />
          )}
          </div>
        );
      })}

      {/* The artboard's footer, and the second line is the legend the four rules need in
          front of a reader who did not read the spec. */}
      <p className="px-4 py-2 flex items-baseline gap-3 border-t border-line
                    text-label text-ink-3">
        <span data-testid="table-footer">
          {data.steps_declared > 0
            ? `${data.steps_declared} processes declared`
            : `${rows.length} processes seen`} ·{" "}
          {rows.reduce((seen, row) => seen + row.tasks, 0)} tasks seen
        </span>
        <span className="ml-auto">
          every bar shares its column's scale · — means nothing was reported, never zero
        </span>
      </p>
    </div>
  );
}

export function Overview({ data, runId, openOn }: {
  data: OverviewData; runId?: string; openOn?: string;
}) {
  return <Table data={data} runId={runId} openOn={openOn} />;
}

export function OverviewPanel({ runId, openOn }: { runId: string; openOn?: string }) {
  const { data, isPending, isError, error } = useQuery({
    queryKey: ["overview", runId],
    queryFn: () => get<OverviewData>(`/api/runs/${runId}/overview`),
    refetchInterval: 4000,
  });
  if (isPending) return <Loading what="the run" />;
  if (isError || !data) return <Failed error={error ?? "the overview could not be read"} />;
  return <Table data={data} runId={runId} openOn={openOn} />;
}
