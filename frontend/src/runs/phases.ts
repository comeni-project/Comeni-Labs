/** How a run's phase is drawn. One vocabulary, shared by the board and the run page.
 *
 * **The same language the rest of the product uses**: `--pea` is settled, `--measured` is
 * working-but-unfinished, `--undecided` is a person is needed. A run does not get a colour set
 * of its own — `dashboard.md` §2 is authoritative, and a second palette would mean a reader
 * learns the product twice.
 */
export const PHASES = [
  "queued", "launching", "running", "succeeded", "failed", "cancelled", "lost",
] as const;

export type Phase = (typeof PHASES)[number];

/** The token each phase is drawn in. `lost` shares `--undecided` with `failed` deliberately:
 * a head process that vanished is a run somebody has to look at, which is the same call to
 * action, and inventing an eighth hue to say "differently bad" is the drift tokens.css exists
 * to stop. The word beside it is what distinguishes them. */
export const colourOf: Record<Phase, string> = {
  queued: "var(--ink-3)",
  launching: "var(--ink-3)",
  // **`--running`, which exists for exactly this and was not being used.** The artboards
  // paint a running phase `#BD6DCD` — the pill, the elapsed and the timeline's live bars all
  // in one colour — and this said `--measured`, the amber that means *a rule matched measured
  // data*. So a running pill claimed a tier and `Timeline.tsx` drew its running bars purple
  // beside it: two answers to *what does running look like* on one screen.
  running: "var(--running)",
  succeeded: "var(--pea)",
  failed: "var(--undecided)",
  cancelled: "var(--ink-3)",
  lost: "var(--undecided)",
};

export function isPhase(value: string): value is Phase {
  return (PHASES as readonly string[]).includes(value);
}
