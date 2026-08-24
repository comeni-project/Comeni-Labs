import { Menu, copy, useContextMenu, type MenuItem } from "./Menu";
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

/** Tag · Attempt · Exit · Memory · CPU · Realtime — the artboard's columns, in its order.
 *  `Process` is prepended for the tab that spans processes and omitted where the row already
 *  sits under its process heading. */
const COLUMNS = "grid-cols-[1fr_4rem_5rem_6rem_4rem_5rem]";
const WITH_PROCESS = "grid-cols-[11rem_1fr_4rem_5rem_6rem_4rem_5rem]";

/** The header the artboard draws above a task table — one spelling, both callers. */
export function TaskHeader({ showProcess }: { showProcess: boolean }) {
  return (
    <div className={`grid ${showProcess ? WITH_PROCESS : COLUMNS} gap-3 px-4 py-1.5
                     border-b border-line bg-surface-2
                     font-ui text-label uppercase tracking-[.14em] font-semibold text-ink-3`}>
      {showProcess && <span>process</span>}
      <span>tag</span>
      <span className="text-right">attempt</span>
      <span className="text-right">exit</span>
      <span className="text-right">memory</span>
      <span className="text-right">cpu</span>
      <span className="text-right">realtime</span>
    </div>
  );
}

/** **One component, two callers** — the expanded process row and the Tasks tab. The same
 * shape as `dag-core` serving both canvases: two renderings of one row is how they drift.
 *
 * `showProcess` is the whole of the difference. The Tasks tab spans processes and needs the
 * name; an expanded row sits under its own process heading and repeating it is noise.
 */
export function TaskRow({ task, showProcess, worst = false, onOpenConsole }: {
  task: TaskView;
  showProcess: boolean;
  worst?: boolean;
  onOpenConsole?: (process: string) => void;
}) {
  const exit = task.latest_exit;
  const menu = useContextMenu();

  /** §12.3's task-row menu. Two of its verbs are dim for a reason that is **not** "W4 does
   *  it": `/tasks` carries `tag` and no other lab string, which A200 decided deliberately —
   *  the work directory and the command line live in `run_event.payload` and stay there. */
  const items: MenuItem[] = [
    { label: "Open in console here",
      onPick: onOpenConsole && (() => onOpenConsole(task.process)) },
    { label: "Copy the task id", onPick: () => void copy(String(task.task_id)) },
    ...(task.tag ? [{ label: "Copy the tag", onPick: () => void copy(task.tag!) }] : []),
    { label: "Copy work directory", why: "not served", separated: true },
    { label: "Copy task hash", why: "not served" },
    { label: "Copy the command line", why: "not served" },
    { label: "Retry this task", w4: true, separated: true },
  ];

  return (
    <>
    <div
      {...menu.bind}
      data-testid={`task-${task.task_id}`}
      className={`grid ${showProcess ? WITH_PROCESS : COLUMNS} items-baseline gap-3 px-4 py-1.5
                  font-data text-secondary border-b border-line last:border-b-0 tabular-nums
                  hover:bg-[var(--hover)]`}
      style={{ transition: `background-color var(--t)` }}
    >
      {showProcess && (
        <span data-testid="process" className="text-ink truncate">{task.process}</span>
      )}

      <span data-testid="task" className="flex items-baseline gap-2 min-w-0 text-ink">
        <span className="truncate">{task.tag ?? `task ${task.task_id}`}</span>
        {worst && <span className="shrink-0 text-ink-3">worst</span>}
      </span>

      {/* The attempt NUMBER, always — the artboard's column. `↻` marks the ones that are not
          the first, so a retry is legible without reading the digit. */}
      <span
        data-testid={task.attempts > 1 ? "retried" : "attempt"}
        className={`text-right ${task.attempts > 1 ? "text-[var(--measured)]" : "text-ink-2"}`}
      >
        {task.attempts > 1 && "↻"}{task.attempts}
      </span>

      <span data-testid="exit" className="text-right">
        {exit === null || exit === undefined ? (
          <span className="text-ink-3">{ABSENT}</span>
        ) : exit === 0 ? (
          <span className="text-ink-2">0</span>
        ) : (
          <span data-testid="mark" className="text-[var(--undecided)]"
                title={exit === OOM ? "killed — out of memory" : undefined}>
            {exit}{exit === OOM && <span className="text-ink-3"> killed — out of memory</span>}
          </span>
        )}
      </span>

      <span data-testid="mem" className="text-right text-ink-2">
        {bytes(task.peak_rss_bytes)}
      </span>
      <span data-testid="cpu" className="text-right text-ink-2">{percent(task.pct_cpu)}</span>
      <span data-testid="time" className="text-right text-ink-2">
        {seconds(task.realtime_ms)}
      </span>
    </div>
    {menu.at && <Menu items={items} at={menu.at} onClose={menu.close} />}
    </>
  );
}
