import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router";

import { useUrlState } from "../../app/useUrlState";
import { Panel } from "../../ui/Panel";
import { get as fromWiener } from "../../wiener/api/client";
import { ganttOf, progressOf, taskWords, type RunNode, type Task, type TimelineData } from "./model";
import { RunCanvas } from "./RunCanvas";
import { bytes, seconds } from "./units";
import { factsOf, useBuildCanvas, useRun, useSamples } from "./useRuns";

const VIEWS = [{ id: "graph", label: "Graph" }, { id: "timeline", label: "Timeline" }] as const;

/** Run's Steps (`Run.dc.html`): the steps as a graph or as a timeline, and under either the tasks of
 *  the step picked in it. **The pick is in the address** (`?step=`), so it holds across the views. */
export function Steps({ draftId, runId, live }: { draftId: string; runId: string; live: boolean }) {
  const [view, setView] = useUrlState<"graph" | "timeline">("view", "graph");
  const [step, setStep] = useUrlState("step", "");
  const run = useRun(runId);
  const samples = useSamples(draftId);
  const nodes = run.graph.data?.nodes ?? [];

  return (
    <>
      <div className="flex flex-wrap items-center gap-3">
        <div role="group" aria-label="View" className="flex p-[3px] rounded-control bg-surface-2 border border-line">
          {VIEWS.map((v) => (
            <button key={v.id} type="button" aria-pressed={view === v.id} onClick={() => setView(v.id)}
                    className={`px-3 py-[5px] rounded-control border-0 text-[12.5px] font-semibold cursor-pointer
                                ${view === v.id ? "bg-surface text-ink shadow-e1" : "bg-transparent text-ink-2 hover:text-ink"}`}>
              {v.label}
            </button>
          ))}
        </div>
        <span className="text-[12.5px] text-ink-3">Pick a step in either view to see its tasks below</span>
      </div>
      {view === "timeline" ? (
        <Gantt runId={runId} draftId={draftId} nodes={nodes} live={live} selected={step} onSelect={setStep} />
      ) : (
        <section aria-label="Pipeline" className="relative h-[min(60vh,620px)] min-h-[380px] flex flex-col bg-surface border border-line rounded-panel overflow-hidden">
          <RunCanvas draftId={draftId} runId={runId} nodes={nodes} samples={samples.length} live={live}
                     selected={step || null} onSelect={(id) => setStep(id ?? "")} />
        </section>
      )}
      {step ? <StepTasks draftId={draftId} runId={runId} node={nodes.find((n) => n.id === step)} step={step}
                         samples={samples} live={live} />
        : <p className="m-0 text-[13px] text-ink-3">No step picked yet.</p>}
    </>
  );
}

