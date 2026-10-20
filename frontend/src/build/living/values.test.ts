import { describe, expect, it } from "vitest";

import type { AnsweredStep } from "../useBuilder";
import { valuesOf } from "./values";

const setting = (name: string, tier: number, answered = false) =>
  ({ name, value: tier === 4 && !answered ? null : "x", via: "ext", tier, reason: "r", because: "",
     axis_reason: "", premise: [], answered });

const step = (id: string, settings: ReturnType<typeof setting>[]) =>
  ({ id, process: id.toUpperCase(), contract_id: `c/${id}`, runs: "once", tier: 2, reason: "", ports: [],
     settings }) as unknown as AnsweredStep;

describe("how a pipeline's values were decided", () => {
  it("counts settled by rule or convention, measured, and open", () => {
    const steps = [
      step("a", [setting("s1", 1), setting("s2", 2), setting("s3", 3)]),
      step("b", [setting("s4", 4), setting("s5", 4, true), setting("s6", 3)]),
    ];
    expect(valuesOf(steps)).toEqual({ total: 6, settled: 3, measured: 2, open: 1 });
  });

  it("counts nothing for a pipeline with no settings", () => {
    expect(valuesOf([step("a", [])])).toEqual({ total: 0, settled: 0, measured: 0, open: 0 });
  });
});
