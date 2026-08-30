import type { ReactNode } from "react";

import { Failed } from "../ui/States";

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
 *
 * **Every step's `error` is REQUIRED, and that is the whole of the fix** — Plan 4 phase 0.
 * On 2026-08-29 the walk found *Keep* answering 500 with nothing on screen, nothing in the
 * console, and `docker logs` the only way to learn that the page's central action had failed.
 * `useKeep` was not the bug: it returned `error` then, with a comment reading *"Shown, not
 * swallowed."* `Builder.tsx` simply never passed it, and `keep` had no slot to pass it into.
 *
 * So the guard is the **type**, not a wrapper around `useMutation`: a hook that returns an error
 * cannot stop a caller from ignoring it, and a required prop can. Omitting one is a compile
 * error. `null` is the way to say *nothing failed*, and it has to be said.
 */
export type StepState = "done" | "now" | "waiting";

function Step({ name, state, note, error, children, panel }: {
  name: string; state: StepState; note?: string | null;
  /** What went wrong here, or `null`. **Required** — see the header. */
  error: string | null;
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
      {/* **Under the control that failed, and shown whatever the step's state is.** A failed
          mutation does not advance the walk, so the step it broke is still `now` or even
          `waiting` — gating this on `state` is how it would go quiet again. */}
      {error && (
        <div data-testid={`step-${name.toLowerCase()}-error`} className="pl-4">
          <Failed error={error} padded={false} />
        </div>
      )}
      {state !== "waiting" && panel && <div className="pl-4">{panel}</div>}
    </div>
  );
}

export function Walk({ draw, keep, gate, run }: {
  draw: { steps: number; problems: number };
  keep: { keptAt?: string | null; stale?: string | null; onKeep?: () => void; busy?: boolean;
          error: string | null };
  gate: { passed: boolean; note?: string | null; blocked?: string | null;
          panel?: ReactNode; error: string | null };
  run: { sent: boolean; note?: string | null; blocked?: string | null;
         onSend?: () => void; panel?: ReactNode; error: string | null };
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
        // Drawing is local state and reaches no server, so there is nothing here to fail.
        // Written as an explicit `null` rather than an optional prop: the point of the slot is
        // that every step has to answer the question.
        error={null}
        note={drawn
          ? `${draw.steps} steps · ${draw.problems ? `${draw.problems} problems` : "no problems"}`
          : "nothing drawn yet"}
      />

      <Step
        name="Keep"
        error={keep.error}
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
        error={gate.error}
        state={gate.passed ? "done" : kept ? "now" : "waiting"}
        note={gate.blocked ?? gate.note}
        panel={gate.panel}
      >
        {/* **No buttons here.** `gate.panel` is `GatePanel`, which renders `Gate`, which
            renders Lint and Preview already — with the state these could not have: whether a
            gate is mid-run, the verdict colour, and the blocked reason as a title. Rendering a
            plain pair beside it drew the step twice, a dead pair above a live one. */}
      </Step>

      <Step
        name="Run"
        error={run.error}
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
