import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";

import { Panel } from "../../ui/Panel";
import { get as fromWiener } from "../../wiener/api/client";
import type { components as wiener } from "../../wiener/api/schema";
import { Measured } from "./Measured";
import { RunCanvas } from "./RunCanvas";
import { bytes } from "./units";
import { factsOf, useAnalysisRuns, useBuildCanvas, useRun, useSamples } from "./useRuns";

type Results = wiener["schemas"]["ResultsOut"];
type File = wiener["schemas"]["ResultFile"];

const PAGE = 500;

/** What a file is, from its name: how it is filtered and badged. */
export type Kind = "table" | "log" | "bam" | "reads" | "index" | "fact" | "other";
export const KINDS: { kind: Kind; label: string; badge: string; tone: string }[] = [
  { kind: "table", label: "Tables", badge: "TSV", tone: "bg-done-soft text-done-ink" },
  { kind: "log", label: "Logs and reports", badge: "LOG", tone: "bg-surface-2 text-ink-2" },
  { kind: "bam", label: "Alignments", badge: "BAM", tone: "bg-now-soft text-now-ink" },
  { kind: "reads", label: "Reads", badge: "FQ", tone: "bg-measured-soft text-measured-ink" },
  { kind: "index", label: "Indexes", badge: "IDX", tone: "bg-surface-2 text-ink-3" },
  { kind: "fact", label: "Measurements", badge: "FACT", tone: "bg-measured-soft text-measured-ink" },
  { kind: "other", label: "Other", badge: "FILE", tone: "bg-surface-2 text-ink-3" },
];

export function kindOf(name: string): Kind {
  const n = name.toLowerCase();
  if (n.endsWith(".measured.json")) return "fact";
  if (/\.(bai|csi|crai|fai|tbi)$/.test(n) || n.includes("/")) return "index";
  if (/\.(bam|cram|sam)$/.test(n)) return "bam";
  if (/\.(f(ast)?q)(\.gz)?$/.test(n)) return "reads";
  if (/\.(tsv|csv|tab|counts?)$/.test(n) && !n.endsWith(".out.tab")) return "table";
  if (/(\.log|\.out|\.txt|\.summary|\.html|\.json|_report.*)$/.test(n) || n.endsWith(".out.tab")) return "log";
  return "other";
}

/** The sample a file belongs to: the longest kept sample name it starts with. */
export function sampleOf(name: string, samples: string[]): string | null {
  const base = name.split("/").pop() ?? name;
  const hits = samples.filter((s) => base.startsWith(s) && !/[A-Za-z0-9]/.test(base.charAt(s.length)));
  return hits.sort((a, b) => b.length - a.length)[0] ?? null;
}

/** **Run → Outputs** (board "Run · Outputs"): what the pipeline was made for first, then what the
 *  run measured, then every file — by sample or by step, searchable, each group folding — beside
 *  a window on the pipeline itself (Run's canvas, which pans and zooms as on Overview) lighting
 *  where the chosen file came from, and the file shown. */
