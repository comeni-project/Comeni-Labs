import type { components } from "../api/schema";

type Summary = components["schemas"]["AdaptationSummary"];
type View = components["schemas"]["AdaptationView"];

export type StageState = "done" | "now" | "failed" | "later";
export type StageName = "tool" | "tests" | "publish";
export interface Stage { name: StageName; label: string; state: StageState; note: string }

/** What a forging's three pages need to say how far it is. */
export interface Progress {
  phase: string;
  waiting: number;
  drafting: boolean;
  tests_failed: number;
  tests_passed: number;
  tests_total: number;
  pull_request: string | null;
  /** Whether the release this installation loads carries it (the catalogue's state); unknown
   *  until the catalogue answers, and then a merge is still waiting. */
  released?: boolean;
}

const ASSEMBLED = new Set(["assembled", "testing", "tested", "publishing", "in_review", "merged"]);
const TESTED = new Set(["tested", "publishing", "in_review", "merged"]);

/** **Tool · Tests · Publish** (board "5 · Forge", "6 · Forging"): each page's state and its one
 *  status line, from the forging's phase, its waiting AI choices, its tests and its pull request. */
export function stagesOf(p: Progress): Stage[] {
  const assembled = ASSEMBLED.has(p.phase);
  const tool: Stage = {
    name: "tool", label: "Tool",
    state: assembled && p.waiting === 0 ? "done" : "now",
    note: p.drafting ? "drafting" : p.waiting ? `${p.waiting} to review` : assembled ? "reviewed" : "in progress",
  };
  const failed = p.tests_failed > 0;
  const passed = TESTED.has(p.phase) && !failed;
  const notRun = p.tests_total - p.tests_passed - p.tests_failed;
  const tests: Stage = {
    name: "tests", label: "Tests",
    state: failed ? "failed" : passed ? "done" : assembled ? "now" : "later",
    note: failed ? `${p.tests_failed} test${p.tests_failed === 1 ? "" : "s"} failed`
      : p.phase === "testing" ? "running"
      : p.tests_total ? [p.tests_passed ? `${p.tests_passed} passed` : "", notRun > 0 ? `${notRun} not run` : ""].filter(Boolean).join(" · ")
      : assembled ? "not run yet" : "after the tool",
  };
  const merged = p.phase === "merged" || p.pull_request === "merged";
  const publish: Stage = {
    name: "publish", label: "Publish",
    state: merged ? "done" : p.phase === "publishing" || p.phase === "in_review" || passed ? "now" : "later",
    note: merged ? (p.released ? "released" : "merged · next release") : p.phase === "in_review" ? "pull request open"
      : p.phase === "publishing" ? "opening a pull request" : passed ? "ready to publish" : "after the tests",
  };
  return [tool, tests, publish];
}

/** The line a forging card or the rail shows: the first page not done, or that it merged. */
export function statusOf(stages: Stage[]): Stage {
  return stages.find((s) => s.state === "failed") ?? stages.find((s) => s.state !== "done") ?? stages[2];
}

export function progressOfSummary(s: Summary): Progress {
  return { phase: s.phase, waiting: s.waiting, drafting: s.drafting, tests_failed: s.tests_failed ?? 0,
           tests_passed: 0, tests_total: 0, pull_request: s.pull_request ?? null };
}

export function progressOfView(v: View): Progress {
  const waiting = v.items.filter((i) => i.status === "proposed" || i.status === "reopened").length;
  const cases = v.items.filter((i) => i.key.startsWith("tests:test:") && i.status !== "removed").length;
  return {
    phase: v.phase, waiting,
    drafting: v.phase === "drafting" || v.phase === "asking" || v.messages.some((m) => m.pending),
    tests_failed: v.tests.filter((t) => t.state === "failed").length,
    tests_passed: v.tests.filter((t) => t.state === "passed").length,
    tests_total: Math.max(cases, v.tests.length),
    pull_request: v.pull_request?.state ?? null,
  };
}

/** Whether a module's catalogue state says the loaded release carries it. */
export const releasedOf = (state: string | undefined) => state === "imported" || state === "update_available";
