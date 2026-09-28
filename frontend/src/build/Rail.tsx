import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router";

import { get } from "../api/client";
import type { AiHealth, BeginAuthoring } from "../api/types";
import { MODES } from "../home/modes";
import { useBegin } from "../home/useBegin";
import type { Answered, AnsweredStep } from "./useBuilder";
import { open as isOpen } from "./useBuilder";

/** **The rail is about the CHOICE. The card on the node is about the VALUES.**
 *
 * `impl-settled` is explicit, and this file is where it lands:
 *
 * > SETTINGS LIVE IN THE CARD ON THE NODE, not the rail. The rail is about the CHOICE — what
 * > this step is, why this tool, swap it. The card is about the VALUES. Two lists of the same
 * > thing is what we just removed.
 *
 * It shipped rendering `<Settings>` inside a Step tab **and** a Review tab listing every open
 * value across every step — so a parameter appeared in three places, and the two in here were
 * the ones nobody could act on without scrolling away from the node they were about. Both are
 * gone. What replaced the Review tab is not nothing: **invariant 6's four places are the node,
 * the status line, the settings card and the run sheet** (`impl-inv`), and the rail is not among
 * them. A red left edge on the canvas says which step, the status line says how many, and the
 * card says which values — each answering a different question rather than three answering one.
 *
 * **This file no longer owns any tabs.** It had its own strip of three underneath `Builder`'s
 * strip of three, underneath the `Side` header, underneath the gate panel: four stacked bands of
 * chrome above the first sentence anybody wanted to read. The artboard draws **one** strip, so
 * `Builder` owns it and the two exports here are bodies.
 */
export function StepChoice({
  step,
  onSwap,
  onOpenSettings,
}: {
  step: AnsweredStep | undefined;
  /** Offer to replace this step. The rail is where a CHOICE is questioned. */
  onSwap?: (id: string) => void;
  /** Open the settings card on the node. The rail points at it; it never draws it. */
  onOpenSettings?: (id: string) => void;
}) {
  if (!step) {
    return (
      <p className="p-4 text-body text-ink-2 m-0">
        Click a step on the canvas to see what it is, why this tool, and what it is set to.
      </p>
    );
  }

  return (
    <div className="px-[18px] pt-5">
      <div className="settle">
        <div className="font-data text-object font-medium text-ink">{step.process}</div>
        <div className="font-data text-label text-ink-4 pt-1">{step.contract_id}</div>
      </div>

      <div className="settle pt-5" style={{ animationDelay: "40ms" }}>
        <div className="text-label font-data uppercase tracking-[.15em] text-ink-3 pb-[9px]">
          Why this tool
        </div>
        {/* **The resolver's own sentence, not a rewrite of it.** `reason` is what the ladder
            recorded when it chose this contract; anything composed here would be a second
            author for a decision that already has one. */}
        <div className="text-secondary text-ink-2 leading-[1.55]">
          {step.reason || "No reason recorded — this step was drawn by hand."}
        </div>
        <button
          type="button"
          data-testid="open-swap"
          onClick={() => onSwap?.(step.id)}
          className="mt-3 border border-line-2 px-3 py-2 text-body text-link bg-transparent
                     cursor-pointer lift"
        >
          Swap for something else
        </button>
      </div>

      <div className="settle pt-6" style={{ animationDelay: "80ms" }}>
        <div className="text-label font-data uppercase tracking-[.15em] text-ink-3 pb-[11px]">
          Values
        </div>
        <Values step={step} />
        <button
          type="button"
          data-testid="open-settings"
          onClick={() => onOpenSettings?.(step.id)}
          className="font-data text-secondary text-link pt-2.5 bg-transparent border-0
                     cursor-pointer p-0 lift"
        >
          open on the node ⋯
        </button>
      </div>
    </div>
  );
}

