import { describe, expect, it } from "vitest";

import { folds } from "./folds";

const FILE = [
  "version: 9",                                  // 0
  "intent:",                                     // 1
  "  want:",                                     // 2
  "  - counts.matrix",                           // 3
  "steps:",                                      // 4
  "- id: star_align",                            // 5
  "  module:",                                   // 6
  "    contract_id: nf-core/star/align@2.7.11b", // 7
  "    digest: sha256:abc",                      // 8
  "    source: nf-core",                         // 9
  "  why:",                                      // 10
  "    tier: 3",                                 // 11
  "    reason: read length favours STAR",        // 12
  "  settings:",                                 // 13
  "  - name: sjdbOverhang",                      // 14
  "    value: '150'",                            // 15
  "  inputs:",                                   // 16
  "  - port: reads",                             // 17
  "    source: trimgalore.reads",                // 18
  "gate: null",                                  // 19
].join("\n");

describe("what folds in the pipeline file (#499)", () => {
  it("folds a step's module, why and inputs to one summary line each, never its settings", () => {
    const found = folds(FILE).filter((f) => f.step === "star_align");
    expect(found.map((f) => [f.start, f.end, f.summary])).toEqual([
      [6, 9, "{ nf-core/star/align@2.7.11b · 4 lines }"],
      [10, 12, "{ tier 3 · read length favours STAR · 3 lines }"],
      [16, 18, "{ reads ← trimgalore · 3 lines }"],
    ]);
    expect(found.every((f) => f.folded)).toBe(true);
  });

  it("lets each top-level section fold too, open to begin with", () => {
    const top = folds(FILE).filter((f) => f.step === null);
    expect(top.map((f) => [f.key, f.start, f.end, f.folded])).toEqual([
      ["intent", 1, 3, false], ["steps", 4, 18, false],
    ]);
  });
});

it("reads a quoted reason that runs over lines, and folds a step's other keys plainly", () => {
  const text = ["steps:", "- id: a", "  why:", "    tier: 3", "    reason: 'STAR''s seed search",
    "      is fast'", "  presence:", "    tier: 1", "    source: resolver"].join("\n");
  expect(folds(text).filter((f) => f.step === "a").map((f) => f.summary)).toEqual([
    "{ tier 3 · STAR's seed search · 4 lines }", "{ 3 lines }"]);
});

it("says an input a channel feeds is fed by that channel, never `null` (plan 2 review)", () => {
  const text = ["steps:", "- id: a", "  inputs:", "  - port: gtf", "    source: null", "    channel: gtf",
    "  - port: reads", "    source: trim.reads", "    channel: null"].join("\n");
  expect(folds(text).find((f) => f.key === "inputs")!.summary).toBe("{ gtf ← channel gtf · reads ← trim · 7 lines }");
});
