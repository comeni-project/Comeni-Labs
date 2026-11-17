import { useState } from "react";
import { Link } from "react-router";

import { Failed } from "../ui/States";
import { describe, live, valueOf, type ItemView } from "./items";
import type { AdaptationView } from "./useAdaptation";
import { useForgeActions } from "./useForgeActions";

type Run = AdaptationView["tests"][number];

interface Case {
  item: ItemView;
  name: string;
  title: string;
  inputs: Record<string, string[]>;
  params: Record<string, unknown>;
  expect: { port: string; pattern: string }[];
  unchecked: Record<string, string>;
  run?: Run;
}

const SYM: Record<string, { sym: string; cls: string; label: string }> = {
  passed: { sym: "✓", cls: "bg-done-soft text-done-ink", label: "passed" },
  failed: { sym: "✕", cls: "bg-needs-you-soft text-needs-you-ink", label: "failed" },
  running: { sym: "…", cls: "bg-now-soft text-now-ink", label: "running" },
  none: { sym: "•", cls: "bg-surface-2 text-ink-3", label: "not run yet" },
};
const symOf = (c: Case) => SYM[c.run?.state ?? "none"] ?? SYM.none;

export function casesOf(view: AdaptationView): Case[] {
  return live(view.items).filter((i) => i.key.startsWith("tests:test:")).map((item) => {
    const v = valueOf(item);
    const name = item.key.slice("tests:test:".length);
    return {
      item, name, title: describe(item).title,
      inputs: (v.inputs ?? {}) as Record<string, string[]>,
      params: (v.params ?? {}) as Record<string, unknown>,
      expect: (v.expect ?? []) as { port: string; pattern: string }[],
      unchecked: (v.unchecked ?? {}) as Record<string, string>,
      run: view.tests.find((t) => t.name === name),
    };
  });
}

/** The tool's ports and parameters, for what the tests cover. */
function shape(view: AdaptationView) {
  const items = live(view.items);
  const outputs = items.filter((i) => i.key.startsWith("contract:output:")).map((i) => i.key.slice("contract:output:".length));
  const optional = items.filter((i) => i.key.startsWith("contract:input:") && valueOf(i).required === false)
    .map((i) => i.key.slice("contract:input:".length));
  return { outputs, optional };
}

/** `/forge/:id/tests` · **Tests** (board "6 · Forging", Tests): the cases from nf-core's test data
 *  run through Comeni's contract, the one picked with what it feeds and what it expects, and what
 *  the tests cover — every output and optional input should be exercised by at least one. */
export function TestsPage({ view }: { view: AdaptationView }) {
  const actions = useForgeActions(view.id);
  const cases = casesOf(view);
  const [picked, setPicked] = useState<string | null>(null);
  const cur = cases.find((c) => c.name === picked) ?? cases[0];
  const passed = cases.filter((c) => c.run?.state === "passed").length;
  const failed = cases.filter((c) => c.run?.state === "failed").length;
  const notRun = cases.length - passed - failed - cases.filter((c) => c.run?.state === "running").length;
  const canRun = view.phase === "assembled" || view.phase === "tested";
  const { outputs, optional } = shape(view);
  const covering = (port: string) => cases.filter((c) => c.expect.some((e) => e.port === port));
  const feeding = (port: string) => cases.filter((c) => (c.inputs[port] ?? []).length > 0);

  return (
    <>
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        {passed > 0 && <span className="inline-flex items-center gap-2 text-[13px] font-semibold"><Sym s={SYM.passed} />{passed} passed</span>}
        {failed > 0 && <span className="inline-flex items-center gap-2 text-[13px] font-semibold text-needs-you-ink"><Sym s={SYM.failed} />{failed} failed</span>}
        {notRun > 0 && <span className="inline-flex items-center gap-2 text-[13px] font-semibold"><Sym s={SYM.none} />{notRun} not run yet</span>}
        <span className="text-[12px] text-ink-3">from {view.source}’s test data, run through Comeni’s contract</span>
        <span className="ml-auto flex gap-2">
          <button type="button" disabled={!canRun || !!view.tests_unavailable || actions.runTests.isPending}
                  onClick={() => actions.runTests.mutate()}
                  className="h-[32px] px-[14px] rounded-control border-0 bg-action text-on-action shadow-raise text-[13px] font-semibold cursor-pointer disabled:opacity-50">
            {view.phase === "testing" ? "Running…" : "Run all"}
          </button>
        </span>
      </div>
      {view.tests_unavailable && <p className="m-0 text-[13px] text-needs-you-ink">{view.tests_unavailable}</p>}
      {!canRun && !view.tests_unavailable && !["testing", "publishing", "in_review", "merged"].includes(view.phase) && (
        <p className="m-0 text-[13px] text-ink-3">The tests run once the tool is assembled: every AI choice reviewed, then Assemble on Publish.</p>
      )}
      {actions.runTests.isError && <Failed error={actions.runTests.error} padded={false} />}

      <div className="grid gap-[14px] items-start xl:grid-cols-[minmax(0,240px)_minmax(0,1fr)_minmax(0,260px)]">
        <section aria-label="Test cases" className="bg-surface border border-line rounded-panel overflow-hidden">
          <div className="px-4 py-3 text-[13.5px] font-semibold">Test cases</div>
          {cases.length === 0 && <p className="m-0 px-4 pb-4 text-[13px] text-ink-3">No tests drafted yet.</p>}
          {cases.map((c) => {
            const on = c.name === cur?.name;
            return (
              <button key={c.name} type="button" aria-pressed={on} onClick={() => setPicked(c.name)}
                      className={`w-full flex gap-2 pl-[13px] pr-4 py-[10px] border-0 border-t border-line-soft border-l-[3px] text-left cursor-pointer
                                  ${on ? "bg-now-soft border-l-now" : "bg-transparent border-l-transparent hover:bg-hover"}`}>
                <Sym s={symOf(c)} />
                <span className="flex flex-col min-w-0">
                  <span className="text-[13px] font-semibold text-ink">{c.title}</span>
                  <span className="text-[12px] text-ink-3 truncate">{Object.entries(c.inputs).filter(([, f]) => f.length).map(([p]) => p).join(", ")}</span>
                </span>
              </button>
            );
          })}
        </section>

        {cur ? <Selected c={cur} /> : <div />}

        <section aria-label="What the tests cover" className="bg-surface border border-line rounded-panel overflow-hidden">
          <div className="flex flex-col gap-[2px] px-4 py-3">
            <span className="text-[13.5px] font-semibold">What the tests cover</span>
            <span className="text-[12px] text-ink-3">Every part should be exercised by at least one test.</span>
          </div>
          <Group label="Outputs" rows={outputs.map((o) => ({ name: o, by: covering(o).length }))} unit={(n) => `${n} test${n === 1 ? "" : "s"}`} />
          {optional.length > 0 && (
            <Group label="Optional inputs" rows={optional.map((o) => ({ name: o, by: feeding(o).length }))} unit={(n) => `${n} test${n === 1 ? "" : "s"}`} />
          )}
        </section>
      </div>
    </>
  );
}

