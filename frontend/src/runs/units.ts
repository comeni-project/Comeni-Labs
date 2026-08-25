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

/** `31.0 / 64 GB` — the artboard's spelling of a comparison.
 *
 * **One unit for the pair**, chosen from the larger half, because two numbers with different
 * suffixes are not a comparison a reader can make at a glance. `—` when either half is
 * missing: half a comparison invites the reader to supply a ceiling they do not have.
 */
export function pair(used: number | null | undefined, asked: number | null | undefined): string {
  if (used === null || used === undefined || asked === null || asked === undefined) return ABSENT;
  const units = ["B", "KB", "MB", "GB", "TB"];
  let unit = 0, scale = 1;
  while (asked / scale >= 1024 && unit < units.length - 1) { scale *= 1024; unit += 1; }
  const round = (value: number) => {
    const size = value / scale;
    return size < 10 && unit > 0 ? size.toFixed(1) : String(Math.round(size));
  };
  const peak = round(used);
  // **One unit, unless one unit erases the measurement.** A process peaking at 3.8 MB against
  // a 31 GB ask renders `0.0 / 31 GB` — and this table's own footer says a dash means nothing
  // was reported, *never zero*. So `0.0` asserts a measured zero the record contradicts, on a
  // screen whose whole claim is that nothing was guessed silently. Where the shared unit would
  // round a real number to nothing, spell each half in its own: comparison at a glance is worth
  // less than not lying about what was measured. Both halves still carry their suffix, so the
  // reader can see the two are orders apart rather than being quietly misled about the scale.
  if (used > 0 && Number(peak) === 0) return `${bytes(used)} / ${bytes(asked)}`;
  return `${peak} / ${round(asked)} ${units[unit]}`;
}

/** `1.2G / 31G` — read and written, kept apart. The artboard shows both because *which step
 *  moves the data* is the question, and a sum answers a different one. */
export function shortBytes(value: number | null | undefined): string {
  if (value === null || value === undefined) return ABSENT;
  const units = ["B", "K", "M", "G", "T"];
  let size = value, unit = 0;
  while (size >= 1024 && unit < units.length - 1) { size /= 1024; unit += 1; }
  return `${size < 10 && unit > 0 ? size.toFixed(1) : Math.round(size)}${units[unit]}`;
}
