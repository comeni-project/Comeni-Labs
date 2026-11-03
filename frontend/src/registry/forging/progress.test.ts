import { expect, it } from "vitest";

import { elapsed, outcomeOf, progressOf } from "./progress";

const step = (seq: number, kind: string, data: Record<string, unknown> = {}) => ({ seq, kind, data, at: "2026-11-01T10:00:00Z" });

it("shows what is happening now, and what is left", () => {
  const view = progressOf([
    step(1, "started", { what: "drafting", piece: "contract" }),
    step(2, "asking", { attempt: 1, attempts: 2, model: "gemma3:12b" }),
  ]);
  expect(view.title).toBe("Drafting the contract");
  expect(view.steps.map((s) => [s.label, s.state])).toEqual([
    ["Read the module", "done"],
    ["Asking gemma3:12b, attempt 1 of 2", "now"],
    ["The engine checks the reply", "waiting"],
  ]);
});

it("a refused attempt shows when it happens, then the retry", () => {
  const view = progressOf([
    step(1, "started", { what: "drafting", piece: "rules" }),
    step(2, "asking", { attempt: 1, attempts: 2, model: "m" }),
    step(3, "called", { attempt: 1, input_tokens: 100, output_tokens: 20, seconds: 3 }),
    step(4, "refused", { attempt: 1, problems: ["MF0507: not a port"] }),
    step(5, "asking", { attempt: 2, attempts: 2, model: "m" }),
  ]);
  expect(view.steps.map((s) => s.state)).toEqual(["done", "refused", "now", "waiting"]);
  expect(view.steps[1].label).toBe("Attempt 1 was refused");
  expect(view.steps[1].detail).toBe("MF0507: not a port");
});

it("adds up what the calls used, and says so only once it is known", () => {
  expect(progressOf([step(1, "started", { what: "replying" })]).tokens).toBeNull();
  const view = progressOf([
    step(1, "started", { what: "replying" }),
    step(2, "called", { attempt: 1, input_tokens: 100, output_tokens: 20, seconds: 3 }),
    step(3, "called", { attempt: 2, input_tokens: 50, output_tokens: 5, seconds: 2 }),
  ]);
  expect(view.tokens).toEqual({ sent: 150, received: 25 });
  expect(view.title).toBe("Writing a reply");
});

it("looks only at the latest piece of work", () => {
  const view = progressOf([
    step(1, "started", { what: "drafting", piece: "contract" }),
    step(2, "saved", { items: 3 }),
    step(3, "started", { what: "drafting", piece: "rules" }),
  ]);
  expect(view.title).toBe("Drafting the rules");
});

it("with nothing recorded yet it still says what is underway", () => {
  expect(progressOf([], "tests").title).toBe("Drafting the tests");
});

it("knows when the work began, and counts up from it", () => {
  expect(progressOf([]).since).toBeNull();
  expect(progressOf([step(1, "started", { what: "replying" })]).since).toBe("2026-11-01T10:00:00Z");
  expect(elapsed("2026-11-01T10:00:00Z", Date.parse("2026-11-01T10:01:09Z"))).toBe("1:09");
  expect(elapsed("2026-11-01T10:00:00Z", Date.parse("2026-11-01T09:59:58Z"))).toBe("0:00");
});

it("a reply that changed nothing says so, whatever its words promised", () => {
  expect(outcomeOf({ role: "ai", commands: [], pending: false })).toEqual({
    tone: "none", label: "No changes made", note: "It sent nothing the engine could apply." });
});

it("a reply that proposed something counts it, as a proposal", () => {
  expect(outcomeOf({ role: "ai", commands: [{}, {}], pending: false })?.label).toBe("2 changes proposed");
  expect(outcomeOf({ role: "ai", commands: [{}], pending: false })?.label).toBe("1 change proposed");
});

it("only the AI's replies carry an outcome", () => {
  expect(outcomeOf({ role: "person", commands: [], pending: true })).toBeNull();
  expect(outcomeOf({ role: "engine", commands: [], pending: false })).toBeNull();
});

it("names the reviewer separately from drafting", () => {
  const progress = progressOf([{ seq: 1, kind: "started", data: { what: "reviewing", piece: "questions" }, at: "2026-11-03T10:00:00Z" }]);
  expect(progress.title).toBe("The reviewer reads it");
});
