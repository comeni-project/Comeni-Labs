import { expect, it } from "vitest";

import { numbered, type RunRow } from "./model";

const run = (id: string, at: string, analysis: string, digest: string) =>
  ({ id, submitted_at: at, analysis, pipeline_digest: digest, phase: "succeeded" }) as unknown as RunRow;

it("lists an analysis's runs by the analysis that sent them, its pipeline changed since (#536)", () => {
  const runs = [run("r1", "2026-11-17T10:00", "d1", "old"), run("r2", "2026-11-17T11:00", "d1", "new"),
                run("x", "2026-11-17T12:00", "d2", "new")];
  expect(numbered(runs, "new", "d1").map(({ run: r, n }) => [r.id, n])).toEqual([["r2", 2], ["r1", 1]]);
});

it("still places a run sent before runs carried their analysis, by its digest", () => {
  const runs = [run("old", "2026-11-16T10:00", "", "kept")];
  expect(numbered(runs, "kept", "d1").map(({ n }) => n)).toEqual([1]);
  expect(numbered(runs, "other", "d1")).toEqual([]);
});
