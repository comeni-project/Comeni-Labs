import { bytes } from "./units";

/** Everything the banner says, and every field of it comes from the record.
 *
 * `report` is Nextflow's own `errorReport`, which `admit()` has always kept and nothing has
 * ever rendered. It is a **`LabString`**: it reaches this browser and must never become a span
 * attribute — §8 forbids that and `test_the_fold_is_where_the_lab_strings_stop` holds it.
 * Nothing here weakens that, because nothing here writes anything back.
 */
export type Attempt = {
  n: number;
  status: string;
  exit?: number | null;
  /** `SIGKILL` for 137 — the 128+n convention, and **nothing else**.
   *
   *  Computed by `wiener_core.signals`, which refuses a cause: a preemption, a `kill -9` and a
   *  cgroup limit are the same code. The panel shows this string as given and adds no word to
   *  it — §18.1, and the temptation is specific enough to have its own guard. */
  signal?: string | null;
  memory_bytes?: number | null;
  peak_rss_bytes?: number | null;
  realtime_ms?: number | null;
};

export type Failed = {
  /** `null` when **no task failed** — a run can stop before any task starts, on a bad
   *  parameter or a file the channel could not read. The phase is still `failed` and the
   *  record still carries Nextflow's report, so the banner says what it has rather than
   *  nothing at all. */
  process: string | null;
  tag?: string | null;
  exit: number | null;
  attempts: number;
  peak_rss_bytes: number | null;
  asked_bytes: number | null;
  report: string | null;
  /** Every attempt, in order — **what each one asked for beside what it touched.**
   *
   *  New as of Plan 4 phase 4. Until then `attempts` was a count, and a count cannot show
   *  36 → 48 → 72 GB, which is the whole reason retries are kept as history (§5.1). It sat in
   *  a JSON column that nothing projected. */
  history?: Attempt[];
};

/** Where a run stopped, above the fold, without a click.
 *
 * **This shows the failure and does not explain it.** §18.1's *nothing explains it until W3*
 * is a boundary rather than a shortfall, and a banner that guessed at a cause here is exactly
 * the shortfall dressed as a feature. Exit 137 is named because SIGKILL is a fact about the
 * code, not an interpretation of the run.
 */
