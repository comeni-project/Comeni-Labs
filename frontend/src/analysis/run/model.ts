/** What Run's pages say, derived from what Wiener recorded and what the analysis is (#511). Pure:
 *  every number on Overview, the canvas and Steps comes from here, so they cannot disagree. */
import type { StepProgress } from "../../build/living/LivingNode";
import type { components as wiener } from "../../wiener/api/schema";

export type RunRow = wiener["schemas"]["RunRow"];
export type ProcessRow = wiener["schemas"]["ProcessRowOut"];
export type Task = wiener["schemas"]["TaskOut"];

/** A step of the run's graph, as `/runs/{id}/graph` draws it: its id is the pipeline's step id. */
export type RunNode = {
  id: string; process: string;
  done: number; failed: number; running: number; total: number; attempts: number;
};
export type Bar = {
  task_id: number; attempt: number; status: string;
  start_ms: number; end_ms: number | null; row: number;
};
export type Lane = { process: string; declared: boolean; bars: Bar[]; rows: number; dense: number };
export type TimelineData = { lanes: Lane[]; from_ms: number; to_ms: number; open: boolean };

/** What Run needs to know of a step from Build: what it does, and whether it runs per sample. */
export type StepFacts = { does?: string | null; perSample: boolean; gathers: boolean };

export const TERMINAL = new Set(["succeeded", "failed", "cancelled", "lost"]);

/** This analysis's runs, newest first, each with its number: Run 1 is the first sent. */
export function numbered(runs: RunRow[], digest: string | null | undefined): { run: RunRow; n: number }[] {
  if (!digest) return [];
  const mine = runs.filter((r) => r.pipeline_digest === digest)
    .sort((a, b) => a.submitted_at.localeCompare(b.submitted_at));
  return mine.map((run, i) => ({ run, n: i + 1 })).reverse();
}

/** The words a run's state is said in: *Running*, *Done*, *Went wrong*. */
export function phaseWords(phase: string): string {
  return ({ queued: "Queued", running: "Running", succeeded: "Done", failed: "Went wrong",
            cancelled: "Stopped", lost: "Lost" } as Record<string, string>)[phase] ?? phase;
}

/** How the samples stand: finished every per-sample step, started one, or not started. A sample
 *  is finished once the slowest per-sample step has done it; the counts never exceed `total`. */
export function samplesOf(rows: ProcessRow[], perSample: Set<string>, total: number) {
  const mine = rows.filter((r) => perSample.has(r.process));
  if (!total || perSample.size === 0) return { finished: 0, inProgress: 0, waiting: total, total };
  const doneOf = (p: string) => mine.find((r) => r.process === p)?.done ?? 0;
  const finished = Math.min(total, ...[...perSample].map(doneOf));
  const started = Math.min(total, Math.max(0, ...mine.map((r) => r.done + r.running + r.failed)));
  const inProgress = Math.max(0, started - finished);
  return { finished, inProgress, waiting: Math.max(0, total - finished - inProgress), total };
}

/** One step's progress, as its node and the tasks panel say it. */
export function progressOf(node: RunNode | undefined, facts: StepFacts | undefined, samples: number,
                           live: boolean): StepProgress {
  const of = facts?.perSample ? Math.max(samples, node?.total ?? 0) : 1;
  const done = Math.min(of, node?.done ?? 0);
  const running = node?.running ?? 0;
  if (node?.failed) return { state: "failed", done, running, of, label: `${node.failed} failed` };
  if (done >= of && (node?.total ?? 0) > 0) {
    return { state: "done", done, running: 0, of, label: of > 1 ? `${of} of ${of}` : "done" };
  }
  if (done || running) {
    return { state: "running", done, running, of,
             label: `${done} of ${of}${running ? ` · ${running} running` : ""}` };
  }
  const label = !live ? "did not run" : facts?.gathers && samples > 1 ? `after all ${samples}` : "waiting";
  return { state: "waiting", done: 0, running: 0, of, label };
}

/** *When each step ran*: from its first task starting to its last finishing, and its slowest task. */
export function ganttOf(timeline: TimelineData, now: number) {
  const to = timeline.open ? Math.max(timeline.to_ms, now) : timeline.to_ms;
  return {
    from: timeline.from_ms,
    to,
    rows: timeline.lanes.filter((l) => l.bars.length > 0).map((lane) => {
      const ends = lane.bars.map((b) => b.end_ms ?? to);
      return {
        process: lane.process,
        start: Math.min(...lane.bars.map((b) => b.start_ms)),
        end: Math.max(...ends),
        live: lane.bars.some((b) => b.end_ms === null),
        slowest: Math.max(...lane.bars.map((b, i) => ends[i] - b.start_ms)),
      };
    }).sort((a, b) => a.start - b.start),
  };
}

const GB = 2 ** 30;

/** Steps that asked for far more memory than they used: at least 4 GB asked, eight times the peak.
 *  The two that left most unused, so a run of small test data does not list every step. */
export function overAsked(rows: ProcessRow[]): { process: string; asked: number; used: number }[] {
  return rows.filter((r) => r.done > 0 && r.memory_asked_bytes && r.memory_peak_bytes
                            && r.memory_asked_bytes >= 4 * GB
                            && r.memory_asked_bytes >= 8 * r.memory_peak_bytes)
    .map((r) => ({ process: r.process, asked: r.memory_asked_bytes!, used: r.memory_peak_bytes! }))
    .sort((a, b) => (b.asked - b.used) - (a.asked - a.used))
    .slice(0, 2);
}

/** Why a task ran again, from its attempts: *ran out of memory at 8 GB, finished with 16 GB*. */
export function retryWhy(task: Task, size: (bytes: number | null | undefined) => string): string {
  const first = task.history[0];
  const last = task.history[task.history.length - 1];
  const killed = first && (first.exit === 137 || first.signal === "SIGKILL" || first.signal === "9");
  const done = task.status === "COMPLETED" || task.status === "CACHED";
  const before = killed ? `ran out of memory at ${size(first.memory_bytes)}` : `attempt 1 stopped (exit ${first?.exit ?? "?"})`;
  return done ? `${before}, finished with ${size(last?.memory_bytes)}` : `${before}; attempt ${task.attempts} running`;
}

/** A task's state in the board's words. */
export function taskWords(status: string | undefined): "done" | "running" | "waiting" | "failed" {
  if (status === "COMPLETED" || status === "CACHED") return "done";
  if (status === "FAILED" || status === "ABORTED") return "failed";
  if (status === "RUNNING") return "running";
  return "waiting";
}

/** A run's state as a colour: done, went wrong, stopped, or going. */
export function dotOf(phase: string): string {
  if (phase === "succeeded") return "var(--done)";
  if (phase === "failed" || phase === "lost") return "var(--needs-you)";
  if (phase === "cancelled") return "var(--line-2)";
  return "var(--now)";
}
