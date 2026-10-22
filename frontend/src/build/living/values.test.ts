import { describe, expect, it } from "vitest";

import type { AnsweredStep } from "../useBuilder";
import { valuesOf } from "./values";

const setting = (name: string, tier: number, answered = false, optional = false,
                 evidence: string | null = tier === 3 ? "measured" : null) =>
  ({ name, value: tier === 4 && !answered ? null : "x", via: "ext", tier, reason: "r", because: "",
     axis_reason: "", premise: [], answered, optional, evidence });

const step = (id: string, settings: ReturnType<typeof setting>[]) =>
  ({ id, process: id.toUpperCase(), contract_id: `c/${id}`, runs: "once", tier: 2, reason: "", ports: [],
     settings }) as unknown as AnsweredStep;

describe("how a pipeline's values were decided", () => {
  it("counts settled by rule or convention, measured, and open", () => {
    const steps = [
      step("a", [setting("s1", 1), setting("s2", 2), setting("s3", 3)]),
      step("b", [setting("s4", 4), setting("s5", 4, true), setting("s6", 3)]),
    ];
    expect(valuesOf(steps)).toEqual({ total: 6, settled: 3, measured: 2, open: 1, optional: 0, read: 0 });
  });

  it("counts nothing for a pipeline with no settings", () => {
    expect(valuesOf([step("a", [])])).toEqual({ total: 0, settled: 0, measured: 0, open: 0, optional: 0, read: 0 });
  });

  it("counts an unanswered optional value apart from one that needs the person (issue 384)", () => {
    const steps = [step("a", [setting("s1", 4, false, true), setting("s2", 4), setting("s3", 1)])];
    expect(valuesOf(steps)).toEqual({ total: 3, settled: 1, measured: 0, open: 1, optional: 1, read: 0 });
  });

  it("counts a rule's value as measured only when what it read was measured (issue 397)", () => {
    const steps = [step("a", [
      setting("typed", 3, false, false, "not_measured"),
      setting("read", 3, false, false, "read_by_ai"),
      setting("sampled", 3, false, false, "measured"),
      setting("unknown", 3, false, false, null),
    ])];
    expect(valuesOf(steps)).toEqual({ total: 4, settled: 2, measured: 1, open: 0, optional: 0, read: 1 });
  });
});
