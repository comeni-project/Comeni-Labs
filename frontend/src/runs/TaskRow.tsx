import { ABSENT, bytes, percent, seconds } from "./units";

/** One task, as either of the two questions asks for it.
 *
 * `tag` is **optional in the type on purpose** — A200's `labels` column arrived on 2026-08-24
 * and nothing back-fills it, so a run ingested before that has no tag at all. The row falls
 * back to `task_id`, which every run has, rather than rendering an empty cell.
 */
export type TaskView = {
  task_id: number;
  process: string;
  status?: string;
  tag?: string | null;
  attempts: number;
  latest_exit?: number | null;
  peak_rss_bytes?: number | null;
  pct_cpu?: number | null;
  realtime_ms?: number | null;
};

/** SIGKILL. On a Nextflow task it is nearly always the OOM killer, and a reader who has to
 *  look 137 up is a reader the interface failed. */
const OOM = 137;

function mark(task: TaskView): string | null {
  if (task.latest_exit === OOM) return "killed — out of memory";
  if (task.latest_exit) return `exit ${task.latest_exit}`;
  return null;
}

/** **One component, two callers** — the expanded process row and the Tasks tab. The same
 * shape as `dag-core` serving both canvases: two renderings of one row is how they drift.
 *
 * `showProcess` is the whole of the difference. The Tasks tab spans processes and needs the
 * name; an expanded row sits under its own process heading and repeating it is noise.
 */
export function TaskRow({ task, showProcess, worst = false }: {
  task: TaskView;
  showProcess: boolean;
  worst?: boolean;
}) {
  const note = mark(task);
  const columns = showProcess
    ? "grid-cols-[10rem_1fr_3.5rem_5.5rem_4rem_5rem]"
    : "grid-cols-[1fr_3.5rem_5.5rem_4rem_5rem]";

  return (
    <div
      data-testid={`task-${task.task_id}`}
      className={`grid ${columns} items-baseline gap-3 px-4 py-1.5 font-data text-secondary
                  border-b border-line last:border-b-0 tabular-nums
                  hover:bg-[var(--hover)]`}
      style={{ transition: `background-color var(--t)` }}
    >
      {showProcess && (
        <span data-testid="process" className="text-ink truncate">{task.process}</span>
      )}

      <span data-testid="task" className="flex items-baseline gap-2 min-w-0">
        <span className="text-ink truncate">{task.tag ?? `task ${task.task_id}`}</span>
        {task.attempts > 1 && (
          <span
            data-testid="retried"
            title={`${task.attempts} attempts`}
            className="shrink-0 text-[var(--measured)]"
          >
            ↻ {task.attempts}
          </span>
        )}
        {worst && <span className="shrink-0 text-ink-3">worst</span>}
        {note && (
          <span data-testid="mark" className="shrink-0 text-[var(--undecided)]">{note}</span>
        )}
      </span>

      <span data-testid="cpu" className="text-right text-ink-2">{percent(task.pct_cpu)}</span>
      <span data-testid="mem" className="text-right text-ink-2">{bytes(task.peak_rss_bytes)}</span>
      <span data-testid="time" className="text-right text-ink-2">
        {seconds(task.realtime_ms)}
      </span>
      <span className="text-right text-ink-3">{task.status ?? ABSENT}</span>
    </div>
  );
}
