/** How long a run has been going, from milliseconds a fold produced.
 *
 * **Formatting only — no clock is read for the ELAPSED of a finished run.** A run that ended
 * has both ends recorded, so its elapsed is a subtraction and renders the same forever. Only a
 * running one needs `now`, and it is passed in rather than read here, for the same reason
 * `wiener-core` refuses one: a value that changes depending on when you look at it cannot be
 * asserted in a test.
 */
export function elapsed(startedMs: number | null, endedMs: number | null, nowMs: number): string {
  if (!startedMs) return "—";
  const seconds = Math.max(0, Math.round(((endedMs ?? nowMs) - startedMs) / 1000));
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  if (hours) return `${hours}h ${String(minutes).padStart(2, "0")}m`;
  if (minutes) return `${minutes}m ${String(seconds % 60).padStart(2, "0")}s`;
  return `${seconds}s`;
}
