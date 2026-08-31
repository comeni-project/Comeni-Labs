/** **Run**: one control, four verbs, in order.
 *
 * `impl-walk`: *the four verbs STILL HAPPEN. They stop being UI.*
 *
 *     Run  =  keep (write the artifact)  ->  lint  ->  open the run sheet  ->  submit
 *
 * ═══ WHY THIS IS CHEAP, AND WHY IT WAS NOT BEFORE ═════════════════════════════════════════
 *
 * The argument for collapsing the rail is that **drafts autosave**, so *Keep* was an
 * implementation detail wearing a button, and **lint is 1.6s** — not the 10s people remember,
 * which was the gate. Both are true; the first only became true in this same phase, because
 * `useGraph`'s save callback had never been passed (see `usePipelineDraft`).
 *
 * ═══ WHAT MUST NOT COLLAPSE ═══════════════════════════════════════════════════════════════
 *
 * **`execution-boundary.md` §3 keeps a gate and a run apart, and that split stays in the
 * backend.** A gate proves an artifact on PUBLIC data; a run touches the laboratory's OWN. They
 * remain two server verbs called in sequence — what this removes is the expectation that a
 * person knows the sequence, not the sequence.
 *
 * **`keep` is still a real boundary.** A save writes the graph into a row; `keep` validates it,
 * refuses anything illegal and writes the `pipeline.yml`. `services/drafts.py` says so in its
 * header, and this calls it rather than assuming an autosave did its job.
 *
 * ═══ IT REPORTS ═══════════════════════════════════════════════════════════════════════════
 *
 * `error` is the reason it stopped, in the words of whichever step stopped it, and the caller
 * must render it. That is phase 0's rule arriving in the one place the 2026-08-29 walk found it
 * missing: *Keep* answered 500 and the rail sat there, unchanged, still offering *Keep*.
 */
import { useCallback, useState } from "react";

/** Where the sequence has got to. `null` when it is not running. */
export type RunStage = "keeping" | "linting" | "asking" | null;

export function useRun({ keep, lint, gatePassed, openSheet }: {
  /** Writes the artifact. Resolves to the draft id, or throws. */
  keep: () => Promise<string | null>;
  /** Starts a lint gate on the kept artifact. */
  lint: () => void;
  /** Whether a gate has passed on what was kept. */
  gatePassed: boolean;
  /** Opens the run sheet — where the data is bound, which is the step a person must do. */
  openSheet: () => void;
}) {
  const [stage, setStage] = useState<RunStage>(null);
  const [error, setError] = useState<string | null>(null);

  const run = useCallback(async () => {
    setError(null);
    try {
      setStage("keeping");
      const draftId = await keep();
      if (draftId === null) throw new Error("this pipeline could not be kept");

      // **The gate is not awaited here.** It is a server job with its own state, watched
      // through the query cache; blocking a button on a 1.6s round trip that already has a
      // visible panel would be a second progress indicator for one thing.
      if (!gatePassed) {
        setStage("linting");
        lint();
      }

      // **The sheet opens whether or not the lint has landed.** Binding data is the step that
      // takes a person time, and `SubmitPanel` refuses to submit until the gate is green — so
      // the two proceed in parallel rather than one waiting on the other.
      setStage("asking");
      openSheet();
    } catch (failed) {
      setError(failed instanceof Error ? failed.message : String(failed));
    } finally {
      setStage(null);
    }
  }, [keep, lint, gatePassed, openSheet]);

  return { run, stage, error, busy: stage !== null };
}
