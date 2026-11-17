import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";

import { get, post } from "../api/client";
import type { components } from "../api/schema";
import { get as fromRunner, post as toRunner, upload } from "../wiener/api/client";

type Test = components["schemas"]["ModulePage"]["tests"][number];
type Case = { name: string; fingerprint: string; run_name: string };
type Run = { id: string; name?: string; phase: string; submitted_at: string; ended_at?: string | null };
const HISTORY = ["registry-sanity-runs"];
const ENDED = new Set(["succeeded", "failed", "cancelled", "lost"]);

async function history(): Promise<Run[]> {
  const found: Run[] = [];
  let total = Infinity;
  while (found.length < total) {
    const page = await fromRunner<{ runs: Run[]; total: number }>(`/api/runs?after=${found.length}&limit=200`);
    found.push(...page.runs); total = page.total;
    if (!page.runs.length) break;
  }
  return found;
}

/** Sanity checks use public registered fixtures and durable runs, never analysis data. */
export function RegisteredTests({ toolId, tests }: { toolId: string; tests: Test[] }) {
  const client = useQueryClient();
  const lock = useRef(false);
  const [submitting, setSubmitting] = useState<string | null>(null);
  const cases = useQuery({ queryKey: ["registered-test-cases", toolId],
    queryFn: () => get<Case[]>(`/tool-tests?contract=${encodeURIComponent(toolId)}`), enabled: tests.length > 0 });
  const runs = useQuery({ queryKey: HISTORY, queryFn: history, enabled: tests.length > 0,
    refetchInterval: (query) => query.state.data?.some((run) => !ENDED.has(run.phase)) ? 3000 : false });
  const launch = useMutation({ mutationFn: async (names: string[]) => {
    if (lock.current) return;
    lock.current = true;
    try {
      for (const name of names) {
        const test = cases.data?.find((test) => test.name === name);
        if (!test) throw new Error("The test definition could not be loaded. Refresh and try again.");
        if (client.getQueryData<Run[]>(HISTORY)?.some((run) => run.name === test.run_name && !ENDED.has(run.phase))) continue;
        setSubmitting(name);
        const prepared = await post<{ bundle: string; params: Record<string, unknown>; run_name: string }>("/tool-tests/prepare", {
          contract: toolId, name, fingerprint: test.fingerprint,
        });
        const bytes = Uint8Array.from(atob(prepared.bundle), (character) => character.charCodeAt(0));
        const stored = await upload<{ artifact_id: string }>("/api/artifacts", "bundle",
          new Blob([bytes.buffer], { type: "application/zip" }), "registered-test.zip", { name: prepared.run_name });
        const accepted = await toRunner<{ run_id: string }>("/api/runs", { artifact_id: stored.artifact_id,
          params: prepared.params, executor: "local" });
        client.setQueryData<Run[]>(HISTORY, (known = []) => [{ id: accepted.run_id, name: prepared.run_name,
          phase: "queued", submitted_at: new Date().toISOString() }, ...known]);
      }
    } finally {
      lock.current = false; setSubmitting(null);
      void client.invalidateQueries({ queryKey: HISTORY });
    }
  } });
  const unavailable = cases.isPending || cases.isError || runs.isPending || runs.isError;
  const live = (test: Case) => runs.data?.some((run) => run.name === test.run_name && !ENDED.has(run.phase));
  const button = "px-3 py-2 rounded-control border border-line-2 bg-surface text-[12px] font-semibold text-ink cursor-pointer hover:bg-hover disabled:opacity-50 disabled:cursor-not-allowed";
  if (!tests.length) return <p className="m-0 text-[12.5px] text-ink-2">No registered tests for this version. Re-forge the tool to add them.</p>;
  return <div className="flex flex-col gap-3">
    <div className="flex flex-wrap items-center justify-between gap-3">
      <span className="text-[12px] text-ink-3">Public test data · runs in the background · checks expected outputs</span>
      <button type="button" disabled={unavailable || launch.isPending || cases.data?.every(live)}
        onClick={() => launch.mutate(tests.map((test) => test.name))} className={button}>
        {launch.isPending ? "Starting…" : "Run all tests"}
      </button>
    </div>
    {(cases.isError || runs.isError) && <p role="alert" className="m-0 text-[12px] text-needs-you-ink">
      Test results could not be loaded. <button type="button" className="connection-text-button" onClick={() => { void cases.refetch(); void runs.refetch(); }}>Retry</button>
    </p>}
    {launch.isError && <p role="alert" className="m-0 text-[12px] text-needs-you-ink">{launch.error.message}</p>}
    {tests.map((test) => {
      const definition = cases.data?.find((one) => one.name === test.name);
      const previous = definition ? (runs.data ?? []).filter((run) => run.name === definition.run_name)
        .sort((a, b) => b.submitted_at.localeCompare(a.submitted_at)) : [];
      return <section key={test.name} aria-label={`Test ${test.name}`} className="p-3 rounded-control border border-line bg-surface-2 flex flex-col gap-2">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <span className="font-data text-[13px] font-semibold text-ink">{test.name}</span>
          <button type="button" disabled={unavailable || launch.isPending || !!definition && !!live(definition)}
            onClick={() => launch.mutate([test.name])} className={button}>
            {submitting === test.name ? "Starting…" : previous.length ? "Run again" : "Run test"}
          </button>
        </div>
        <dl className="m-0 grid grid-cols-[auto_minmax(0,1fr)] gap-x-3 gap-y-1 text-[12px]">
          <dt className="text-ink-3">Inputs</dt><dd className="m-0 font-data text-ink-2 break-all">{test.feeds.join(", ") || "None declared"}</dd>
          <dt className="text-ink-3">Expected outputs</dt><dd className="m-0 font-data text-ink-2 break-all">{test.expects.join(", ")}</dd>
        </dl>
        {definition && previous[0] ? <TestResult key={previous[0].id} contract={toolId} test={definition} run={previous[0]} />
          : <span className="text-[12px] text-ink-3">{cases.isPending || runs.isPending ? "Loading results…" : unavailable ? "Results unavailable" : "Not run"}</span>}
        {previous.length > 1 && definition && <details className="text-[12px] text-ink-3">
          <summary className="cursor-pointer">Previous runs ({previous.length - 1})</summary>
          <div className="pt-2 flex flex-col gap-3">{previous.slice(1).map((run) => <TestResult key={run.id} contract={toolId} test={definition} run={run} />)}</div>
        </details>}
      </section>;
    })}
  </div>;
}

