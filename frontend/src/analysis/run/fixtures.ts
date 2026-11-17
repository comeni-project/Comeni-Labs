/** A routed Run page with its servers answered (#511): one analysis `d1` keeping a two-step pipeline
 *  (Align reads, then Sort alignments, both per sample) over three samples, and its runs. */
import { vi } from "vitest";

export const DIGEST = "sha256:" + "d".repeat(64);
export const OTHER = "sha256:" + "e".repeat(64);

const step = (id: string, process: string, does: string, contract: string) => ({
  id, process, contract_id: contract, does, measures: false, runs: "per_item", tier: 2, reason: "",
  ports: [], checked_per_sample: [], settings: [],
});

export const CANVAS_SESSION = {
  id: "s1", draft_id: "d1", name: "Yeast counts", revision: 3, decision_revision: 1, projection_current: true,
  retired: false, graph: { nodes: [], edges: [] }, placement: {}, steps_total: 2, row_version: 1,
  usage: { input: 0, output: 0, cached: 0, calls: 0, in_flight: false }, turns: [], working: false,
  goal: null, facts: [], inputs: [], fact_subjects: [],
  canvas: {
    context: { draft_revision: 3, decision_revision: 1, session_version: 1, registry: "" }, current: true,
    graph: { nodes: [{ id: "star_align", contract_id: "nf-core/star/align@2.7.11b", params: [] },
                     { id: "samtools_sort", contract_id: "nf-core/samtools/sort@1.24", params: [] }],
             edges: [] },
    steps: [step("star_align", "STAR_ALIGN", "Align reads", "nf-core/star/align@2.7.11b"),
            step("samtools_sort", "SAMTOOLS_SORT", "Sort alignments", "nf-core/samtools/sort@1.24")],
    // The pipeline's one per-sample input: Run counts the samples of this type (2026-11-17).
    channels: [{ name: "reads", param: "input", type_id: "fastq.reads", grain: "sample", ports: [], states: [] }],
    placement: { star_align: { x: 0, y: 0 }, samtools_sort: { x: 240, y: 0 } },
  },
};

const node = (id: string, process: string, done: number, running: number) =>
  ({ id, process, x: 0, y: 0, width: 172, height: 112, tier: 2, inputs: [], outputs: [],
     done, failed: 0, running, total: done + running, attempts: 1 });

const task = (id: number, process: string, tag: string, status: string) => ({
  task_id: id, process, status, attempts: 1, latest_exit: status === "COMPLETED" ? 0 : null,
  last_change_ms: 0, peak_rss_bytes: 1_200_000_000, realtime_ms: 61_000, pct_cpu: 99, tag, history: [],
});

export const RUN = (id: string, digest: string, at: string, phase = "succeeded") => ({
  id, phase, executor: "local", name: "Yeast counts", submitted_by: "operator", submitted_at: at,
  ended_at: phase === "running" ? null : at, tasks_done: 4, tasks_seen: 4, pipeline_digest: digest,
});

type Answers = {
  runs?: unknown[];
  bindings?: unknown;
  posted?: (url: string, body: unknown) => void;
};

/** Stubs `fetch` for the Run pages. `runs` are Wiener's runs; `bindings` what Data answers. */
export function stubRunServers({ runs = [], bindings, posted = () => {} }: Answers = {}) {
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    const ok = (body: unknown) => ({ ok: true, status: 200, json: async () => body, blob: async () => new Blob(["zip"]) });
    if (init?.method === "POST") {
      const body = typeof init.body === "string" ? JSON.parse(init.body)
        : init.body instanceof FormData ? (() => {
          const fields: Record<string, string> = {};
          init.body.forEach((value, key) => { if (typeof value === "string") fields[key] = value; });
          return fields;
        })()
        : null;
      posted(url, body);
      if (url.includes("/session")) return ok({ session_id: "s1" });
      if (url.endsWith("/api/artifacts")) return ok({ artifact_id: "art1", declared: [] });
      if (url.endsWith("/api/runs")) return ok({ run_id: "new-run" });
      return ok({});
    }
    if (url.includes("/health/ai")) return new Promise(() => {});
    const path = url.replace(/^https?:\/\/[^/]+/, "");
    const body =
      path.includes("/bindings") ? bindings
      : path.endsWith("/bundle") ? {}
      : path.endsWith("/pipeline/drafts") ? { drafts: [{ id: "d1", name: "Yeast counts", digest: DIGEST, kept: true,
                                                         changed_since_kept: false, steps: 2, who: "", updated_at: "" }], total: 1 }
      : path.includes("/pipeline/drafts/d1") ? { id: "d1", name: "Yeast counts", graph: { nodes: [], edges: [] }, revision: 3 }
      : path.includes("/pipeline/authoring/") ? CANVAS_SESSION
      : path.endsWith("/data/machine") ? { cpus: 12, load: 4, memory_gb: 64, memory_free_gb: 40, disk_free_gb: 200 }
      : path.includes("/data/d1") ? { folders: ["/data/yeast"], files: 6, references: [], checks: [], revision: 1,
                                      scan: { state: "done" }, rule: {}, fixes: [], kinds: [], columns: {}, unfit: [],
                                      samples: ["WT_REP1", "WT_REP2", "RAP1"].map((name) => ({ name, files: [], facts: [], left_out: false, type_id: "fastq.reads" })) }
      : path.startsWith("/api/runs?") ? { runs, total: runs.length }
      : path.endsWith("/overview") ? { rows: [], steps_declared: 2, steps_finished: 1 }
      : path.endsWith("/graph") ? { nodes: [node("star_align", "STAR_ALIGN", 3, 0), node("samtools_sort", "SAMTOOLS_SORT", 1, 1)], wires: [] }
      : path.endsWith("/timeline") ? { from_ms: 0, to_ms: 100_000, open: false, lanes: [
          { process: "STAR_ALIGN", declared: true, rows: 1, dense: 0, bars: [{ task_id: 1, attempt: 1, status: "COMPLETED", start_ms: 0, end_ms: 60_000, row: 0 }] },
          { process: "SAMTOOLS_SORT", declared: true, rows: 1, dense: 0, bars: [{ task_id: 4, attempt: 1, status: "COMPLETED", start_ms: 60_000, end_ms: 100_000, row: 0 }] },
        ] }
      : path.includes("/tasks?process=STAR_ALIGN") ? { tasks: [task(1, "STAR_ALIGN", "WT_REP1", "COMPLETED"),
                                                               task(2, "STAR_ALIGN", "WT_REP2", "COMPLETED"),
                                                               task(3, "STAR_ALIGN", "RAP1", "COMPLETED")], total: 3 }
      : path.includes("/tasks?process=SAMTOOLS_SORT") ? { tasks: [task(4, "SAMTOOLS_SORT", "WT_REP1", "COMPLETED"),
                                                                  task(5, "SAMTOOLS_SORT", "WT_REP2", "RUNNING")], total: 2 }
      : path.includes("/tasks") ? { tasks: [], total: 0 }
      : path.endsWith("/measured") ? { facts: [], decided: [] }
      : path.includes("/results") ? { files: [], total: 0, published: true }
      : path.includes("/events") ? { events: [], next: null }
      : /\/api\/runs\/[^/]+$/.test(path) ? { run_id: path.split("/").pop(), phase: "succeeded",
          counts: { succeeded: 5, failed: 0, cached: 0, running: 0, submitted: 0 },
          started_at_ms: 0, ended_at_ms: 100_000, executor: "local" }
      : {};
    return ok(body);
  }));
}
