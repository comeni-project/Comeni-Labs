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
  it("stills the agent's working dot, whose words already say it is working", () => {
    const css = readFileSync(join(HERE, "../../main.css"), "utf8");
    expect(css).toMatch(/@media \(prefers-reduced-motion: reduce\)\s*\{\s*\.agent-pulse, \.agent-arrive\s*\{\s*animation:\s*none/);
  });
});

describe("a step's card stays inside the canvas (plan 2 review)", () => {
  it("clamps its left, its top and its height in the stylesheet, from where the step is", () => {
    const css = readFileSync(join(HERE, "../../main.css"), "utf8");
    const rule = /\.step-beside \{([^}]*)\}/.exec(css)?.[1] ?? "";
    expect(rule).toMatch(/left: max\(8px, min\(var\(--card-x\)/);
    expect(rule).toMatch(/top: max\(12px, min\(var\(--card-y\)/);
    expect(rule).toMatch(/max-height: calc\(100% - max\(12px, min\(var\(--card-y\)/);
  });
});

describe("the pipeline file's AI on a narrow screen (plan 2 review)", () => {
  it("stacks the AI panel under the file rather than hiding where its answers land", () => {
    const css = readFileSync(join(HERE, "../../main.css"), "utf8");
    const narrow = /@media \(max-width: 900px\) \{([\s\S]*?)\n\}/.exec(css)?.[1] ?? "";
    expect(narrow).toContain(".pipeline-file");
    expect(narrow).not.toMatch(/file-aside[^}]*display: none/);
    expect(narrow).toMatch(/\.file-aside \{[^}]*height/);
  });
});