export function Outputs({ draftId, runId, live }: { draftId: string; runId: string; live: boolean }) {
  const results = useQuery({
    queryKey: ["results", runId],
    queryFn: () => fromWiener<Results>(`/api/runs/${runId}/results?limit=${PAGE}`),
    refetchInterval: live ? 6_000 : false,
  });
  const canvas = useBuildCanvas(draftId);
  const facts = factsOf(canvas.data);
  const samples = useSamples(draftId);
  const run = useRun(runId);
  const current = useAnalysisRuns(draftId).list.some(({ run: r }) => r.id === runId);
  const edges = canvas.data?.canvas?.graph.edges ?? [];
  const stepIds = (canvas.data?.canvas?.steps ?? []).map((s) => s.id);

  const [by, setBy] = useState<"sample" | "step">("sample");
  const [kind, setKind] = useState<Kind | "all">("all");
  const [step, setStep] = useState<string | null>(null);
  const [find, setFind] = useState("");
  const [closed, setClosed] = useState<Set<string>>(new Set());
  const [picked, setPicked] = useState<string | null>(null);

  const files = results.data?.files ?? [];
  const stepOf = (f: File) => stepIds.find((id) => id.toLowerCase() === f.process.toLowerCase()) ?? f.process;
  const keyOf = (f: File) => `${f.process}/${f.name}`;
  const nameOf = (id: string) => facts[id]?.does ?? id;
  const q = find.trim().toLowerCase();
  const shown = files.filter((f) => (kind === "all" || kindOf(f.name) === kind)
    && (!step || stepOf(f) === step)
    && (!q || f.name.toLowerCase().includes(q) || (sampleOf(f.name, samples) ?? "").toLowerCase().includes(q)));
  // What the pipeline was made for: what its last steps published, readable.
  const sinks = stepIds.filter((id) => !edges.some((e) => e.from_node === id));
  const made = files.filter((f) => sinks.includes(stepOf(f)) && f.viewable && kindOf(f.name) !== "log");
  const cur = files.find((f) => keyOf(f) === picked) ?? made[0] ?? files[0];

  const groups = useMemo(() => {
    if (by === "step") {
      const order = [...stepIds, ...new Set(shown.map(stepOf).filter((s) => !stepIds.includes(s)))];
      return order.map((id) => ({ key: id, title: nameOf(id), files: shown.filter((f) => stepOf(f) === id) }))
        .filter((g) => g.files.length);
    }
    return [...samples.map((s) => ({ key: s, title: s, files: shown.filter((f) => sampleOf(f.name, samples) === s) })),
            { key: "_shared", title: "Shared", files: shown.filter((f) => !sampleOf(f.name, samples)) }]
      .filter((g) => g.files.length);
  }, [by, shown, samples, stepIds]); // eslint-disable-line react-hooks/exhaustive-deps

  if (results.data && !results.data.published) {
    return <Panel title="Outputs"><p className="m-0 px-5 pb-4 text-[13px] text-ink-3">Nothing published yet.</p></Panel>;
  }
  // Many samples start folded; a search opens what it finds.
  const isOpen = (key: string) => (q ? true : groups.length > 8 ? !closed.has(key) && closed.has(`open:${key}`) : !closed.has(key));
  const flip = (key: string) => setClosed((was) => {
    const next = new Set(was);
    if (groups.length > 8) { if (next.has(`open:${key}`)) next.delete(`open:${key}`); else next.add(`open:${key}`); }
    else if (next.has(key)) next.delete(key); else next.add(key);
    return next;
  });
  const madeBySteps = [...new Set(made.map(stepOf))];

  return (
    <div className="flex flex-col gap-3 min-w-0">
      {results.error && <p role="alert" className="m-0 text-[13px] text-needs-you-ink">The outputs could not be listed.</p>}
      {madeBySteps.length > 0 && (
        <Panel title="Your results">
          <div className="grid gap-[10px] px-4 pb-4 grid-cols-[repeat(auto-fit,minmax(260px,1fr))]">
            {madeBySteps.map((id) => (
              <div key={id} className="flex flex-col gap-[10px] p-[14px] rounded-panel border border-done-line bg-done-soft">
                <span className="text-[14px] font-semibold text-ink">{nameOf(id)}</span>
                <span className="flex flex-wrap gap-[6px]">
                  {made.filter((f) => stepOf(f) === id).map((f) => (
                    <button key={keyOf(f)} type="button" onClick={() => setPicked(keyOf(f))}
                            className="inline-flex items-center gap-[6px] h-[28px] px-[10px] rounded-control border border-line-2 bg-surface text-[12.5px] text-ink cursor-pointer">
                      {sampleOf(f.name, samples) ?? f.name}<span className="font-data text-[10.5px] text-ink-3">{bytes(f.size_bytes)}</span>
                    </button>
                  ))}
                </span>
              </div>
            ))}
          </div>
        </Panel>
      )}
      <Measured runId={runId} live={live} />

      <div className="flex flex-wrap gap-4 items-start">
        <section aria-label="All files" className="flex-[1_1_520px] min-w-0 bg-surface border border-line rounded-panel overflow-hidden">
          <div className="flex flex-wrap items-center gap-2 px-4 pt-[14px] pb-[10px]">
            <h2 className="m-0 text-[14px] font-semibold">All files</h2>
            <span className="text-[12px] text-ink-3">{results.data?.total ?? 0}</span>
            {step && (
              <button type="button" onClick={() => setStep(null)}
                      className="h-[26px] px-[9px] rounded-control border border-now-line bg-now-soft text-now-ink text-[12px] font-semibold cursor-pointer">
                {nameOf(step)} ×
              </button>
            )}
            <span role="group" aria-label="Group files" className="ml-auto inline-flex rounded-control border border-line-2 overflow-hidden">
              {(["sample", "step"] as const).map((g) => (
                <button key={g} type="button" aria-pressed={by === g} onClick={() => setBy(g)}
                        className={`h-[28px] px-3 border-0 text-[12.5px] cursor-pointer ${by === g ? "bg-action text-on-action shadow-raise font-semibold" : "bg-surface text-ink-2"}`}>
                  {g === "sample" ? "By sample" : "By step"}
                </button>
              ))}
            </span>
          </div>
          <div className="flex flex-wrap items-center gap-[6px] px-4 pb-[10px]">
            <input aria-label="Find a sample or file" placeholder="Find a sample or file" value={find} onChange={(e) => setFind(e.target.value)}
                   className="h-[28px] w-[200px] max-w-full px-[10px] rounded-control border border-line-2 bg-surface text-[12.5px] text-ink" />
            {([["all", "All"], ...KINDS.map((k) => [k.kind, k.label])] as [Kind | "all", string][])
              .filter(([k]) => k === "all" || files.some((f) => kindOf(f.name) === k))
              .map(([k, label]) => (
                <button key={k} type="button" aria-pressed={kind === k} onClick={() => setKind(k)}
                        className={`h-[28px] px-[10px] rounded-control border text-[12.5px] cursor-pointer
                                    ${kind === k ? "bg-now-soft border-now-line text-now-ink font-semibold" : "bg-surface border-line-2 text-ink-2"}`}>
                  {label} <span className="text-ink-3 font-normal">{k === "all" ? files.length : files.filter((f) => kindOf(f.name) === k).length}</span>
                </button>
              ))}
          </div>
          {groups.length === 0 && <p className="m-0 px-4 pb-4 text-[13px] text-ink-3">{files.length ? "Nothing matches." : "Nothing published yet."}</p>}
          {groups.map((g) => (
            <div key={g.key} className="border-t border-line">
              <button type="button" aria-expanded={isOpen(g.key)} onClick={() => flip(g.key)}
                      className="w-full flex items-center gap-2 px-4 py-[9px] border-0 bg-surface-2 text-left cursor-pointer">
                <svg aria-hidden="true" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3"
                     className="text-ink-3" style={{ transform: isOpen(g.key) ? "rotate(90deg)" : undefined }}><path d="M9 6l6 6-6 6" /></svg>
                <span className="text-[13px] font-semibold text-ink">{g.title}</span>
                <span className="text-[12px] text-ink-3">{g.files.length}</span>
              </button>
              {isOpen(g.key) && g.files.map((f) => {
                const on = cur && keyOf(f) === keyOf(cur);
                const k = KINDS.find((x) => x.kind === kindOf(f.name))!;
                return (
                  <button key={keyOf(f)} type="button" aria-pressed={on} onClick={() => setPicked(keyOf(f))}
                          className={`w-full flex items-center gap-[10px] pl-[13px] pr-4 py-2 border-0 border-t border-line-soft border-l-[3px] text-left cursor-pointer
                                      ${on ? "bg-now-soft border-l-now" : "bg-surface border-l-transparent hover:bg-hover"}`}>
                    <span className={`w-[30px] h-[22px] shrink-0 rounded-xs grid place-items-center text-[9.5px] font-bold ${k.tone}`}>{k.badge}</span>
                    <span className="flex flex-col min-w-0">
                      <span className="text-[13px] font-semibold text-ink truncate">{by === "step" ? sampleOf(f.name, samples) ?? f.name : nameOf(stepOf(f))}</span>
                      <span className="font-data text-[11px] text-ink-3 truncate">{f.name}</span>
                    </span>
                    <span className="ml-auto font-data text-[11.5px] text-ink-3">{bytes(f.size_bytes)}</span>
                  </button>
                );
              })}
            </div>
          ))}
          {results.data && results.data.total > files.length && (
            <p className="m-0 px-4 py-3 border-t border-line-soft text-[12.5px] text-ink-3">Showing {files.length} of {results.data.total}.</p>
          )}
        </section>

        {cur && (
          <Preview runId={runId} draftId={draftId} file={cur} step={stepOf(cur)} nameOf={nameOf} sample={sampleOf(cur.name, samples)}
                   edges={edges} files={files} stepOf={stepOf} samples={samples}
                   canvas={<RunCanvas draftId={draftId} runId={runId} nodes={run.graph.data?.nodes ?? []} samples={samples.length}
                                      live={live} current={current} selected={step ?? stepOf(cur)}
                                      onSelect={(id) => setStep(id && id === step ? null : id)}
                                      lit={[...upstream(stepOf(cur), edges), stepOf(cur)]} focus={stepOf(cur)} />}
                   onPick={(f) => setPicked(keyOf(f))} />
        )}
      </div>
    </div>
  );
}

