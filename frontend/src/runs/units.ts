/** How a number is spelled on a run screen.
 *
 * Lifted out of `Stats.tsx` before Task 6 deletes it. Two callers is not the reason — one
 * spelling is: `1.2 GB` and `1288490188` are the same fact, and a table where one column
 * rounds differently from the next is a table nobody can compare down.
 *
 * **`null` is a dash and never a zero.** A run launched without `trace.enabled` reports no
 * resources at all, and a `0 B` would read as *this task used no memory* — a lie about a real
 * number that a reader cannot tell from a true one. The projection keeps the distinction
 * (`wiener_core.overview`); this is where it survives being drawn.
 */

export const ABSENT = "—";

export function bytes(value: number | null | undefined): string {
  if (value === null || value === undefined) return ABSENT;
  const units = ["B", "KB", "MB", "GB", "TB"];
  let size = value, unit = 0;
  while (size >= 1024 && unit < units.length - 1) { size /= 1024; unit += 1; }
  return `${size < 10 && unit > 0 ? size.toFixed(1) : Math.round(size)} ${units[unit]}`;
}

export function seconds(ms: number | null | undefined): string {
  if (ms === null || ms === undefined) return ABSENT;
  if (ms < 1000) return `${ms}ms`;
  const total = Math.round(ms / 1000);
  return total < 60
    ? `${total}s`
    : `${Math.floor(total / 60)}m ${String(total % 60).padStart(2, "0")}s`;
}

export function percent(value: number | null | undefined): string {
  if (value === null || value === undefined) return ABSENT;
  return `${Math.round(value)}%`;
}
