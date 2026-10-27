import { describe, expect, it } from "vitest";

import type { Answered } from "../useBuilder";
import { fileLines } from "./fileLines";
import { markOf } from "./valueMarks";

/** A slice of `tests/fixtures/pipeline-v8/pipeline.yml`: a step with no settings, then STAR's
 *  first setting, whose reason wraps onto a second line, and the start of the next. */
const FILE = `version: 8
steps:
- id: trimgalore
  module:
    contract_id: nf-core/trimgalore@2.3.0
  why:
    tier: 2
  settings: []
- id: star_align
  settings:
  - name: seq_platform
    value: null
    via: ext
    why:
      tier: 4
      reason: nothing decided 'seq_platform'; selected the first of 1 candidates without judgement
        — please review
      premise: []
  - name: star_ignore_sjdbgtf
    value: false
  inputs:
  - port: reads
channels:
- name: reads`;

const lines = FILE.split("\n");
const at = (text: string) => fileLines(FILE)[lines.findIndex((l) => l === text)];

describe("which setting each line of the file is (one builder plan 5)", () => {
  it("gives every line of a setting's block that setting, its first line the head", () => {
    expect(at("  - name: seq_platform")).toEqual({ step: "star_align", setting: "seq_platform", head: true });
    expect(at("    value: null")).toEqual({ step: "star_align", setting: "seq_platform", head: false });
    expect(at("        — please review")).toEqual({ step: "star_align", setting: "seq_platform", head: false });
    expect(at("  - name: star_ignore_sjdbgtf")).toEqual({ step: "star_align", setting: "star_ignore_sjdbgtf", head: true });
  });

  it("gives nothing to a step without settings, the step's own keys, or the top level", () => {
    expect(at("  settings: []")).toBeNull();
    expect(at("    tier: 2")).toBeNull();
    expect(at("- id: star_align")).toBeNull();
    expect(at("  inputs:")).toBeNull();
    expect(at("  - port: reads")).toBeNull();
    expect(at("- name: reads")).toBeNull();
    expect(at("version: 8")).toBeNull();
    expect(fileLines(FILE)).toHaveLength(lines.length);
  });
});

const tiers = { name: (t: number) => `tier-${t}`, group: (t: number) => `group-${t}` } as never;
const setting = (over: Partial<Answered>) => ({ name: "x", value: "1", via: "ext", tier: 2, reason: "",
  because: "", axis_reason: "", optional: false, premise: [], ...over }) as Answered;

describe("the mark on a value's line, named by its evidence (issue 397)", () => {
  it.each([
    [{ tier: 4, value: null }, "needs you", "open"],
    [{ tier: 4, value: null, optional: true }, "optional", "plain"],
    [{ tier: 4, value: "x", answered: true }, "your answer", "yours"],
    [{ tier: 3, evidence: "measured" }, "tier-3", "measured"],
    [{ tier: 3, evidence: "typed" }, "group-3", "plain"],
    [{ tier: 1 }, "tier-1", "plain"],
  ])("%o reads %s", (over, words, tone) => {
    expect(markOf(setting(over as Partial<Answered>), tiers)).toEqual({ words, tone });
  });
});