/** Every step a step's inputs came from, however far back. */
export function upstream(step: string, edges: { from_node: string; to_node: string }[]): string[] {
  const seen = new Set<string>();
  const walk = (id: string) => edges.filter((e) => e.to_node === id).forEach((e) => {
    if (!seen.has(e.from_node)) { seen.add(e.from_node); walk(e.from_node); }
  });
  walk(step);
  return [...seen];
}

function Preview({ runId, file, step, nameOf, sample, edges, files, stepOf, samples, canvas, onPick }: {
  runId: string; draftId: string; file: File; step: string; nameOf: (id: string) => string; sample: string | null;
  edges: { from_node: string; to_node: string }[]; files: File[]; stepOf: (f: File) => string; samples: string[];
  canvas: React.ReactNode; onPick: (f: File) => void;
}) {
  // **A link, not a fetched blob** (Checkpoint D): Wiener serves reports sandboxed. The local
  // proxy adds the token; a hosted install would need a signed link.
  const href = `/api/runs/${runId}/results/file?process=${encodeURIComponent(file.process)}&name=${encodeURIComponent(file.name)}`;
  const head = useQuery({
    queryKey: ["result-head", runId, file.process, file.name],
    queryFn: async () => {
      const got = await fetch(href, { headers: { Range: "bytes=0-16383" } });
      if (!got.ok) throw new Error(`${got.status}`);
      return (await got.text()).slice(0, 16384);
    },
    enabled: file.viewable === true && !file.name.endsWith(".html"),
    staleTime: Infinity,
  });
  const from = edges.filter((e) => e.to_node === step).map((e) => e.from_node);
  const to = [...new Set(edges.filter((e) => e.from_node === step).map((e) => e.to_node))];
  const madeFrom = files.filter((f) => from.includes(stepOf(f)) && sampleOf(f.name, samples) === sample
    && !["log", "index"].includes(kindOf(f.name)));
  const lines = (head.data ?? "").split("\n").filter((l) => l.length > 0);
  const table = lines.length > 1 && lines.slice(0, 5).every((l) => l.startsWith("#") || l.includes("\t"));
  const rows = lines.filter((l) => !l.startsWith("#")).slice(0, 8).map((l) => l.split("\t"));
  const kind = kindOf(file.name);

  return (
    <aside aria-label="Preview" className="flex-[1_1_460px] min-w-0 sticky top-4 self-start max-h-[calc(100dvh-32px)] overflow-y-auto bg-surface border border-line rounded-panel">
      <div className="flex items-start gap-3 px-4 pt-[14px] pb-3 border-b border-line-soft">
        <span className="flex flex-col gap-[3px] min-w-0 flex-1">
          <span className="text-[15px] font-semibold text-ink">{sample ? `${sample} · ` : ""}{nameOf(step)}</span>
          <span className="font-data text-[11.5px] text-ink-3 break-all">{file.process}/{file.name}</span>
          <span className="text-[12px] text-ink-3">{bytes(file.size_bytes)}</span>
        </span>
        <span className="flex gap-[6px] shrink-0">
          {file.viewable && (
            <a href={href} target="_blank" rel="noopener noreferrer" aria-label={`Open ${file.name}`}
               className="h-[30px] px-3 inline-flex items-center rounded-control border border-line-2 bg-surface text-[12.5px] font-semibold text-ink no-underline hover:bg-surface-2">
              Open
            </a>
          )}
          <button type="button" onClick={() => void navigator.clipboard?.writeText(`${file.process}/${file.name}`)}
                  className="h-[30px] px-3 rounded-control border border-line-2 bg-surface text-[12.5px] text-ink cursor-pointer">Copy path</button>
        </span>
      </div>
      <div className="flex flex-col gap-[10px] px-4 py-3 border-b border-line-soft">
        <div data-testid="outputs-pipeline" className="relative h-[260px] flex flex-col rounded-panel border border-line-soft overflow-hidden">{canvas}</div>
        <div className="grid grid-cols-[74px_minmax(0,1fr)] gap-x-[10px] gap-y-1 text-[12px]">
          <span className="text-ink-3">Made from</span>
          <span className="flex flex-wrap gap-1">
            {madeFrom.length ? madeFrom.map((f) => (
              <button key={`${f.process}/${f.name}`} type="button" onClick={() => onPick(f)}
                      className="h-[22px] px-[7px] rounded-xs border border-line-2 bg-surface text-[11px] text-ink-2 cursor-pointer">{f.name}</button>
            )) : <span className="text-ink-2">{from.length ? from.map(nameOf).join(", ") : "the data"}</span>}
          </span>
          <span className="text-ink-3">Used by</span>
          <span className="text-ink-2">{to.length ? to.map(nameOf).join(", ") : "—"}</span>
        </div>
      </div>
      {!file.viewable && (
        <p className="m-0 px-4 py-4 text-[13px] text-ink-2">{kind === "bam" ? "BAM · binary" : kind === "reads" ? "FASTQ · gzip · binary" : "Binary"}</p>
      )}
      {file.viewable && file.name.endsWith(".html") && (
        <p className="m-0 px-4 py-4 text-[13px] text-ink-2">A report: Open shows it.</p>
      )}
      {head.isPending && file.viewable && !file.name.endsWith(".html") && <p className="m-0 px-4 py-4 text-[13px] text-ink-3">Reading…</p>}
      {head.data !== undefined && table && (
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-[12px]">
            <tbody>
              {rows.map((r, n) => (
                <tr key={n} className={n === 0 ? "bg-surface-2 text-ink-3" : ""}>
                  {r.map((c, m) => <td key={m} className="px-3 py-[6px] border-b border-line-soft font-data whitespace-nowrap">{c}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {head.data !== undefined && !table && (
        <pre className="m-4 p-3 rounded-control bg-surface-2 font-data text-[11.5px] leading-[18px] text-ink-2 whitespace-pre-wrap max-h-[320px] overflow-y-auto">{lines.slice(0, 40).join("\n")}</pre>
      )}
    </aside>
  );
}
