import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate } from "react-router";

import { get } from "../api/client";
import type { AiHealth, BeginAuthoring } from "../api/types";
import { useBegin } from "./useBegin";

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
 * ═══ THE PROMPT IS LIVE WHEN A MODEL IS, AND SAYS SO WHEN IT IS NOT ═══════════════════════
 *
 * Turning a sentence into a `Goal` is **door 1**, and it exists as of the living pipeline. It was
 * drawn disabled from 2026-08-30, the operator's decision, because nothing implemented it; it is
 * enabled only when `/health/ai` says a model is configured. **Without one the bar stays drawn and
 * disabled with that sentence under it**, because a laboratory that sets no model has chosen the
 * no-AI lane and `draw it yourself` is still the whole of what works for them.
 *
 * The two cards are `LivingOpen`'s: **one choice, two policies over one engine.** The mode is the
 * only thing it sends beside the sentence — it selects no different route or component.
 *
 * **What must not happen is the model producing a pipeline.** The assistant writes a GOAL,
 * never a graph, and the person corrects the goal card before anything is built.
 *
 * *Sends* is the artboard's last row and it is a promise the payload keeps: `BeginAuthoring` has a
 * prompt and a mode, and no field that could carry a filename.
 */
const MODES = [
  { mode: "build", title: "Build step by step", short: "You choose at each real decision.",
    long: "Every step is shown with the reason it is there, and the alternatives that would also fit." },
  { mode: "spawn", title: "Spawn the whole thing", short: "It makes the safe choices and stops where it cannot.",
    long: "Same engine, same pipeline. It only stops where a person genuinely has to answer." },
] as const;

export function First() {
  const navigate = useNavigate();
  const [prompt, setPrompt] = useState("");
  const [mode, setMode] = useState<BeginAuthoring["mode"]>("build");
  const health = useQuery({
    queryKey: ["health", "ai"],
    queryFn: () => get<AiHealth>("/health/ai"),
    retry: false,
  });
  const live = health.data?.configured === true;
  const begin = useBegin((started) => navigate(`/build?session=${started.session.id}`));
  const ready = live && prompt.trim().length > 0 && !begin.isPending;

  return (
    <div className="relative overflow-auto">
      <form
        aria-label="describe an analysis"
        onSubmit={(e) => {
          e.preventDefault();
          if (ready) begin.mutate({ prompt: prompt.trim(), mode });
        }}
        className="relative min-h-full flex flex-col items-center justify-center gap-[30px] gutter pb-20"
      >
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
          className={`settle w-[min(660px,100%)] flex items-center gap-3 px-[18px] py-[15px]
                      ${live ? "cursor-text" : "cursor-not-allowed"}`}
          style={{ background: "var(--paper-2)", border: "1px solid var(--link-line)",
                   animationDelay: "120ms" }}
        >
          <span aria-hidden className="font-data text-[14px]"
                style={{ color: "var(--link)" }}>&rsaquo;</span>
          {/* **Not `grow`, and sized to its own content.** The artboard sets the chevron, the
              text and the cursor as three flex children at their natural widths, so the cursor
              sits immediately after the sentence the way a terminal's does. Stretching the
              input pinned the cursor to the far right edge of a 660px bar, 400px from the text
              it belongs to.

              `field-sizing: content` is what closes the last of that gap: `size` counts
              *average* character widths, which in a proportional face leaves the box wider than
              the words in it. `size` stays as the fallback for a browser without it — the
              cursor then sits a little further out, which is a smaller wrong than a control
              with no width at all. */}
          <input
            id="goal"
            disabled={!live || begin.isPending}
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            aria-label="what do you want to make?"
            size={44}
            className="bg-transparent border-0 outline-none text-[15px] text-ink disabled:cursor-not-allowed
                       max-w-full [field-sizing:content]
                       placeholder:text-[color:var(--ink-4)]"
            placeholder="gene counts from paired-end RNA-seq of mouse liver"
          />
          {/* The blinking block. `steps(1)` — it snaps rather than fading, which is what a
              terminal cursor does and what the artboard specifies. */}
          <span aria-hidden className="font-data text-[15px] blink"
                style={{ color: "var(--link)" }}>▮</span>
        </label>

        {live && (
          <div role="radiogroup" aria-label="how to build it" className="settle w-[min(660px,100%)] flex flex-wrap gap-3"
               style={{ animationDelay: "180ms" }}>
            {MODES.map((option) => {
              const chosen = mode === option.mode;
              return (
                <button key={option.mode} type="button" role="radio" aria-checked={chosen}
                        data-testid={`mode-${option.mode}`}
                        onClick={() => setMode(option.mode)}
                        className="lift flex-1 min-w-[240px] flex gap-[11px] px-[17px] py-[15px] text-left cursor-pointer
                                   focus-visible:shadow-[var(--ring)]"
                        style={{ border: `1px solid ${chosen ? "var(--link-line)" : "var(--line)"}`,
                                 background: chosen ? "var(--paper-2)" : "transparent" }}>
                  <span aria-hidden className="w-[9px] h-[9px] flex-none mt-[3px]"
                        style={{ border: `1px solid ${chosen ? "var(--link)" : "var(--line-2)"}`,
                                 background: chosen ? "var(--link)" : "transparent",
                                 boxShadow: chosen ? "inset 0 0 0 2px var(--paper)" : undefined }} />
                  <span>
                    <span className="block text-[14px] font-semibold tracking-[-.01em] text-ink">{option.title}</span>
                    <span className="block text-[12px] text-ink-3 pt-[3px]">{option.short}</span>
                    <span className="block text-[12px] text-ink-2 leading-[1.5] pt-[6px]">{option.long}</span>
                  </span>
                </button>
              );
            })}
          </div>
        )}

        <div className="settle w-[min(660px,100%)] flex flex-wrap items-center gap-4"
             style={{ animationDelay: "240ms" }}>
          {live && (
            <button type="submit" data-testid="start-building" disabled={!ready}
                    className="px-[22px] py-[10px] border-0 cursor-pointer font-semibold text-[13.5px]
                               bg-[var(--link)] text-paper disabled:cursor-not-allowed disabled:opacity-40">
              {begin.isPending ? "Starting…" : "Start building"}
            </button>
          )}
          <span className="text-[12.5px] text-ink-3" data-testid="first-aside">
            {live ? "or " : health.isPending
              ? "Checking whether a model is configured — meanwhile, "
              : "No model is configured on this installation, so describing it in words is off — "}
            <Link to="/build" className="text-[var(--link)] no-underline hover:text-ink">
              draw it yourself
            </Link>
            {" "}— the canvas without a conversation
          </span>
        </div>
        {begin.error && (
          <p role="alert" className="m-0 w-[min(660px,100%)] text-[12.5px] text-[var(--undecided)]">
            {begin.error.message}
          </p>
        )}

        {live && (
          <div className="settle w-[min(660px,100%)] flex gap-[9px] items-baseline pt-[14px]"
               style={{ animationDelay: "300ms", borderTop: "1px solid var(--line)" }}>
            <span className="font-data text-[9.5px] tracking-[.12em] uppercase text-ink-4">Sends</span>
            <span className="text-[11.5px] leading-[1.5] text-ink-4">
              Your sentence, and nothing else. No filenames, no sample names, no paths — those belong
              to the run, not the pipeline.
            </span>
          </div>
        )}
      </form>
    </div>
  );
}