export function Failure({ failed, onOpenConsole }: {
  failed: Failed;
  /** Open the console filtered to the failed step. Absent where there is no console. */
  onOpenConsole?: (process: string) => void;
}) {
  const both = failed.peak_rss_bytes !== null && failed.asked_bytes !== null;
  const escalation = failed.history ?? [];
  const ceiling = Math.max(...escalation.map((a) => a.memory_bytes ?? 0), 1);

  return (
    /* **A needs-you border around the run's account of itself**, two columns that stack when
       narrow: the failed task on the left, Nextflow's own words on the right. */
    <section
      data-testid="failure"
      className="rounded-panel bg-surface p-5 grid gap-5 grid-cols-1 lg:grid-cols-2"
      style={{ border: "1.5px solid var(--needs-you)" }}
    >
      <section aria-label="the failed task" className="flex flex-col gap-3 min-w-0">
        <div className="flex items-baseline gap-2.5 flex-wrap">
          <p className="m-0 font-data text-[15px] font-semibold text-ink">
            {failed.process ?? "No task failed — the run stopped before one started"}
          </p>
          {failed.process && failed.tag && <span className="font-data text-[12.5px] text-ink-3">{failed.tag}</span>}
          {failed.process && failed.exit !== null && (
            <span className="px-[7px] py-[2px] rounded-control text-[12px] font-semibold text-needs-you-ink"
                  style={{ background: "var(--needs-you-soft)" }}>
              exited {failed.exit}
            </span>
          )}
        </div>
        {failed.process && (
          <p className="m-0 text-[14px] text-ink">
            It stopped on attempt {failed.attempts}. Every value here is from the record; nothing
            is interpreted.
          </p>
        )}

        {/* **Only when both halves are known.** Half a comparison is worse than none: a bare
            `63.8 GB` invites the reader to supply a ceiling they do not have. Only for a single
            try — more than one has its own bars below. */}
        {both && escalation.length <= 1 && (
          <div data-testid="failure-resources" className="flex items-center gap-2.5">
            <span className="block h-[8px] w-[200px] rounded-full overflow-hidden shrink-0"
                  style={{ background: "var(--surface-2)" }}>
              <span className="block h-full rounded-full"
                    style={{ width: `${Math.min(100, Math.round(
                      (failed.peak_rss_bytes! / failed.asked_bytes!) * 100))}%`,
                      background: "var(--measured)" }} />
            </span>
            <span className="font-data text-[13px] text-ink-2">
              peaked at {bytes(failed.peak_rss_bytes)} of {bytes(failed.asked_bytes)} asked
            </span>
          </div>
        )}

        {/* **The escalation is the panel's best evidence**: three attempts asking for 36, then
            48, then 72 GB and dying at each is a story read in one glance, which `attempts: 3`
            cannot tell. Each bar is what an attempt asked for, on one scale; its fill is how
            much of that it touched. */}
        {escalation.length > 1 && (
          <div data-testid="failure-escalation" className="flex flex-col gap-2">
            <p className="m-0 text-[13px] font-semibold text-ink">
              The {escalation.length === 3 ? "three" : escalation.length} attempts
            </p>
            {escalation.map((attempt) => (
              <div key={attempt.n} data-testid={`attempt-${attempt.n}`}
                   className="grid items-center gap-x-3 gap-y-1 text-[13px]
                              grid-cols-[70px_minmax(60px,1fr)] sm:grid-cols-[70px_minmax(80px,1fr)_auto]">
                <span className="text-ink-2">attempt {attempt.n}</span>
                <span className="block h-[8px] rounded-full overflow-hidden"
                      style={{ width: `${((attempt.memory_bytes ?? 0) / ceiling) * 100}%`,
                               background: "var(--surface-2)" }}>
                  <span className="block h-full rounded-full"
                        style={{ width: `${attempt.memory_bytes
                          ? Math.min(100, ((attempt.peak_rss_bytes ?? 0) / attempt.memory_bytes) * 100) : 0}%`,
                                 background: "var(--measured)" }} />
                </span>
                <span className="col-span-2 sm:col-span-1 font-data text-ink tabular-nums">
                  peak {bytes(attempt.peak_rss_bytes)} of {bytes(attempt.memory_bytes)}
                  <span className="text-ink-3">
                    {attempt.exit === null || attempt.exit === undefined ? ` · ${attempt.status}` : ` · exit ${attempt.exit}`}
                    {/* Shown AS GIVEN: `wiener_core.signals` knows the 128+n convention and
                        refuses a cause, and so does this. */}
                    {attempt.signal && ` · ${attempt.signal}`}
                  </span>
                </span>
              </div>
            ))}
          </div>
        )}

        {failed.process && onOpenConsole && (
          <button type="button" onClick={() => onOpenConsole(failed.process!)}
                  className="self-start px-[14px] py-[7px] rounded-button border border-line-2 bg-surface
                             text-[13px] font-semibold text-ink cursor-pointer hover:bg-[var(--hover)]
                             focus-visible:shadow-[var(--ring)]">
            Open the console at this task
          </button>
        )}
      </section>

      <section aria-label="What Nextflow reported" className="flex flex-col gap-2 min-w-0">
        <div className="flex items-baseline gap-3">
          <h3 className="m-0 text-heading font-semibold text-ink">What Nextflow reported</h3>
          <span className="ml-auto text-[12.5px] text-ink-3">shown as written</span>
        </div>
        {failed.report ? (
          /* **Scrolls rather than truncates**: cutting a real `errorReport` at three lines would
             hide the half that matters on the runs this is for. */
          <pre
            data-testid="failure-report"
            className="m-0 p-3 font-data text-[12px] text-ink-2 rounded-button max-h-72 overflow-auto
                       whitespace-pre-wrap"
            style={{ background: "var(--surface-2)", border: "1px solid var(--line)", lineHeight: 1.7 }}
          >
            {failed.report}
          </pre>
        ) : (
          <p className="m-0 text-[13px] text-ink-3">The record carries no report from Nextflow.</p>
        )}
      </section>
    </section>
  );
}
