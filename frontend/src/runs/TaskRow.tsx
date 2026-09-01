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

/** Tag · Attempt · Exit · Memory · CPU · Realtime · mark — the artboard's columns, its
 *  widths, its order. `Process` is prepended for the tab that spans processes and omitted
 *  where the row already sits under its process heading.
 *
 * **The `1fr` is on `tag`, and the mark column is fixed** — `.tk` in `RunView.dc.html` is
 * `56px 176px 92px 1fr 82px 74px 58px`, so the flexible column sits early and every figure
 * after it is anchored at the right edge.
 *
 * **This was corrected twice and the first correction over-shot.** The `1fr` began on `tag`,
 * which pushed the numbers to the far right — a row with its identity at one end of the screen
 * and its figures at the other. Moving it to the LAST column fixed that and created the
 * opposite fault: every column packed hard against the left with the whole surplus in one
 * empty gutter on the right, which is what the operator saw as *the tasks table is not
 * centered*.
 *
 * The artboard has both properties at once and neither correction found it: one early flexible
 * column spreads the row, and narrow fixed columns after it cluster the figures where the eye
 * compares them down the column. The mark column keeps its slot — `worst`, `retried once`,
 * `killed — out of memory` — at a fixed width rather than by absorbing the slack.
 */
const COLUMNS = "grid-cols-[1fr_80px_70px_110px_90px_100px_128px]";
const WITH_PROCESS = "grid-cols-[176px_1fr_80px_70px_110px_90px_100px_128px]";

/** Indented under its process, or flush in the tab that spans them — the artboard's two
 *  paddings. The indent is what makes an expanded block read as *inside* its row. */
const PAD = "pl-[46px] pr-[18px]";
const PAD_TAB = "px-[18px]";

/** The header the artboard draws above a task table — one spelling, both callers. */
export function TaskHeader({ showProcess }: { showProcess: boolean }) {
  return (
    <div className={`grid ${showProcess ? WITH_PROCESS : COLUMNS} gap-4
                     ${showProcess ? `${PAD_TAB} py-2 border-b border-line-2`
                                   : `${PAD} py-[7px] border-y border-line`}
                     font-ui text-label uppercase tracking-[.08em] font-semibold text-ink-3`}>
      {showProcess && <span>process</span>}
      <span>tag</span><span>attempt</span><span>exit</span>
      <span>memory</span><span>cpu</span><span>realtime</span><span />
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

  // **The mark column carries every annotation**, so the figures stay a clean grid. `worst`
  // and a retry note are the artboard's; the OOM gloss moves here out of the exit cell,
  // where it was widening a 70px column with a sentence.
  const failed = exit !== null && exit !== undefined && exit !== 0;
  const mark = failed && exit === OOM ? "killed — out of memory"
    : task.attempts > 1 ? `retried ${task.attempts > 2 ? `${task.attempts - 1} times` : "once"}`
    : worst ? "worst" : "";

  return (
    <>
    <div
      {...menu.bind}
      data-testid={`task-${task.task_id}`}
      className={`grid ${showProcess ? WITH_PROCESS : COLUMNS} items-baseline gap-4
                  ${showProcess ? PAD_TAB : PAD} py-1.5
                  font-data text-secondary border-b border-line last:border-b-0 tabular-nums
                  hover:bg-[var(--hover)]`}
      style={{
        transition: `background-color var(--t)`,
        // A failed task is tinted and struck with a 2px rule down its left edge — the
        // artboard's treatment, and the reason a failing row is findable in a wall of them
        // without reading the exit column.
        ...(failed
          ? { background: "var(--undecided-soft)",
              boxShadow: "inset 2px 0 0 var(--undecided)" }
          : {}),
      }}
    >
      {showProcess && (
        <span data-testid="process" className="text-ink truncate">{task.process}</span>
      )}

      <span data-testid="task"
            className={`truncate ${failed ? "text-[var(--undecided)]" : "text-ink"}`}>
        {task.tag ?? `task ${task.task_id}`}
      </span>

      {/* The attempt NUMBER, always — the artboard's column. It turns `--measured` when it is
          not the first, so a retry is legible without reading the digit. */}
      <span
        data-testid={task.attempts > 1 ? "retried" : "attempt"}
        className={task.attempts > 1 ? "text-[var(--measured)]" : "text-ink-2"}
      >
        {task.attempts}
      </span>

      <span data-testid="exit">
        {exit === null || exit === undefined ? (
          <span className="text-ink-3">{ABSENT}</span>
        ) : exit === 0 ? (
          <span className="text-ink-2">0</span>
        ) : (
          <span data-testid="mark" className="text-[var(--undecided)]">{exit}</span>
        )}
      </span>

      <span data-testid="mem" className="text-ink-2">{bytes(task.peak_rss_bytes)}</span>
      <span data-testid="cpu" className="text-ink-2">{percent(task.pct_cpu)}</span>
      <span data-testid="time" className="text-ink-2">{seconds(task.realtime_ms)}</span>
      <span data-testid="note"
            className={failed ? "text-[var(--undecided)]" : "text-ink-3"}>{mark}</span>
    </div>
    {menu.at && <Menu items={items} at={menu.at} onClose={menu.close} />}
    </>
  );
}
