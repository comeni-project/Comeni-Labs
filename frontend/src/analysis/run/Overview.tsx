import { useQuery } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { Link, useNavigate } from "react-router";

import { get } from "../../api/client";
import type { components } from "../../api/schema";
import { Panel } from "../../ui/Panel";
import { get as fromWiener } from "../../wiener/api/client";
import { overAsked, progressOf, retryWhy, samplesOf, type ProcessRow, type RunNode, type Task } from "./model";
import { Measured } from "./Measured";
import { RunCanvas } from "./RunCanvas";
import { bytes } from "./units";
import { factsOf, useAnalysisRuns, useBuildCanvas, useRun, useSamples, type RunState } from "./useRuns";

type Machine = components["schemas"]["Machine"];

/** Run's Overview (`Run.dc.html`): how far it has got first, then the live pipeline, what is worth a
 *  look, the results so far and this machine. */
export function Overview({ draftId, runId, base, state, live, stop }: {
  draftId: string; runId: string; base: string; state: RunState; live: boolean; stop: ReactNode;
}) {
  const navigate = useNavigate();
  const run = useRun(runId);
  const runs = useAnalysisRuns(draftId);
  const canvas = useBuildCanvas(draftId);
  const samples = useSamples(draftId);
  const facts = factsOf(canvas.data);
  const nodes = run.graph.data?.nodes ?? [];
  const rows = run.overview.data?.rows ?? [];
  const perSample = new Set(nodes.filter((n) => facts[n.id]?.perSample).map((n) => n.process));
  const counted = samplesOf(rows, perSample, samples.length);
  const current = runs.list.some(({ run: r }) => r.id === runId);
  const retried = useQuery({
    queryKey: ["retried-tasks", runId],
    queryFn: () => fromWiener<{ tasks: Task[]; total: number }>(`/api/runs/${runId}/tasks?retried_only=true&limit=20`),
    refetchInterval: live ? 5_000 : false,
  });
  const failed = useQuery({
    queryKey: ["failed-tasks", runId],
    queryFn: () => fromWiener<{ tasks: Task[]; total: number }>(`/api/runs/${runId}/tasks?status=FAILED&limit=20`),
    refetchInterval: live ? 5_000 : false,
  });
  const nodeOf = (process: string) => nodes.find((n) => n.process === process);
  const nameOf = (process: string) => facts[nodeOf(process)?.id ?? ""]?.does ?? process;
  const stepLink = (process: string) => {
    const id = nodeOf(process)?.id;
    return id ? `${base}/steps?step=${encodeURIComponent(id)}` : `${base}/steps`;
  };
  const failures = failed.data?.total ?? state.counts.failed;
  const retries = retried.data?.total ?? 0;
  const togo = counted.inProgress + counted.waiting;
  // **Steps, when nothing runs per sample**: a pipeline over one reference still says how far it is.
  const bySteps = counted.total === 0 || perSample.size === 0;
  const stepsDone = nodes.filter((n) => n.total > 0 && n.done >= n.total).length;

  return (
    <>
      <section aria-label="How far it has got" className="bg-surface border border-line rounded-panel px-5 py-3 flex flex-col gap-[10px]">
        <div className="flex flex-wrap items-start gap-3">
          <div className="flex flex-col gap-1">
            <p data-testid="run-status" className="m-0 text-ink">
              <span className="text-[28px] font-semibold tracking-[-.02em] tabular-nums">{bySteps ? stepsDone : counted.finished}</span>
              <span className="text-[15px] text-ink-2"> of {bySteps ? nodes.length : counted.total} {bySteps ? "steps" : "samples"} finished</span>
            </p>
            <p className="m-0 text-[13px] text-ink-2">
              {bySteps ? `${nodes.length - stepsDone} to go` : `${togo} to go`}
              {" · "}{failures ? <span className="text-needs-you-ink font-semibold">{failures} failed</span> : "no failures"}
              {retries > 0 && ` · ${retries} ${retries === 1 ? "retry" : "retries"}`}
            </p>
          </div>
          <span className="ml-auto flex items-center gap-2">
            <Link to={`${base}/outputs`} className="h-[32px] px-3 inline-flex items-center rounded-control border border-line-2 bg-surface text-[13px] font-semibold text-ink no-underline hover:bg-surface-2">
              Outputs
            </Link>
            {stop}
          </span>
        </div>
        {!bySteps && (
          <>
            <div aria-hidden className="flex h-[8px] rounded-full overflow-hidden bg-line-soft">
              <span style={{ width: `${(100 * counted.finished) / counted.total}%`, background: "var(--done)" }} />
              <span style={{ width: `${(100 * counted.inProgress) / counted.total}%`, background: "var(--now-mid)" }} />
            </div>
            <p className="m-0 flex flex-wrap gap-4 text-[12.5px] text-ink-2">
              <Legend colour="var(--done)">finished {counted.finished}</Legend>
              <Legend colour="var(--now-mid)">in progress {counted.inProgress}</Legend>
              <Legend colour="var(--line-2)">waiting {counted.waiting}</Legend>
            </p>
          </>
        )}
      </section>

      <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_380px] xl:grid-cols-[minmax(0,1fr)_440px] items-stretch flex-1">
        <Panel className="flex flex-col" title="Pipeline" actions={
          <Link to={`${base}/steps`} className="h-[28px] px-3 inline-flex items-center rounded-control border border-line-2 bg-surface text-[12.5px] font-semibold text-ink no-underline hover:bg-surface-2">Open</Link>
        }>
          <div className="relative flex-1 min-h-[440px] flex flex-col border-t border-line-soft" data-testid="run-pipeline">
            <RunCanvas draftId={draftId} runId={runId} nodes={nodes} samples={samples.length} live={live} current={current}
                       selected={null} onSelect={(step) => step && navigate(`${base}/steps?step=${encodeURIComponent(step)}`)} />
          </div>
        </Panel>
        <div className="flex flex-col gap-3 min-w-0">
          <WorthALook
            items={[
              ...(failed.data?.tasks ?? []).map((t) => ({
                key: `f${t.task_id}`, mark: "FAILED", tone: "needs-you" as const,
                what: <><b>{nameOf(t.process)}</b>{t.tag ? ` · ${t.tag}` : ""} stopped{t.latest_exit != null ? ` (exit ${t.latest_exit})` : ""}.</>,
                to: stepLink(t.process),
              })),
              ...(retried.data?.tasks ?? []).map((t) => ({
                key: `r${t.task_id}`, mark: "RETRIED", tone: "measured" as const,
                what: <><b>{nameOf(t.process)}</b>{t.tag ? ` · ${t.tag}` : ""} {retryWhy(t, bytes)}.</>,
                to: stepLink(t.process),
              })),
              ...overAsked(rows).map((m) => ({
                key: `m${m.process}`, mark: "MEMORY", tone: "plain" as const,
                what: <><b>{nameOf(m.process)}</b> asked {bytes(m.asked)}, used {bytes(m.used)}.</>,
                to: stepLink(m.process),
              })),
            ]}
          />
          <ResultsSoFar runId={runId} base={base} nodes={nodes} facts={facts} samples={samples.length} live={live} />
          <MachineCard rows={rows} live={live} />
        </div>
      </div>
      {/* What the run measured beside what it was built on (issue 465): a disagreement flags the
          decisions that rested on the estimate. */}
      <Measured runId={runId} live={live} />
    </>
  );
}