function TestResult({ contract, test, run }: { contract: string; test: Case; run: Run }) {
  const [showLog, setShowLog] = useState(false);
  const verified = useQuery({ queryKey: ["registry-sanity-outputs", run.id, test.fingerprint],
    enabled: run.phase === "succeeded", retry: false,
    queryFn: async () => {
      const files: string[] = [];
      let total = Infinity;
      while (files.length < total) {
        const page = await fromRunner<{ files: { process: string; name: string }[]; total: number }>(`/api/runs/${run.id}/results?after=${files.length}&limit=200`);
        files.push(...page.files.map((file) => `${file.process}/${file.name}`)); total = page.total;
        if (!page.files.length) break;
      }
      return await post<{ passed: boolean; problems: string[] }>("/tool-tests/check-outputs", {
        contract, name: test.name, fingerprint: test.fingerprint, files,
      });
    } });
  const log = useQuery({ queryKey: ["registry-sanity-log", run.id], enabled: showLog,
    queryFn: () => fromRunner<{ text: string }>(`/api/runs/${run.id}/terminal/console?lines=150`) });
  const label = run.phase === "succeeded"
    ? verified.isError ? "Could not verify outputs" : verified.isPending ? "Checking outputs…" : verified.data?.passed ? "Passed" : "Failed"
    : ({ queued: "Queued", running: "Running", failed: "Failed", cancelled: "Stopped", lost: "Lost" } as Record<string, string>)[run.phase] ?? run.phase;
  const tone = label === "Passed" ? "bg-done-soft text-done-ink" : label === "Failed" || verified.isError
    ? "bg-needs-you-soft text-needs-you-ink" : "bg-now-soft text-now-ink";
  return <div className="flex flex-col gap-2">
    <div className="flex flex-wrap items-center gap-2">
      <span role="status" className={`px-2 py-1 rounded-control text-[12px] font-semibold ${tone}`}>{label}</span>
      <time dateTime={run.submitted_at} className="text-[11px] text-ink-3">{new Date(run.submitted_at).toLocaleString()}</time>
    </div>
    {verified.data?.problems.map((problem) => <p key={problem} className="m-0 text-[12px] text-needs-you-ink">{problem}</p>)}
    {verified.isError && <p className="m-0 text-[12px] text-needs-you-ink">{verified.error.message}</p>}
    <details onToggle={(event) => setShowLog(event.currentTarget.open)} className="text-[12px] text-ink-3">
      <summary className="cursor-pointer">Run log</summary>
      {showLog && <pre className="max-h-72 overflow-auto whitespace-pre-wrap break-all rounded-control bg-surface p-3 text-[11px] font-data text-ink-2">{log.isPending ? "Loading log…" : log.isError ? "The run log could not be loaded." : log.data?.text || "No output yet."}</pre>}
    </details>
  </div>;
}
