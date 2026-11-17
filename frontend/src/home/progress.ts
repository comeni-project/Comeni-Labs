import type { components } from "../api/schema";
import type { components as wiener } from "../wiener/api/schema";

export type Draft = components["schemas"]["DraftRow"];
export type RunRow = wiener["schemas"]["RunRow"];
export type Stage = "done" | "now" | "look" | "failed" | "none";

/** Where each analysis stands, derived here from what the two servers already say. Neither knows
 *  the other: a run belongs to an analysis by the kept pipeline's digest (`wiener.md` §12). */

export const LIVE = new Set(["queued", "launching", "running"]);

/** The newest run of each kept pipeline. */
export function latestRuns(runs: RunRow[]): Map<string, RunRow> {
  const latest = new Map<string, RunRow>();
  for (const run of runs) {
    if (!run.pipeline_digest) continue;
    const seen = latest.get(run.pipeline_digest);
    if (!seen || run.submitted_at > seen.submitted_at) latest.set(run.pipeline_digest, run);
  }
  return latest;
}

export function dataStage(d: Draft): Stage {
  if (!d.data) return "none";
  if (d.data.scan === "scanning") return "now";
  if (d.data.scan === "failed") return "failed";
  return d.data.checks > 0 ? "look" : "done";
}

export function openChoices(d: Draft): number {
  return (d.open_values ?? []).length + d.open_not_named;
}

export function buildStage(d: Draft): Stage {
  if (d.steps === 0) return "none";
  return openChoices(d) > 0 ? "look" : "done";
}

export function runStage(run: RunRow | undefined): Stage {
  if (!run) return "none";
  if (LIVE.has(run.phase)) return "now";
  if (run.phase === "succeeded") return "done";
  return run.phase === "cancelled" ? "none" : "failed";
}

export const STAGE_WORDS: Record<Stage, string> = {
  done: "done", now: "running", look: "needs a look", failed: "failed", none: "not yet",
};

export function dataLine(d: Draft): string {
  if (!d.data) return "No data yet";
  if (d.data.scan === "scanning") return "Reading the files…";
  const n = d.data.samples;
  return `${n} ${n === 1 ? "sample" : "samples"}${d.data.checks ? ` · ${d.data.checks} to check` : ""}`;
}

/** *today, 10:00*, *yesterday*, *4 days ago*, or the date. */
export function when(iso: string, now = new Date()): string {
  const then = new Date(iso);
  const days = Math.floor((startOfDay(now) - startOfDay(then)) / 86_400_000);
  if (days <= 0) return `today, ${then.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`;
  if (days === 1) return "yesterday";
  if (days < 7) return `${days} days ago`;
  return then.toLocaleDateString();
}

function startOfDay(d: Date): number {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
}

export function elapsed(iso: string, now = Date.now()): string {
  const s = Math.max(0, Math.round((now - new Date(iso).getTime()) / 1000));
  const m = Math.floor(s / 60);
  return m >= 60 ? `${Math.floor(m / 60)} h ${m % 60} min` : m > 0 ? `${m} min ${s % 60} s` : `${s} s`;
}