function Legend({ colour, children }: { colour: string; children: ReactNode }) {
  return (
    <span className="flex items-center gap-[6px]">
      <span aria-hidden className="w-[8px] h-[8px] rounded-full" style={{ background: colour }} />
      {children}
    </span>
  );
}

type Look = { key: string; mark: string; tone: "needs-you" | "measured" | "plain"; what: ReactNode; to: string };

const TONE = {
  "needs-you": { color: "var(--needs-you-ink)", background: "var(--needs-you-soft)" },
  measured: { color: "var(--measured-ink)", background: "var(--measured-soft)" },
  plain: { color: "var(--ink-2)", background: "var(--surface-2)" },
};

/** *Worth a look*: what stopped, what ran again and why, and what asked for far more than it used. */
function WorthALook({ items }: { items: Look[] }) {
  return (
    <Panel title="Worth a look" actions={<span className="text-[12.5px] text-ink-3 tabular-nums">{items.length}</span>}>
      {items.length === 0 ? (
        <p className="m-0 px-5 pb-4 text-[13px] text-ink-3">Nothing so far.</p>
      ) : (
        <ul aria-label="Worth a look" className="list-none m-0 p-0">
          {items.map((item) => (
            <li key={item.key} className="flex items-center gap-3 px-5 py-[10px] border-t border-line-soft">
              <span className="shrink-0 px-[6px] py-[2px] rounded-control text-[10.5px] font-semibold tracking-[.04em]" style={TONE[item.tone]}>
                {item.mark}
              </span>
              <span className="flex-1 min-w-0 text-[13px] text-ink">{item.what}</span>
              <Link to={item.to} className="shrink-0 h-[28px] px-3 inline-flex items-center rounded-control border border-line-2 bg-surface text-[12.5px] font-semibold text-ink no-underline hover:bg-surface-2">See</Link>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}

/** *Results so far*: each step nothing else reads, with how much of it is there. */
function ResultsSoFar({ runId, base, nodes, facts, samples, live }: {
  runId: string; base: string; nodes: RunNode[];
  facts: ReturnType<typeof factsOf>; samples: number; live: boolean;
}) {
  const wires = useQuery({
    queryKey: ["run-graph", runId],
    queryFn: () => fromWiener<{ wires: { from_node: string; to_node: string }[] }>(`/api/runs/${runId}/graph`),
    select: (g) => g.wires,
  });
  const read = new Set((wires.data ?? []).map((w) => w.from_node));
  const ends = nodes.filter((n) => !read.has(n.id) && !/^measure_/.test(n.id));
  return (
    <Panel title="Results so far" actions={
      <Link to={`${base}/outputs`} className="h-[28px] px-3 inline-flex items-center rounded-control border border-line-2 bg-surface text-[12.5px] font-semibold text-ink no-underline hover:bg-surface-2">Outputs</Link>
    }>
      <ul aria-label="Results so far" className="list-none m-0 p-0">
        {ends.map((n) => {
          const p = progressOf(n, facts[n.id], samples, live);
          return (
            <li key={n.id} className="flex items-center gap-3 px-5 py-[9px] border-t border-line-soft text-[13px]">
              <span className="flex-1 text-ink">{facts[n.id]?.does ?? n.process}</span>
              <span className="font-data text-[12px] text-ink-2">{p.label}</span>
            </li>
          );
        })}
      </ul>
    </Panel>
  );
}

/** *This machine · now*: what a run here has to work with. */
/** *This machine* (#511): what **this run** is using now — its running tasks and what they asked
 *  for — beside what the whole machine has free. The machine's numbers count every program on it,
 *  and say so; when nothing of the run is running, the card says that rather than showing a load
 *  that is someone else's. */
function MachineCard({ rows, live }: { rows: ProcessRow[]; live: boolean }) {
  const machine = useQuery({
    queryKey: ["machine"],
    queryFn: () => get<Machine>("/data/machine"),
    refetchInterval: 10_000,
    retry: false,
  });
  const m = machine.data;
  const running = rows.reduce((n, r) => n + r.running, 0);
  const cores = rows.reduce((n, r) => n + r.running * (r.cpus_asked ?? 0), 0);
  const asked = rows.reduce((n, r) => n + r.running * (r.memory_asked_bytes ?? 0), 0) / 2 ** 30;
  const status = !live ? "The run is over: it uses nothing now."
    : running === 0 ? "Between tasks: nothing of this run is running this moment."
    : `${running} ${running === 1 ? "task" : "tasks"} running, asking ${cores} ${cores === 1 ? "core" : "cores"} and ${asked.toFixed(asked < 10 ? 1 : 0)} GB.`;
  return (
    <Panel title="This machine" actions={<span className="text-[12.5px] text-ink-3">now</span>}>
      <div className="flex flex-col gap-[10px] px-5 pb-4">
        <p data-testid="machine-run" className="m-0 text-[12.5px] text-ink">{status}</p>
        {m && (
          <>
            <Meter label="Cores" total={m.cpus} run={live ? cores : 0} busy={Math.min(m.cpus, m.load)}
                   value={`${Math.max(0, Math.round(m.cpus - m.load))} of ${m.cpus} free`} />
            <Meter label="Memory" total={m.memory_gb} run={live ? asked : 0} busy={m.memory_gb - m.memory_free_gb}
                   value={`${Math.round(m.memory_free_gb)} of ${Math.round(m.memory_gb)} GB free`} />
            <p className="m-0 flex flex-wrap gap-x-4 gap-y-1 text-[11.5px] text-ink-3">
              <span className="flex items-center gap-[6px]"><span aria-hidden className="w-2 h-2 rounded-full bg-now-mid" />this run asked</span>
              <span className="flex items-center gap-[6px]"><span aria-hidden className="w-2 h-2 rounded-full bg-line-2" />in use by everything on the machine</span>
            </p>
          </>
        )}
      </div>
    </Panel>
  );
}

function Meter({ label, total, run, busy, value }: { label: string; total: number; run: number; busy: number; value: string }) {
  const share = (n: number) => Math.round(Math.min(1, Math.max(0, n / (total || 1))) * 100);
  return (
    <div className="grid grid-cols-[64px_minmax(0,1fr)_auto] items-center gap-3 text-[12.5px] text-ink-2">
      {label}
      <div role="meter" aria-label={`${label} in use`} aria-valuenow={share(busy)} aria-valuemin={0} aria-valuemax={100}
           className="relative h-[6px] rounded-full bg-line-soft overflow-hidden">
        <div className="absolute inset-y-0 left-0 bg-line-2" style={{ width: `${share(busy)}%` }} />
        <div className="absolute inset-y-0 left-0 bg-now-mid" style={{ width: `${share(Math.min(run, total))}%` }} />
      </div>
      <span className="font-data text-ink">{value}</span>
    </div>
  );
}
