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
    // **`Submit.tsx` is the one place a path is legitimate, and the guard caught it — which is
    // how the boundary got drawn properly rather than assumed.**
    //
    // The run sheet is where a laboratory supplies ITS OWN data, and those values go to Wiener
    // as a RUN's parameters: they fill the artifact's declared nulls and never enter the graph
    // or `pipeline.yml` (`wiener.md` §12). Invariant 15 is about what MENDEL receives — the
    // `Goal` holds a shape — and a run is the other side of `execution-boundary.md`.
    //
    // An allowlist of one, named, with the reason: the same shape as
    // `artifacts.SUPPLIED_BY_WIENER`. If a second file ever needs to be here, that is a
    // conversation rather than an edit.
    const BINDS_A_RUN = new Set(["Submit.tsx"]);

    const dir = join(import.meta.dirname, ".");
    const offenders: string[] = [];
    for (const entry of readdirSync(dir)) {
      if (!/\.tsx?$/.test(entry) || /\.test\.tsx?$/.test(entry)) continue;
      if (BINDS_A_RUN.has(entry)) continue;
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


describe("invariant 15, on the screen that draws a pipeline", () => {
  it("offers no control that takes a filesystem path", () => {
    // **`impl-inv`: invariant 15 decides the input design.** *No input accepts a sample
    // identifier, filename or path. The `Goal` holds a SHAPE* — so a source node carries a TYPE
    // and never a path, and the binding lives with the RUN. Same pipeline, different data, no
    // edit. *If a path ever reaches `pipeline.yml`, the product's central promise is gone. This
    // is not a style choice.*
    //
    // The binding itself is `SubmitPanel`'s and it is correct: Wiener reads the artifact's own
    // declared nulls, and the values go to a RUN rather than into the graph. What this holds is
    // the other half — that the BUILDER never grows a field for one. The cheapest possible check
    // on the most expensive possible mistake.
    //
    // `type="file"` is the obvious shape; a placeholder or label mentioning a path is the one
    // somebody would actually write while meaning well.
    // **`Submit.tsx` is the one place a path is legitimate, and the guard caught it — which is
    // how the boundary got drawn properly rather than assumed.**
    //
    // The run sheet is where a laboratory supplies ITS OWN data, and those values go to Wiener
    // as a RUN's parameters: they fill the artifact's declared nulls and never enter the graph
    // or `pipeline.yml` (`wiener.md` §12). Invariant 15 is about what MENDEL receives — the
    // `Goal` holds a shape — and a run is the other side of `execution-boundary.md`.
    //
    // An allowlist of one, named, with the reason: the same shape as
    // `artifacts.SUPPLIED_BY_WIENER`. If a second file ever needs to be here, that is a
    // conversation rather than an edit.
    const BINDS_A_RUN = new Set(["Submit.tsx"]);

    const dir = join(import.meta.dirname, ".");
    const offenders: string[] = [];
    for (const entry of readdirSync(dir)) {
      if (!/\.tsx?$/.test(entry) || /\.test\.tsx?$/.test(entry)) continue;
      if (BINDS_A_RUN.has(entry)) continue;
      const text = readFileSync(join(dir, entry), "utf8")
        .replace(/\/\*[\s\S]*?\*\//g, "")
        .replace(/(^|[^:])\/\/.*$/gm, "$1");
      if (/type=\s*["'`]file/.test(text)) offenders.push(`${entry}: a file input`);
      if (/(placeholder|aria-label)\s*=\s*["'`][^"'`]*(path|filename|samplesheet)/i.test(text)) {
        offenders.push(`${entry}: a control asking for a path`);
      }
    }
    expect(offenders).toEqual([]);
  });
});