/** *When each step ran*: one bar a step, from its first sample starting to its last finishing. */
function Gantt({ runId, draftId, nodes, live, selected, onSelect }: {
  runId: string; draftId: string; nodes: RunNode[]; live: boolean; selected: string; onSelect: (step: string) => void;
}) {
  const timeline = useQuery({
    queryKey: ["timeline", runId],
    queryFn: () => fromWiener<TimelineData>(`/api/runs/${runId}/timeline`),
    refetchInterval: live ? 5_000 : false,
  });
  const facts = factsOf(useBuildCanvas(draftId).data);
  if (timeline.error) return <Panel title="When each step ran"><p role="alert" className="m-0 px-5 pb-4 text-[13px] text-needs-you-ink">The timeline could not be read.</p></Panel>;
  if (!timeline.data) return <Panel title="When each step ran"><p className="m-0 px-5 pb-4 text-[13px] text-ink-3">{timeline.isPending ? "Reading…" : "Nothing has run yet."}</p></Panel>;
  const g = ganttOf(timeline.data, Date.now());
  const span = Math.max(1, g.to - g.from);
  const at = (ms: number) => `${(100 * (ms - g.from)) / span}%`;
  const clock = (ms: number) => new Date(ms).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: span < 600_000 ? "2-digit" : undefined });
  const ticks = [0, 1 / 3, 2 / 3].map((f) => g.from + f * span);
  const idOf = (process: string) => nodes.find((n) => n.process === process)?.id ?? "";
  return (
    <Panel title="When each step ran" hint="first sample starting → last sample finishing">
      <div className="px-5 pb-4 overflow-x-auto">
        <div className="min-w-[640px]">
          <div className="grid grid-cols-[180px_minmax(0,1fr)_110px] gap-3 pb-2 text-[11.5px] text-ink-3">
            <span>Step</span>
            <span className="relative h-[14px]">
              {ticks.map((t) => <span key={t} className="absolute font-data" style={{ left: at(t) }}>{clock(t)}</span>)}
              <span className="absolute right-0 font-data">{timeline.data.open ? "now" : clock(g.to)}</span>
            </span>
            <span className="text-right">Slowest sample</span>
          </div>
          <ul aria-label="When each step ran" className="list-none m-0 p-0 flex flex-col">
            {g.rows.map((row) => {
              const id = idOf(row.process);
              const on = id !== "" && id === selected;
              return (
                <li key={row.process}>
                  <button type="button" aria-pressed={on} onClick={() => id && onSelect(id)}
                          data-testid={`gantt-${id || row.process}`}
                          className="w-full grid grid-cols-[180px_minmax(0,1fr)_110px] items-center gap-3 px-2 -mx-2 py-[7px] rounded-control border-0 text-left cursor-pointer bg-transparent hover:bg-surface-2"
                          style={on ? { background: "var(--now-soft)", boxShadow: "inset 3px 0 0 var(--now)" } : undefined}>
                    <span className="text-[13px] font-semibold text-ink truncate">{facts[id]?.does ?? row.process}</span>
                    <span className="relative h-[10px] rounded-xs bg-line-soft">
                      <span className="absolute top-0 bottom-0 rounded-xs"
                            style={{ left: at(row.start), width: `max(3px, ${(100 * (row.end - row.start)) / span}%)`,
                                     background: row.live ? "var(--now-mid)" : "var(--done)" }} />
                    </span>
                    <span className="text-right font-data text-[12px] text-ink-2">{seconds(row.slowest)}</span>
                  </button>
                </li>
              );
            })}
          </ul>
          <p className="m-0 pt-3 flex gap-4 text-[12px] text-ink-2">
            <span className="flex items-center gap-[6px]"><span aria-hidden className="w-[10px] h-[6px] rounded-xs" style={{ background: "var(--done)" }} />finished</span>
            <span className="flex items-center gap-[6px]"><span aria-hidden className="w-[10px] h-[6px] rounded-xs" style={{ background: "var(--now-mid)" }} />not finished</span>
          </p>
        </div>
      </div>
    </Panel>
  );
}

type Filter = "all" | "running" | "waiting" | "failed" | "retried";

