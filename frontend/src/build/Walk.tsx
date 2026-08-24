import type { ReactNode } from "react";

/** Draw → Keep → Gate → Run, as one visible sequence.
 *
 * **Named `Walk`, not `Rail`.** `Rail.tsx` is Plan 3C's side rail — Ask, Step, Review — and the
 * W2 plan asked for a file by that name without knowing it was taken. The artboard behind this
 * one is `w2-mockups/Walk.dc.html`, so the artboard's name is the one that wins.
 *
 * **Every step derives its state from the world, never from an index.** A rail that advances a
 * counter tells you where the *interface* thinks you are; this one reads what is actually true,
 * so changing the graph after keeping it moves the sequence backwards — which is the honest
 * answer and the one a counter cannot give.
 *
 * **Why a control is off is written under it, never in a tooltip.** A disabled button with a
 * hidden reason is a dead end; the reason is the only thing that makes it a step.
 */
export type StepState = "done" | "now" | "waiting";

function Step({ name, state, note, children, panel }: {
  name: string; state: StepState; note?: string | null;
  children?: ReactNode;
  /** **Expanded in place, not in a tab.** Gate output and submit errors belong under the step
   *  that produced them — a tab elsewhere is what made this two journeys instead of one. */
  panel?: ReactNode;
}) {
  const dot = state === "done" ? "var(--pea)"
    : state === "now" ? "var(--measured)" : "var(--line-2)";
  return (
    <div
      data-testid={`step-${name.toLowerCase()}`}
      data-state={state}
      className={`flex flex-col gap-1.5 px-4 py-3 border-b border-line last:border-b-0
                  ${state === "waiting" ? "opacity-60" : ""}`}
    >
      <span className="flex items-center gap-2">
        <span aria-hidden className="inline-block w-2 h-2 rounded-full shrink-0"
              style={{ background: dot }} />
        <span className={`text-body ${state === "waiting" ? "text-ink-3" : "text-ink"}`}>
          {name}
        </span>
      </span>
      {children && <span className="flex items-center gap-2 pl-4">{children}</span>}
      {note && <span className="pl-4 text-label text-ink-3">{note}</span>}
      {state !== "waiting" && panel && <div className="pl-4">{panel}</div>}
    </div>
  );
}

export function Walk({ draw, keep, gate, run }: {
  draw: { steps: number; problems: number };
  keep: { keptAt?: string | null; stale?: string | null; onKeep?: () => void; busy?: boolean };
  gate: { passed: boolean; note?: string | null; blocked?: string | null;
          onLint?: () => void; onPreview?: () => void; panel?: ReactNode };
  run: { sent: boolean; note?: string | null; blocked?: string | null;
         onSend?: () => void; panel?: ReactNode };
}) {
  const drawn = draw.steps > 0;
  const kept = Boolean(keep.keptAt) && !keep.stale;

  const control = `text-secondary px-2 py-1 rounded-[var(--r)] border border-line bg-surface
                   cursor-pointer disabled:cursor-not-allowed disabled:opacity-40
                   hover:bg-[var(--hover)]`;

  return (
    <div data-testid="walk" className="bg-surface border border-line rounded-[var(--r)]
                                        shadow-e2 overflow-hidden">
      <Step
        name="Draw"
        state={drawn ? "done" : "now"}
        note={drawn
          ? `${draw.steps} steps · ${draw.problems ? `${draw.problems} problems` : "no problems"}`
          : "nothing drawn yet"}
      />

      <Step
        name="Keep"
        state={kept ? "done" : drawn ? "now" : "waiting"}
        note={keep.stale ?? (keep.keptAt ? `kept ${keep.keptAt}` : "not kept yet")}
      >
        <button type="button" className={control} disabled={!drawn || keep.busy}
                onClick={keep.onKeep} style={{ transition: `background-color var(--t)` }}>
          {keep.busy ? "Keeping…" : "Keep"}
        </button>
      </Step>

      <Step
        name="Gate"
        state={gate.passed ? "done" : kept ? "now" : "waiting"}
        note={gate.blocked ?? gate.note}
        panel={gate.panel}
      >
        <button type="button" className={control} disabled={!kept} onClick={gate.onLint}
                style={{ transition: `background-color var(--t)` }}>Lint</button>
        <button type="button" className={control} disabled={!kept} onClick={gate.onPreview}
                style={{ transition: `background-color var(--t)` }}>Preview</button>
      </Step>

      <Step
        name="Run"
        state={run.sent ? "done" : gate.passed ? "now" : "waiting"}
        note={run.blocked ?? run.note}
        panel={run.panel}
      >
        <button type="button" className={control} disabled={!gate.passed} onClick={run.onSend}
                style={{ transition: `background-color var(--t)` }}>
          Send to Wiener
        </button>
      </Step>
    </div>
  );
}
