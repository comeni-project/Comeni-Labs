import { Link } from "react-router";

/** The first run: one question, one field.
 *
 * **Its own composition, not this page with everything hidden**, and not onboarding cards —
 * `ov-absence`'s one stated exception.
 *
 * ═══ THE PROMPT IS DISABLED, AND SAYS WHY ═════════════════════════════════════════════════
 *
 * The artboard's primary affordance is a prompt box, and **it cannot work yet**. Turning a
 * sentence into a `Goal` is **door 1** — goal extraction — and invariant 3 declares it as one of
 * exactly three runtime AI points. Nothing implements it: there is no adapter on the build path
 * at all, and `mendel build` has no AI path until the tier-4 resolver arrives with Plan 3.
 *
 * Operator's decision, 2026-08-30: **draw it, disabled, with the reason underneath.** The
 * alternative considered was omitting it — absence is absence — and the argument against is that
 * a person who has just installed this should be able to see what the product is going to be.
 * The argument *for* omitting it is `Shell.tsx`'s: a control going nowhere silently is worse
 * than one that admits it. A disabled control that states its reason is neither.
 *
 * **What must not happen is the model producing a pipeline.** Invariant 3 and `impl-inv`: the
 * assistant writes a GOAL, never a graph, and the person corrects the typed goal card before
 * anything runs. An assistant that draws nodes has put the model's unreliability back into the
 * output, which is the whole thing this product exists to prevent.
 *
 * **`build it by hand` is the path that works today**, and it is the one that is live.
 */
export function First() {
  return (
    <div className="overflow-auto">
      <div className="max-w-[880px] mx-auto px-6 min-h-[70vh] flex flex-col justify-center
                      settle">
        <h1 className="font-display text-hero text-ink text-center m-0 tracking-[-.02em]">
          What do you want to make?
        </h1>

        <div className="mt-8">
          <label
            htmlFor="goal"
            className="flex items-center gap-3 border border-line rounded-r bg-surface px-4 py-4
                       opacity-55"
          >
            <span aria-hidden className="text-ink-3 font-data">›</span>
            <input
              id="goal"
              disabled
              className="grow bg-transparent border-0 outline-none text-object text-ink-3
                         cursor-not-allowed"
              placeholder="gene counts from paired-end RNA-seq of mouse liver"
            />
          </label>

          {/* **The reason is under the control, never in a tooltip** — the rule `Walk.tsx`
              states and the reason a disabled thing is a step rather than a wall. */}
          <p className="text-secondary text-ink-3 mt-3 mb-0 text-center">
            Describing an analysis in words is not built yet. It is one of three declared points
            where a model may run, and it produces a <em>goal</em> you correct — never a
            pipeline.
          </p>
        </div>

        <p className="text-body text-ink-2 mt-8 mb-0 text-center">
          <Link to="/build" className="text-[var(--link)]">Build it by hand</Link>
          {" — that path works today."}
        </p>
      </div>
    </div>
  );
}
