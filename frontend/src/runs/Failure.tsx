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
    <section
      data-testid="failure"
      className="bg-surface border border-line rounded-[var(--r)] shadow-e2 overflow-hidden"
      style={{ borderLeft: "3px solid var(--fault)" }}
    >
      <div className="px-4 py-3 flex flex-col gap-1.5">
        <p className="font-data text-body text-ink">
          {failed.process ?? "no task failed — the run stopped before one started"}
          {failed.process && (
            <span className="text-ink-2">
              {failed.tag && ` (${failed.tag})`}
              {failed.exit !== null && ` exited ${failed.exit}`}
              {` on attempt ${failed.attempts}`}
              {failed.exit === 137 && (
                <span className="text-ink-3"> — killed, out of memory</span>
              )}
            </span>
          )}
        </p>
        {/* **Said out loud, because it is the difference between this and a chat window.**
            Every field above is a value the record holds; nothing here is inferred. */}
        <p className="text-label text-ink-3">from the record · nothing interpreted</p>

        {/* **Only when both halves are known.** Half a comparison is worse than none: a bare
            `63.8 GB` invites the reader to supply a ceiling they do not have. */}
        {both && (
          <p data-testid="failure-resources" className="font-data text-secondary text-ink-2">
            peaked at {bytes(failed.peak_rss_bytes)} of {bytes(failed.asked_bytes)} asked
          </p>
        )}
      </div>

      {failed.report && (
        <div className="border-t border-line">
          <p className="px-4 pt-3 text-label text-ink-3">Command error:</p>
          <pre
            data-testid="failure-report"
            className="mx-4 my-2 p-3 font-data text-secondary text-ink-2 bg-paper
                       border border-line rounded-[var(--r)] max-h-64
                       overflow-auto whitespace-pre-wrap"
          >
            {failed.report}
          </pre>
          {/* §18.1: nothing EXPLAINS a failure until W3. Saying so is a boundary; leaving it
              unsaid would let the banner read as an explanation that came up short. */}
          <p className="px-4 pb-3 text-label text-ink-3">
            Nextflow&rsquo;s own errorReport · shown, not explained — W3 explains
          </p>
        </div>
      )}
    </section>
  );
}
