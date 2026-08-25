import { bytes } from "./units";

/** Everything the banner says, and every field of it comes from the record.
 *
 * `report` is Nextflow's own `errorReport`, which `admit()` has always kept and nothing has
 * ever rendered. It is a **`LabString`**: it reaches this browser and must never become a span
 * attribute — §8 forbids that and `test_the_fold_is_where_the_lab_strings_stop` holds it.
 * Nothing here weakens that, because nothing here writes anything back.
 */
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
