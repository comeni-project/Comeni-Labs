/** Spawn's staged reveal: once on first arrival, never again on reload.
 *
 * A Spawn session can arrive with a whole pipeline already built. Showing it all at once loses the
 * one thing the reveal is for — that each step arrived by a decision, in order — and replaying ten
 * seconds of animation on every reload is a page that makes somebody wait to see what they already
 * saw. So the reveal plays over the steps accepted **since this tab last looked**, and remembers
 * how many that was.
 *
 * **Only a count is stored, and only in `sessionStorage`** — Task 12's rule, and the one exception
 * to this directory's storage guard, which names this file. The transcript and the prompt stay on
 * the server; a number of steps seen identifies nothing and dies with the tab.
 */

const KEY = (sessionId: string) => `comeni-living-seen:${sessionId}`;

/** How long the whole reveal may take, however long the pipeline is. */
export const REVEAL_CAP_MS = 2400;
/** The longest pause between two columns, for a short pipeline that would otherwise crawl. */
export const REVEAL_STEP_MS = 180;

/** How many accepted steps this tab has already seen for a session, or `null` on first arrival. */
export function lastSeen(sessionId: string): number | null {
  try {
    const raw = window.sessionStorage.getItem(KEY(sessionId));
    const seen = raw === null ? NaN : Number(raw);
    return Number.isInteger(seen) && seen >= 0 ? seen : null;
  } catch {
    return null;
  }
}

/** Remember how many accepted steps have been seen. A number, and nothing else. */
export function markSeen(sessionId: string, count: number): void {
  try {
    window.sessionStorage.setItem(KEY(sessionId), String(Math.max(0, Math.floor(count))));
  } catch {
    // Storage may be blocked; the only cost is replaying the reveal once more.
  }
}

/** A delay per step, in reveal order — **grouped by column, capped in total**.
 *
 * Steps that share a column appear together, which is how a burst of siblings reads as one moment
 * rather than a stutter. The pause between columns shrinks for a long pipeline so the whole reveal
 * never exceeds `REVEAL_CAP_MS`; under reduced motion the animation is `none` in CSS and every step
 * is simply there.
 */
export function revealPlan(
  steps: string[],
  columnOf: (step: string) => number,
): Record<string, number> {
  const columns = [...new Set(steps.map(columnOf))].sort((a, b) => a - b);
  if (columns.length === 0) return {};
  const pause = Math.min(REVEAL_STEP_MS, Math.floor(REVEAL_CAP_MS / columns.length));
  const indexOf = new Map(columns.map((column, index) => [column, index]));
  return Object.fromEntries(steps.map((step) => [step, (indexOf.get(columnOf(step)) ?? 0) * pause]));
}