/** **Door 1 — the slot held its place until the door existed, and now it is the door.**
 *
 * The tab was static copy saying the prompt was *not wired yet*, kept because a rail that gains a
 * tab later moves every position a person had learned. The living pipeline wired it, and the tab
 * is **the only way into a living session once a lab has any pipeline**: `Home` draws the
 * first-run prompt only while there are none, and *New pipeline* opens this builder.
 *
 * So it sends exactly what `First` sends — a sentence and a mode, nothing that could carry a
 * filename — and opens the session it started. What the model writes is still a goal the person
 * confirms before anything is built; that seam now lives on the goal card in the conversation.
 */
export function Assistant() {
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
    <div data-testid="ask" className="p-4">
      <form
        aria-label="describe an analysis"
        onSubmit={(e) => {
          e.preventDefault();
          if (ready) begin.mutate({ prompt: prompt.trim(), mode });
        }}
        className="flex flex-col gap-3"
      >
        <p className="text-body text-ink m-0">
          Describe an analysis. It is read into a <b className="font-normal">goal</b> you confirm,
          then built beside a conversation.
        </p>
        <textarea
          aria-label="what do you want to make?"
          disabled={!live || begin.isPending}
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          rows={3}
          placeholder="gene counts from paired-end RNA-seq of mouse liver"
          className="w-full resize-y font-ui text-body text-ink bg-transparent border px-2 py-1.5
                     disabled:cursor-not-allowed placeholder:text-[color:var(--ink-4)]"
          style={{ borderColor: "var(--link-line)" }}
        />
        {live && (
          <div role="radiogroup" aria-label="how to build it" className="flex flex-col gap-1.5">
            {MODES.map((option) => (
              <button
                key={option.mode}
                type="button"
                role="radio"
                aria-checked={mode === option.mode}
                onClick={() => setMode(option.mode)}
                className="text-left px-2.5 py-2 border bg-transparent cursor-pointer lift
                           focus-visible:shadow-[var(--ring)]"
                style={{ borderColor: mode === option.mode ? "var(--link-line)" : "var(--line)" }}
              >
                <span className="block text-body text-ink">{option.title}</span>
                <span className="block text-secondary text-ink-3">{option.short}</span>
              </button>
            ))}
          </div>
        )}
        {live ? (
          <button
            type="submit"
            data-testid="ask-start"
            disabled={!ready}
            className="self-start px-3 py-1.5 border-0 cursor-pointer text-body font-semibold
                       bg-[var(--link)] text-paper disabled:cursor-not-allowed disabled:opacity-40"
          >
            {begin.isPending ? "Starting…" : "Start"}
          </button>
        ) : (
          <p className="text-secondary text-ink-3 m-0">
            {health.isPending
              ? "Checking whether a model is configured."
              : "No model is configured on this installation, so describing it in words is off. The canvas works without one."}
          </p>
        )}
        {begin.error && (
          <p role="alert" className="m-0 text-secondary text-[var(--undecided)]">
            {begin.error.message}
          </p>
        )}
      </form>
    </div>
  );
}

/** One sentence about a step's parameters, and a dot in the colour of the worst of them.
 *
 * **A count, not a list** — the list is the card's. What this has to get right is the *claim*:
 * `14 settings, all settled` is a strong statement and it must not be made while two of them
 * are open, which is exactly the direction invariant 6 protects.
 */
function Values({ step }: { step: AnsweredStep }) {
  const open = step.settings.filter(isOpen).length;
  const measured = step.settings.filter((one: Answered) => one.tier === 3).length;
  const total = step.settings.length;

  const worst = open > 0 ? "var(--undecided)" : measured > 0 ? "var(--measured)" : "var(--pea)";
  const said =
    total === 0
      ? "no parameters — everything is forced by the module"
      : open > 0
        ? `${total} settings, ${open} need you`
        : measured > 0
          ? `${total} settings, ${measured} measured`
          : `${total} settings, all settled`;

  return (
    <div data-testid="values-line" className="flex items-baseline gap-[9px]">
      <span className="text-[8px] leading-none" style={{ color: worst }}>
        ●
      </span>
      <span className="text-secondary text-ink-2">{said}</span>
    </div>
  );
}
