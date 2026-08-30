import { Link } from "react-router";

/** The first run: one question, one field. **Drawn against `OverviewFirst.dc.html`, measurement
 *  for measurement.**
 *
 * ═══ WHAT THE FIRST VERSION GOT WRONG ═════════════════════════════════════════════════════
 *
 * It shipped as a washed-out rounded input at 55% opacity in a 880px column, under a headline
 * set in **Georgia**, on a flat black page. The artboard is a 660px square-cornered bar with a
 * blue chevron and a blinking cursor, under Geist at 34px, over a bloom of arcs. Nothing about
 * it read as the same screen, and the operator was right to say so.
 *
 * The measurements are the artboard's own: `min(660px, 100%)` · `1px solid #1E3A4E` ·
 * `background #0B1013` · `padding 15px 18px` · `gap 12px` · placeholder at 15px in `#455257`.
 * **Square, not rounded** — nothing in this product has a radius above 3px and this bar has
 * none at all.
 *
 * ═══ THE BLOOM IS THIS SCREEN'S OWN ══════════════════════════════════════════════════════
 *
 * `origin="bottom"` throws the arcs from below the prompt rather than from the lower-left
 * corner, so they radiate out of the thing you are being asked to use. Every other screen uses
 * the corner origin. That is the artboard's distinction and it is why `Field` takes an origin
 * rather than being two components.
 *
 * ═══ THE PROMPT IS DISABLED, AND SAYS WHY ════════════════════════════════════════════════
 *
 * Turning a sentence into a `Goal` is **door 1** — goal extraction — one of the three runtime
 * AI points invariant 3 declares, and nothing implements it: there is no adapter on the build
 * path, and `mendel build` has no AI path until the tier-4 resolver arrives.
 *
 * Operator's decision, 2026-08-30: **draw it, disabled, with the reason underneath.** Omitting
 * it was the alternative — absence is absence — and the argument against is that somebody who
 * has just installed this should see what the product is going to be. `Shell.tsx`'s rule is
 * that a control going nowhere *silently* is worse than one that admits it; a disabled control
 * stating its reason is neither.
 *
 * **What must not happen is the model producing a pipeline.** The assistant writes a GOAL,
 * never a graph, and the person corrects the typed goal card before anything runs.
 *
 * **`build it by hand` is the path that works today**, and it is the one that is live.
 */
export function First() {
  return (
    <div className="relative overflow-auto">
      <div className="relative min-h-full flex flex-col items-center justify-center
                      gap-[30px] px-11 pb-20">
        {/* 34px / 600 / -.03em / 22ch, balanced — the artboard's exact type. It was
            `font-display`, which was a serif, at a size the artboard does not use. */}
        <h1 className="settle m-0 text-center font-ui text-ink font-semibold
                       text-[34px] leading-[1.25] tracking-[-.03em] max-w-[22ch]
                       [text-wrap:balance]">
          What do you want to make?
        </h1>

        {/* **Square, 660px, and it looks like a terminal because that is the drawing.** The
            chevron and the cursor are what make it read as something you type into — without
            them a disabled input is just a grey box, which is exactly how it looked. */}
        <label
          htmlFor="goal"
          data-testid="goal-bar"
          className="settle w-[min(660px,100%)] flex items-center gap-3 px-[18px] py-[15px]
                     cursor-not-allowed"
          style={{ background: "var(--paper-2)", border: "1px solid var(--link-line)",
                   animationDelay: "120ms" }}
        >
          <span aria-hidden className="font-data text-[14px]"
                style={{ color: "var(--link)" }}>&rsaquo;</span>
          {/* **Not `grow`.** The artboard sets the chevron, the text and the cursor as three
              flex children at their natural widths, so the cursor sits immediately after the
              sentence the way a terminal's does. Stretching the input pinned the cursor to the
              far right edge of a 660px bar, 400px from the text it belongs to. */}
          <input
            id="goal"
            disabled
            size={44}
            className="bg-transparent border-0 outline-none text-[15px] cursor-not-allowed
                       max-w-full placeholder:text-[color:var(--ink-4)]"
            placeholder="gene counts from paired-end RNA-seq of mouse liver"
          />
          {/* The blinking block. `steps(1)` — it snaps rather than fading, which is what a
              terminal cursor does and what the artboard specifies. */}
          <span aria-hidden className="font-data text-[15px] blink"
                style={{ color: "var(--link)" }}>▮</span>
        </label>

        {/* **12.5px and ONE line**, which is the artboard's whole shape for this row: a quiet
            aside under the bar, not a paragraph. It shipped as three lines explaining door 1 at
            the width of the page — every word true, and the wrong weight for the last thing on
            a first-run screen. The reason stays (it belongs under the control, `Walk.tsx`), the
            argument behind it moved to this file's header where it can be as long as it needs.

            The artboard's second route — *start from a published pipeline* — is **not** drawn:
            there is no such screen, and a link going nowhere is what `Shell.tsx` records as the
            mistake 3A shipped six of. */}
        <p className="settle m-0 text-center text-[12.5px] text-ink-3"
           style={{ animationDelay: "220ms" }}>
          Describing it in words is not built yet — for now,{" "}
          <Link to="/build" className="text-[var(--link)] no-underline hover:text-ink">
            build it by hand
          </Link>.
        </p>
      </div>
    </div>
  );
}
