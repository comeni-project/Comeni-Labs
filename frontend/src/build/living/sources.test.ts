import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

/** Scans over the living builder's source files — excluded from `tsconfig.app.json`, like
 *  `tokens.test.ts`, because they read the filesystem with Node's own modules.
 *
 * **They lived inside two component tests for two commits, and that broke `tsc -b`**: the app
 * config has no Node types, so `node:fs` and `__dirname` did not resolve. It went unnoticed because
 * the typecheck being run was `tsc --noEmit -p .`, and the root `tsconfig.json` is `files: []` with
 * project references — a command that checks nothing and exits clean. The precedent was already in
 * this directory's parent: `norule.test.ts` sits on the same exclude list for the same reason.
 */

const HERE = __dirname;

function sources(): string[] {
  return readdirSync(HERE, { recursive: true })
    .map(String)
    .filter((f) => /\.tsx?$/.test(f) && !/\.test\./.test(f));
}

describe("what is kept in the browser", () => {
  it("writes nothing about a session to localStorage", () => {
    // The prompt and the transcript are durable on the server. A browser copy would be a second
    // record of what somebody typed about their analysis, on a machine the platform does not
    // control, and it would outlive the session it came from.
    const files = sources();
    expect(files.length).toBeGreaterThan(5);
    for (const file of files) {
      // **Use, not the word.** The first version matched the bare name and fired on the hook's
      // own docstring saying it does not do this — a scan over prose firing on the sentence that
      // protects it, which `CLAUDE.md` records twice already.
      expect(readFileSync(join(HERE, file), "utf8"), file).not.toMatch(
        /\b(?:local|session)Storage\s*[.[]/,
      );
    }
  });
});

describe("the layout does not assume JavaScript measured anything", () => {
  it("reads no viewport size in any living component — breakpoints are CSS", () => {
    const files = sources();
    expect(files.length).toBeGreaterThan(5);
    for (const file of files) {
      const text = readFileSync(join(HERE, file), "utf8");
      expect(text, file).not.toMatch(/\b(?:innerWidth|innerHeight|matchMedia|ResizeObserver)\b/);
    }
  });

  it("declares the artboards' breakpoints in the stylesheet", () => {
    const css = readFileSync(join(HERE, "../../main.css"), "utf8");
    expect(css).toMatch(/\.living\s*\{[^}]*grid-template-columns:\s*minmax\(0,\s*1fr\)\s*420px/);
    expect(css).toMatch(/@media \(max-width: 1180px\)\s*\{\s*\.living/);
    expect(css).toMatch(/@media \(max-width: 1000px\)[\s\S]*\.living-rail\s*\{\s*order:\s*1/);
  });
});

describe("reduced motion", () => {
  it("switches off every living animation and leaves the end state where it is", () => {
    const css = readFileSync(join(HERE, "../../main.css"), "utf8");
    const block = /@media \(prefers-reduced-motion: reduce\)\s*\{([^}]*\.living-pop[^}]*)\}/.exec(css);
    expect(block, "no reduced-motion block names the living classes").not.toBeNull();
    for (const name of ["living-pop", "living-settle", "living-draw"]) {
      expect(block![1]).toContain(name);
    }
    expect(block![1]).toMatch(/animation:\s*none/);
  });
});
