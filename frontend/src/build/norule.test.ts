import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

/** The rule that decides whether a BAM can feed featureCounts lives in ONE place.
 *
 * Split out of `Picker.test.tsx` because it walks the filesystem, and the node-using scan
 * tests are excluded from `tsconfig.app.json` — `tokens.test.ts` and `reported.test.ts` set
 * that precedent. Excluding a file that also holds real component tests would take those out
 * of typechecking with it.
 */
describe("the rule lives in one place", () => {
  it("never parses a type signature in the browser", () => {
    // **The drift guard `useCompatibility.ts` asks for, made real.** Its header: *if a line here
    // ever parses a signature — splits on `[`, compares type ids, subtracts state sets — the
    // rule that decides whether a BAM can feed featureCounts lives in two places, and the second
    // one is invisible to the agreement test. That is the drift this repository has paid for
    // twice.* It asserted the absence in prose; this asserts it.
    const dir = join(import.meta.dirname, ".");
    const offenders: string[] = [];
    for (const entry of readdirSync(dir)) {
      if (!/\.tsx?$/.test(entry) || /\.test\.tsx?$/.test(entry)) continue;
      const text = readFileSync(join(dir, entry), "utf8")
        .replace(/\/\*[\s\S]*?\*\//g, "")
        .replace(/(^|[^:])\/\/.*$/gm, "$1");
      // Splitting a signature apart, or doing set arithmetic on states, are the two shapes the
      // rule takes when it is reimplemented.
      if (/\.split\(\s*["'`]\[/.test(text)) offenders.push(`${entry}: splits a signature`);
      if (/states\s*\.\s*(?:filter|every|some)\s*\(/.test(text)) {
        offenders.push(`${entry}: does state-set arithmetic`);
      }
    }
    expect(offenders).toEqual([]);
  });
});