/** The picked step's tasks: one row a sample, with how it went, and a search. */
function StepTasks({ draftId, runId, node, step, samples, live }: {
  draftId: string; runId: string; node?: RunNode; step: string; samples: string[]; live: boolean;
}) {
  const navigate = useNavigate();
  const [filter, setFilter] = useState<Filter>("all");
  const [find, setFind] = useState("");
  const canvas = useBuildCanvas(draftId);
  const facts = factsOf(canvas.data)[step];
  const built = canvas.data?.canvas?.steps.find((s) => s.id === step);
  const tasks = useQuery({
    queryKey: ["step-tasks", runId, node?.process],
    queryFn: () => fromWiener<{ tasks: Task[] }>(`/api/runs/${runId}/tasks?process=${encodeURIComponent(node!.process)}&limit=500`),
    enabled: !!node,
    refetchInterval: live ? 4_000 : false,
  });
  const seen = tasks.data?.tasks ?? [];
  const byTag = new Map(seen.map((t) => [t.tag ?? "", t]));
  const rows = facts?.perSample
    ? [...samples.map((sample) => ({ sample, task: byTag.get(sample) })),
       ...seen.filter((t) => !samples.includes(t.tag ?? "")).map((t) => ({ sample: t.tag ?? `task ${t.task_id}`, task: t }))]
    : seen.length ? seen.map((t) => ({ sample: t.tag ?? `task ${t.task_id}`, task: t as Task | undefined }))
    : [{ sample: facts?.gathers ? "all samples" : "reference", task: undefined as Task | undefined }];
  const words = (task?: Task) => (task ? taskWords(task.status) : "waiting");
  const count = (f: Filter) => rows.filter((r) => f === "all" || (f === "retried" ? (r.task?.attempts ?? 1) > 1 : words(r.task) === f)).length;
  const shown = rows.filter((r) => (filter === "all" || (filter === "retried" ? (r.task?.attempts ?? 1) > 1 : words(r.task) === filter))
    && r.sample.toLowerCase().includes(find.trim().toLowerCase()));
  const progress = progressOf(node, facts, samples.length, live);
  const filters: Filter[] = ["all", "running", "waiting", ...(count("failed") ? ["failed" as const] : []), "retried"];

  return (
    <section aria-label="Tasks" className="bg-surface border border-line rounded-panel">
      <header className="flex flex-wrap items-center gap-3 px-5 pt-4 pb-3">
        <h2 className="m-0 text-[15.5px] font-semibold text-ink">{facts?.does ?? node?.process ?? step}</h2>
        {built && <span className="font-data text-[12px] text-ink-3">{node?.process ?? ""} {built.contract_id.split("@")[1]}</span>}
        <span className="text-[12.5px] text-ink-2">· {progress.label}</span>
        <span className="ml-auto flex flex-wrap items-center gap-[6px]">
          {filters.map((f) => (
            <button key={f} type="button" aria-pressed={filter === f} onClick={() => setFilter(f)}
                    className={`h-[28px] px-[10px] rounded-control border text-[12px] font-semibold cursor-pointer
                                ${filter === f ? "border-now-line bg-now-soft text-now-ink" : "border-line-2 bg-surface text-ink-2 hover:text-ink"}`}>
              {f[0].toUpperCase() + f.slice(1)} {count(f)}
            </button>
          ))}
          <input aria-label="Find a sample" placeholder="Find a sample" value={find} onChange={(e) => setFind(e.target.value)}
                 className="h-[28px] w-[150px] px-2 rounded-control border border-line-2 bg-surface text-[12.5px] text-ink" />
        </span>
      </header>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[640px] border-collapse text-[13px]">
          <thead>
            <tr className="text-left text-[11.5px] text-ink-3">
              {["Sample", "Status", "Attempt", "Time", "Peak memory", "Note", ""].map((h) => (
                <th key={h} className="font-semibold px-5 py-2 border-t border-line-soft">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {shown.map(({ sample, task }) => {
              const state = words(task);
              const note = !task ? (live ? (facts?.gathers ? "starts when every sample is done" : "queued") : "did not run")
                : task.attempts > 1 ? `attempt ${task.attempts}` : state === "failed" ? `exit ${task.latest_exit ?? "?"}` : "";
              return (
                <tr key={sample} data-testid={`task-row-${sample}`} className="border-t border-line-soft">
                  <td className="px-5 py-[8px] font-data text-ink">{sample}</td>
                  <td className="px-5 py-[8px]">
                    <span className="flex items-center gap-[6px] text-ink-2">
                      <span aria-hidden className="w-[7px] h-[7px] rounded-full" style={{ background: DOT[state] }} />{state}
                    </span>
                  </td>
                  <td className={`px-5 py-[8px] font-data ${(task?.attempts ?? 1) > 1 ? "text-measured-ink" : "text-ink-2"}`}>{task?.attempts ?? 1}</td>
                  <td className="px-5 py-[8px] font-data text-ink-2">{task?.realtime_ms != null ? seconds(task.realtime_ms) : "—"}</td>
                  <td className="px-5 py-[8px] font-data text-ink-2">{task ? bytes(task.peak_rss_bytes) : "—"}</td>
                  <td className="px-5 py-[8px] text-ink-3">{note}</td>
                  <td className="px-5 py-[8px] text-right">
                    {task && node && (
                      <button type="button" onClick={() => navigate(`../console?process=${encodeURIComponent(node.process)}`, { relative: "path" })}
                              className="h-[26px] px-[10px] rounded-control border border-line-2 bg-surface text-[12px] font-semibold text-ink cursor-pointer hover:bg-surface-2">
                        Log
                      </button>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {shown.length === 0 && <p className="m-0 px-5 py-3 text-[13px] text-ink-3">No sample matches.</p>}
      </div>
    </section>
  );
}

const DOT = { done: "var(--done)", running: "var(--now)", waiting: "var(--line-2)", failed: "var(--needs-you)" };