function Sym({ s }: { s: { sym: string; cls: string; label: string } }) {
  return <span aria-label={s.label} className={`w-[16px] h-[16px] shrink-0 rounded-full grid place-items-center text-[10px] font-bold ${s.cls}`}>{s.sym}</span>;
}

function Group({ label, rows, unit }: { label: string; rows: { name: string; by: number }[]; unit: (n: number) => string }) {
  return (
    <div className="flex flex-col pb-2">
      <span className="px-4 pt-2 pb-1 text-[11.5px] font-semibold text-ink-3">{label}</span>
      {rows.map((r) => (
        <span key={r.name} className="flex items-center gap-2 px-4 py-[6px] border-t border-line-soft text-[13px]">
          <Sym s={r.by ? SYM.passed : SYM.none} />
          <span className="font-data text-ink">{r.name}</span>
          <span className={`ml-auto text-[12px] ${r.by ? "text-ink-3" : "text-measured-ink"}`}>{r.by ? unit(r.by) : "not covered"}</span>
        </span>
      ))}
    </div>
  );
}

function Selected({ c }: { c: Case }) {
  const s = symOf(c);
  const inputs = Object.entries(c.inputs).filter(([, files]) => files.length > 0);
  const params = Object.entries(c.params);
  return (
    <section aria-label="Selected test" className="bg-surface border border-line rounded-panel overflow-hidden min-w-0">
      <div className="flex flex-wrap items-center gap-2 px-4 py-3">
        <Sym s={s} />
        <h2 className="m-0 text-[15px] font-semibold">{c.title}</h2>
        <span className="text-[12px] text-ink-3">{s.label}</span>
        {c.run?.run_id && <Link to={`/runs/${c.run.run_id}`} className="ml-auto inline-flex items-center h-[28px] px-3 rounded-control border border-line-2 bg-surface text-[12.5px] text-ink no-underline">Log</Link>}
      </div>
      {c.run?.says && <p className="m-0 px-4 pb-2 text-[12.5px] text-needs-you-ink break-words">{c.run.says}</p>}
      <div className="flex flex-col gap-1 px-4 pb-3">
        <span className="text-[11.5px] font-semibold text-ink-3">Inputs</span>
        {inputs.map(([port, files]) => (
          <span key={port} className="grid grid-cols-[120px_minmax(0,1fr)] gap-2 text-[12.5px]">
            <b className="font-semibold">{port}</b>
            <span className="font-data text-ink-3 truncate">{files.map((f) => `test-datasets/…/${f.split("/").pop()}`).join(", ")}</span>
          </span>
        ))}
        {params.length > 0 && (
          <span className="text-[12.5px]"><b className="font-semibold">Parameters changed:</b> {params.map(([k, v]) => `${k} = ${String(v)}`).join(", ")}</span>
        )}
      </div>
      <table className="w-full border-collapse text-[12.5px]">
        <thead><tr className="bg-surface-2 text-left text-[11.5px] text-ink-3">
          <th className="w-[32px]" /><th className="px-3 py-[6px] font-semibold">Output</th><th className="px-3 py-[6px] font-semibold">Expected</th><th className="px-3 py-[6px] font-semibold">Got</th>
        </tr></thead>
        <tbody>
          {c.expect.map((e) => (
            <tr key={e.port} className="border-t border-line-soft">
              <td className="pl-3"><Sym s={s} /></td>
              <td className="px-3 py-2 font-data">{e.port}</td>
              <td className="px-3 py-2">a file named like <span className="font-data">{e.pattern}</span></td>
              <td className="px-3 py-2 text-ink-3">{c.run?.state === "passed" ? "found" : c.run?.state === "failed" ? "see the log" : "not run"}</td>
            </tr>
          ))}
          {Object.entries(c.unchecked).map(([port, why]) => (
            <tr key={port} className="border-t border-line-soft text-ink-3">
              <td className="pl-3"><Sym s={SYM.none} /></td>
              <td className="px-3 py-2 font-data">{port}</td>
              <td className="px-3 py-2" colSpan={2}>not checked · {why}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="m-0 px-4 py-3 text-[12px] text-ink-3">Passing proves the tool runs as declared and writes each expected output; it does not check the numbers in them.</p>
    </section>
  );
}
