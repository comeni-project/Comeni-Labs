import { expect, it } from "vitest";

import type { components } from "../api/schema";
import type { components as wiener } from "../wiener/api/schema";
import { jumpTargets } from "./jump";

type DraftRow = components["schemas"]["DraftRow"];
type RunRow = wiener["schemas"]["RunRow"];

const draft = (id: string, name: string, updated_at: string, steps = 6) =>
  ({ id, name, updated_at, steps }) as DraftRow;
const run = (id: string, name: string, phase = "running") =>
  ({ id, name, phase, submitted_at: "2026-10-19T09:00:00Z" }) as RunRow;

const DRAFTS = [
  draft("d1", "rnaseq-star", "2026-10-18T10:00:00Z"),
  draft("d2", "chip-peaks", "2026-10-19T10:00:00Z", 3),
];
const RUNS = [run("b71e04d2aaaa", "star-test"), run("c0ffee000000", "", "failed")];

it("matches a pipeline by name and a run by name, ignoring case", () => {
  const found = jumpTargets("STAR", DRAFTS, RUNS);
  expect(found.pipelines.map((t) => t.id)).toEqual(["d1"]);
  expect(found.runs.map((t) => t.id)).toEqual(["b71e04d2aaaa"]);
});

it("matches a run by the start of its id", () => {
  expect(jumpTargets("c0ff", DRAFTS, RUNS).runs.map((t) => t.id)).toEqual(["c0ffee000000"]);
});

it("names a run without a name by its short id", () => {
  const unnamed = jumpTargets("c0ff", DRAFTS, RUNS).runs[0];
  expect(unnamed.label).toBe("run c0ffee00");
  expect(unnamed.detail).toBe("failed");
  expect(unnamed.phase).toBe("failed");
});

it("lists at most eight of each", () => {
  const many = Array.from({ length: 9 }, (_, i) => draft(`p${i}`, `star-${i}`, `2026-10-0${i + 1}T00:00:00Z`));
  expect(jumpTargets("star", many, []).pipelines).toHaveLength(8);
});

it("lists the newest pipelines first when nothing is typed", () => {
  const found = jumpTargets("", DRAFTS, RUNS);
  expect(found.pipelines.map((t) => t.id)).toEqual(["d2", "d1"]);
  expect(found.runs.map((t) => t.id)).toEqual(["b71e04d2aaaa", "c0ffee000000"]);
});

it("goes where Home's links go", () => {
  const found = jumpTargets("", DRAFTS, RUNS);
  expect(found.pipelines[0]).toMatchObject({ kind: "pipeline", to: "/build?draft=d2", label: "chip-peaks", detail: "3 steps" });
  expect(found.runs[0]).toMatchObject({ kind: "run", to: "/runs/b71e04d2aaaa", label: "star-test",
    when: "2026-10-19T09:00:00Z" });
});
