import { expect, it } from "vitest";

import { stagesOf, statusOf, type Progress } from "./stages";

const base: Progress = { phase: "reviewing", waiting: 0, drafting: false, tests_failed: 0, tests_passed: 0,
                         tests_total: 0, pull_request: null };

it("a forging with AI choices waiting is on its tool, with how many to review", () => {
  const [tool, tests, publish] = stagesOf({ ...base, waiting: 3 });
  expect([tool.state, tool.note]).toEqual(["now", "3 to review"]);
  expect(tests.state).toBe("later");
  expect(publish.state).toBe("later");
  expect(statusOf(stagesOf({ ...base, waiting: 3 })).note).toBe("3 to review");
});

it("a failed test is the line to show, ahead of anything else", () => {
  const stages = stagesOf({ ...base, phase: "assembled", tests_failed: 1, tests_passed: 1, tests_total: 2 });
  expect(stages.map((s) => s.state)).toEqual(["done", "failed", "later"]);
  expect(statusOf(stages).note).toBe("1 test failed");
});

it("merged is done all through, waiting for a release", () => {
  const stages = stagesOf({ ...base, phase: "merged", tests_passed: 2, tests_total: 3, pull_request: "merged" });
  expect(stages.map((s) => s.state)).toEqual(["done", "done", "done"]);
  expect(stages[1].note).toBe("2 passed · 1 not run");
  expect(statusOf(stages).note).toBe("merged · next release");
});
