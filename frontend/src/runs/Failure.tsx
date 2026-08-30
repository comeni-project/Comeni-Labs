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
export function Failure({ failed }: { failed: Failed }) {
  const both = failed.peak_rss_bytes !== null && failed.asked_bytes !== null;
  const escalation = failed.history ?? [];
  // One scale for every bar, the largest ask — so the growth is the thing the eye reads.
  // Two bars scaled to their own rows would each be full and say nothing about each other.
  const ceiling = Math.max(...escalation.map((a) => a.memory_bytes ?? 0), 1);

  return (
    /* **A tinted block with a full border, not a white card with a red stripe.** The artboard
       fills the banner with `--undecided-soft` and outlines it in `--undecided`, which is what
       makes it read as *the run stopped here* before a word of it is read. The left-stripe
       card was the same treatment the console gives one failed LINE — using it for the whole
       banner flattened the difference between the run failing and a task failing. */
    <section
      data-testid="failure"
      className="rounded-[var(--r)] shadow-e2 p-[15px] flex flex-col gap-2.5"
      style={{ background: "var(--undecided-soft)", border: "1px solid var(--undecided)" }}
    >
      <div className="flex items-baseline gap-2.5">
        <p className="font-data m-0" style={{ fontSize: "15px", color: "var(--fault)" }}>
          {failed.process ?? "no task failed — the run stopped before one started"}
          {failed.process && (
            <>
              {failed.tag && ` (${failed.tag})`}
              {failed.exit !== null && ` exited ${failed.exit}`}
              {` on attempt ${failed.attempts}`}
            </>
          )}
        </p>
        {/* **Said out loud, and set opposite the headline** — because it is the difference
            between this and a chat window. Every field beside it is a value the record holds;
            nothing here is inferred. */}
        <p className="ml-auto m-0 text-label uppercase tracking-[.08em] text-ink-3
                      whitespace-nowrap">
          from the record · nothing interpreted
        </p>
      </div>

      {/* **Only when both halves are known.** Half a comparison is worse than none: a bare
          `63.8 GB` invites the reader to supply a ceiling they do not have.
          The BAR is the point — `63.8 of 64` is a sentence, and a bar at 99% is the reason
          the task died, visible without reading either number. */}
      {both && (
        <div data-testid="failure-resources" className="flex items-center gap-2.5">
          <span className="block h-[7px] w-[170px] rounded-[3px] overflow-hidden shrink-0"
                style={{ background: "var(--surface-2)", boxShadow: "var(--well)" }}>
            <span className="block h-full"
                  style={{ width: `${Math.min(100, Math.round(
                    (failed.peak_rss_bytes! / failed.asked_bytes!) * 100))}%`,
                    background: "var(--undecided)" }} />
          </span>
          <span className="font-data text-body text-ink-2">
            peaked at {bytes(failed.peak_rss_bytes)} of {bytes(failed.asked_bytes)} asked
          </span>
        </div>
      )}

      {/* **The escalation, and it is the panel's best evidence.** Three attempts asking for
          36, then 48, then 72 GB and dying at each is a story a reader assembles in one glance
          — and it is the story `attempts: 3` cannot tell. The bars share one scale, the largest
          ask, so the growth is visible before either number is read.

          **Only when there is more than one attempt.** A single try has nothing to escalate,
          and its asked-beside-touched is already the bar above. */}
      {escalation.length > 1 && (
        <div data-testid="failure-escalation" className="flex flex-col gap-1.5">
          {escalation.map((attempt) => (
            <div key={attempt.n} data-testid={`attempt-${attempt.n}`}
                 className="flex items-center gap-2.5 text-secondary">
              <span className="font-data text-ink-3 w-[54px] shrink-0 tabular-nums">
                try {attempt.n}
              </span>
              <span className="block h-[7px] w-[170px] rounded-[3px] overflow-hidden shrink-0"
                    style={{ background: "var(--surface-2)", boxShadow: "var(--well)" }}>
                <span className="block h-full"
                      style={{ width: `${((attempt.memory_bytes ?? 0) / ceiling) * 100}%`,
                               background: "var(--ink-3)" }} />
              </span>
              <span className="font-data text-ink-2 tabular-nums">
                asked {bytes(attempt.memory_bytes)} · touched {bytes(attempt.peak_rss_bytes)}
              </span>
              <span className="ml-auto font-data text-ink-3 tabular-nums whitespace-nowrap">
                {attempt.exit === null || attempt.exit === undefined
                  ? attempt.status
                  : `exit ${attempt.exit}`}
                {/* Shown AS GIVEN. `wiener_core.signals` knows the 128+n convention and refuses
                    a cause; adding one here would be W3 arriving early, unlabelled, and right
                    often enough to be trusted when it is wrong. */}
                {attempt.signal && ` · ${attempt.signal}`}
              </span>
            </div>
          ))}
        </div>
      )}

      {failed.report && (
        <>
          {/* `--surface` inside the tinted banner, so the record sits ON the alarm rather than
              in it — the artboard's inset well. **Scrolls rather than truncates**: the
              artboard shows a curated three-line excerpt, and cutting a real `errorReport` at
              three lines would hide the half that matters on the runs this is for. */}
          <pre
            data-testid="failure-report"
            className="m-0 p-3 font-data text-secondary text-ink-2 rounded-[var(--r)]
                       max-h-72 overflow-auto whitespace-pre-wrap"
            style={{ background: "var(--surface)", border: "1px solid var(--line)",
                     boxShadow: "var(--well)", lineHeight: 1.7 }}
          >
            {failed.report}
          </pre>
          {/* §18.1: nothing EXPLAINS a failure until W3. Saying so is a boundary; leaving it
              unsaid would let the banner read as an explanation that came up short. */}
          <p className="m-0 text-label uppercase tracking-[.08em] text-ink-3">
            Nextflow&rsquo;s own errorReport · shown, not explained — W3 explains
          </p>
        </>
      )}
    </section>
  );
}
