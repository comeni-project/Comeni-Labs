import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router";

import { get } from "../../api/client";
import type { components } from "../../api/schema";
import { useAnalysis } from "../../app/AnalysisFrame";
import { chipName } from "../../build/living/CollectionChannel";
import { useTypeNames } from "../../build/living/useTypeNames";
import { Loading } from "../../ui/States";
import { get as fromWiener } from "../../wiener/api/client";
import type { AnalysisData } from "../data/types";
import type { ProcessRow } from "./model";
import { useAnalysisRuns, useBuildCanvas } from "./useRuns";
import { useSend } from "./useSend";

type Machine = components["schemas"]["Machine"];
type State = "ok" | "warn" | "fail";
type Check = { key: string; state: State; title: string; detail: string; fix?: { to: string; words: string } };

const GB = 2 ** 30;

/** **New run** (#511, board *New run*): what it reads, the pre-flight checks, what it will make,
 *  and where it runs; **Run on this machine** once nothing fails. No form: every input is answered
 *  from Data by type, and the run is sent with exactly that. */
export function Send({ draftId, kept }: { draftId: string; kept: boolean }) {
  const { name } = useAnalysis();
  const navigate = useNavigate();
  const sending = useSend(draftId, { name, keep: !kept });
  const base = `/a/${encodeURIComponent(draftId)}`;
  const typeName = useTypeNames();
  const canvas = useBuildCanvas(draftId);
  const data = useQuery({ queryKey: ["analysis-data", draftId], queryFn: () => get<AnalysisData>(`/data/${encodeURIComponent(draftId)}`) });
  const machine = useQuery({ queryKey: ["machine"], queryFn: () => get<Machine>("/data/machine"), retry: false });
  const runs = useAnalysisRuns(draftId);
  const previous = runs.list[0]?.run;
  const before = useQuery({
    queryKey: ["overview", previous?.id],
    queryFn: () => fromWiener<{ rows: ProcessRow[] }>(`/api/runs/${previous!.id}/overview`),
    enabled: !!previous,
  });

  if (sending.loading || data.isPending || canvas.isPending) return <div className="page"><Loading what="the run" /></div>;

  const frame = canvas.data?.canvas;
  const steps = frame?.steps ?? [];
  const channels = frame?.channels ?? [];
  const samples = data.data?.samples ?? [];
  const kept_ = samples.filter((s) => !s.left_out);
  const out = samples.filter((s) => s.left_out);
  const refs = data.data?.references ?? [];
  const inputTypes = new Set(channels.filter((c) => c.grain === "sample").map((c) => c.type_id));
  const otherSamples = kept_.filter((s) => !inputTypes.has(s.type_id ?? ""));
  const missing = sending.bindings?.missing ?? [];
  const m = machine.data;

  // ── What it reads: one row a pipeline input, answered from Data ──────────────────────────
  const reads = [...channels].sort((a, b) => (a.grain === b.grain ? 0 : a.grain === "sample" ? -1 : 1)).map((c) => {
    const lacking = missing.find((x) => x.channel === c.name);
    const mine = kept_.filter((s) => s.type_id === c.type_id);
    const ref = refs.find((r) => r.type_id === c.type_id);
    return { c, lacking, mine, ref, name: chipName(typeName(c.type_id)) };
  });

  // ── Pre-flight checks ────────────────────────────────────────────────────────────────────
  const open = steps.flatMap((s) => s.settings.filter((x) => x.tier === 4 && x.value == null && !x.optional)
    .map((x) => ({ step: s.does ?? s.process, name: x.name })));
  const unreviewed = canvas.data?.ai_unreviewed ?? [];
  const files = kept_.reduce((n, s) => n + s.files.length, 0) + refs.length;
  const gone = missing.filter((x) => x.why.startsWith("file not found"));
  // One entry a sample: a sample odd in two measurements is one to check.
  const odd = [...new Map((data.data?.checks ?? []).filter((c) => !out.some((s) => s.name === c.sample))
    .map((c) => [c.sample, c])).values()];
  const length = kept_[0]?.facts.find((f) => f.measurement === "read_length")?.value;
  const asked = Math.max(0, ...(before.data?.rows ?? []).map((r) => r.memory_asked_bytes ?? 0));
  const heaviest = (before.data?.rows ?? []).find((r) => r.memory_asked_bytes === asked);
  const checks: Check[] = [
    kept ? { key: "saved", state: "ok", title: "Pipeline saved", detail: "As Build shows it" }
      : sending.error ? { key: "saved", state: "fail", title: "Pipeline could not be saved", detail: sending.error, fix: { to: `${base}/build`, words: "Open Build" } }
      : { key: "saved", state: "warn", title: "Pipeline changed since saved", detail: "It is saved again when you run" },
    ...(missing.filter((x) => !x.why.startsWith("file not found")).length === 0
      ? [{ key: "inputs", state: "ok" as const, title: "Every input has data", detail: sending.bindings?.summary ?? "" }]
      : missing.filter((x) => !x.why.startsWith("file not found")).map((x, i) => ({
          key: `missing-${i}`, state: "fail" as const, title: x.channel ? `${chipName(typeName(x.type_id))} missing` : "Nothing to run yet",
          detail: x.why, fix: x.channel ? { to: `${base}/data/${/reference/.test(x.why) ? "references" : "samples"}`, words: /reference/.test(x.why) ? "Add a reference" : "Open Samples" }
            : { to: `${base}/build`, words: "Open Build" },
        }))),
    gone.length ? { key: "files", state: "fail", title: "Some files are gone", detail: gone.map((g) => g.why.replace("file not found: ", "")).join(", "), fix: { to: `${base}/data/files`, words: "Open Files" } }
      : { key: "files", state: "ok", title: `All ${files} files are there`, detail: "Read just now, where they are" },
    odd.length ? { key: "agree", state: "warn", title: `${odd.length} ${odd.length === 1 ? "sample" : "samples"} to check`, detail: odd.map((c) => c.sample).join(", "), fix: { to: `${base}/data`, words: "Check in Data" } }
      : { key: "agree", state: "ok", title: "Samples agree", detail: length ? `Same read length (${String(length)}) and pairing` : `${kept_.length} read alike` },
    open.length ? { key: "values", state: "fail", title: `${open.length} ${open.length === 1 ? "setting needs" : "settings need"} a value`, detail: open.map((o) => `${o.name}, on ${o.step}`).join("; "), fix: { to: `${base}/build`, words: "Set in Build" } }
      : { key: "values", state: "ok", title: "No setting needs a value", detail: `${steps.reduce((n, s) => n + s.settings.length, 0)} settled` },
    unreviewed.length ? { key: "ai", state: "warn", title: `${unreviewed.length} AI ${unreviewed.length === 1 ? "choice" : "choices"} to review`, detail: "It can run; you can review after", fix: { to: `${base}/build`, words: "Review in Build" } }
      : { key: "ai", state: "ok", title: "AI choices reviewed", detail: "Nothing waiting" },
    ...(m && asked ? [asked / GB > m.memory_free_gb
      ? { key: "memory", state: "warn" as const, title: "Memory", detail: `${heaviest ? `${steps.find((x) => x.process === heaviest.process)?.does ?? heaviest.process} asked` : "Asks"} ${Math.round(asked / GB)} GB last time, ${Math.round(m.memory_free_gb)} GB free`, fix: { to: `${base}/build`, words: "Change in Build" } }
      : { key: "memory", state: "ok" as const, title: "Memory", detail: `Largest step asked ${Math.round(asked / GB)} GB last time, ${Math.round(m.memory_free_gb)} GB free` }] : []),
    ...(m ? [m.disk_free_gb < 10
      ? { key: "disk", state: "warn" as const, title: "Disk space", detail: `Only ${Math.round(m.disk_free_gb)} GB free where runs are written` }
      : { key: "disk", state: "ok" as const, title: "Disk space", detail: `${Math.round(m.disk_free_gb)} GB free where runs are written` }] : []),
  ];
  const failing = checks.filter((c) => c.state === "fail");
  const looking = checks.filter((c) => c.state === "warn");
  const ready = sending.bindings !== null && missing.length === 0 && failing.length === 0;

  // ── What it will make: each step nothing else reads ───────────────────────────────────────
  const read = new Set((frame?.graph.edges ?? []).map((e) => e.from_node));
  const results = steps.filter((s) => !read.has(s.id) && !s.measures).map((s) => {
    const port = s.ports.find((p) => p.side === "out");
    return { id: s.id, name: port ? chipName(typeName(port.type_id)) : s.does ?? s.process,
             from: s.does ?? s.process,
             detail: s.runs === "per_item" ? `${kept_.length} files, one per sample` : "1 file for the whole run" };
  });

  const go = async () => {
    const accepted = await sending.send().catch(() => null);
    if (accepted) navigate(`${base}/run/${encodeURIComponent(accepted.run_id)}`);
  };

  return (
    <div className="overflow-y-auto h-full">
      <div className="page">
        <header className="flex flex-wrap items-end gap-4">
          <div className="flex flex-col gap-[3px] min-w-0">
            <h1 className="m-0 text-[22px] font-semibold tracking-[-.015em] text-ink">New run</h1>
            <span className="text-[13px] text-ink-2">{name || "This analysis"} · {steps.length} {steps.length === 1 ? "step" : "steps"}</span>
          </div>
          <span className="ml-auto flex items-center gap-3">
            <span data-testid="run-ready" className={`flex items-center gap-[6px] text-[12.5px] ${ready ? "text-done-ink" : "text-needs-you-ink"}`}>
              <span aria-hidden className={`w-[7px] h-[7px] rounded-full ${ready ? "bg-done" : "bg-needs-you"}`} />
              {ready ? (looking.length ? `Ready · ${looking.length} to look at` : "Ready") : `${failing.length + (missing.length && !failing.length ? 1 : 0) || 1} to fix first`}
            </span>
            <button type="button" onClick={go} disabled={!ready || sending.sending}
                    className="h-[42px] px-[22px] rounded-button border-0 bg-action text-on-action shadow-raise text-[14.5px] font-semibold cursor-pointer
                               disabled:bg-line-soft disabled:text-ink-3 disabled:shadow-none disabled:cursor-not-allowed">
              {sending.sending ? "Starting…" : "Run on this machine"}
            </button>
          </span>
        </header>
        {sending.error && kept && <p role="alert" className="m-0 text-[13px] text-needs-you-ink">{sending.error}</p>}

        <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_380px] items-start">
          <div className="flex flex-col gap-3 min-w-0">
            <section aria-label="What it reads" className="bg-surface border border-line rounded-panel">
              <h2 className="m-0 px-5 pt-[14px] pb-[10px] text-[15.5px] font-semibold text-ink">What it reads</h2>
              {(otherSamples.length > 0 || out.length > 0) && <p className="m-0 px-5 pb-3 text-[12.5px] text-ink-2">
                {otherSamples.length} other samples in Data are not used by this pipeline · {out.length} samples left out.
              </p>}
              {missing.length > 0 && missing.some((x) => !x.channel) && (
                <p className="m-0 px-5 pb-3 text-[13px] text-needs-you-ink">{missing.find((x) => !x.channel)?.why}</p>
              )}
              <ul aria-label="Inputs" className="list-none m-0 p-0">
                {reads.map(({ c, lacking, mine, ref, name: what }) => (
                  <li key={c.name} data-testid={`reads-${c.name}`}
                      className={`grid grid-cols-[22px_160px_minmax(0,1fr)_auto] gap-x-[14px] gap-y-[6px] items-start px-5 py-3 border-t border-line-soft ${lacking ? "bg-needs-you-soft" : ""}`}>
                    <Mark state={lacking ? "fail" : "ok"} small />
                    <span className="flex flex-col gap-[2px]">
                      <span className="text-[13.5px] font-semibold text-ink">{what}</span>
                      <span className="text-[12px] text-ink-3">{c.grain === "sample" ? "one per sample" : "for the whole run"}</span>
                    </span>
                    {lacking ? (
                      <span className="text-[13px] font-semibold text-needs-you-ink">{lacking.why}</span>
                    ) : c.grain === "sample" ? (
                      <span className="flex flex-col gap-2 min-w-0">
                        <span className="text-[13.5px] text-ink"><b>{mine.length} {mine.length === 1 ? "sample" : "samples"}</b>, {mine.reduce((n, s) => n + s.files.length, 0)} files</span>
                        <span className="flex flex-wrap gap-[6px]">
                          {mine.map((s) => (
                            <span key={s.name} className="px-2 py-[2px] rounded-control bg-surface-2 border border-line font-data text-[11.5px] text-ink">{s.name}</span>
                          ))}
                        </span>
                        {out.length > 0 && (
                          <span className="text-[12px] text-ink-3">Left out: <span className="font-data">{out.map((s) => s.name).join(", ")}</span></span>
                        )}
                      </span>
                    ) : (
                      <span className="font-data text-[12.5px] text-ink">{ref?.name ?? "—"}</span>
                    )}
                    <Link to={`${base}/data/${c.grain === "sample" ? "samples" : "references"}`}
                          className="text-[12.5px] font-semibold text-now-ink no-underline hover:underline whitespace-nowrap">
                      {lacking && c.grain !== "sample" ? "Add a reference" : c.grain === "sample" ? "Samples" : "References"}
                    </Link>
                  </li>
                ))}
              </ul>
            </section>

            <section aria-label="Pre-flight checks" className="bg-surface border border-line rounded-panel">
              <header className="flex items-center gap-3 px-5 pt-[14px] pb-3">
                <h2 className="m-0 text-[15.5px] font-semibold text-ink">Pre-flight checks</h2>
                <span className="ml-auto text-[12.5px] text-ink-2">
                  <b>{checks.filter((c) => c.state === "ok").length} of {checks.length}</b> passed
                  {failing.length ? ` · ${failing.length} to fix` : looking.length ? ` · ${looking.length} to look at` : ""}
                </span>
              </header>
              <ul aria-label="Pre-flight checks" className="list-none m-0 grid gap-2 px-4 pb-4 sm:grid-cols-2">
                {checks.map((c) => (
                  <li key={c.key} data-testid={`check-${c.key}`} data-state={c.state}
                      className={`grid grid-cols-[28px_minmax(0,1fr)_auto] gap-[10px] items-center px-3 py-[10px] rounded-control border bg-surface
                                  ${c.state === "fail" ? "border-needs-you-line" : c.state === "warn" ? "border-measured-line" : "border-line"}`}>
                    <Mark state={c.state} />
                    <span className="flex flex-col gap-[2px] min-w-0">
                      <span className="text-[13px] font-semibold text-ink">{c.title}</span>
                      <span className="text-[12px] text-ink-3 truncate" title={c.detail}>{c.detail}</span>
                    </span>
                    {c.fix ? <Link to={c.fix.to} className="text-[12.5px] font-semibold text-now-ink no-underline hover:underline whitespace-nowrap">{c.fix.words}</Link> : <span />}
                  </li>
                ))}
              </ul>
            </section>

            {results.length > 0 && (
              <section aria-label="What you will get" className="bg-surface border border-line rounded-panel">
                <h2 className="m-0 px-5 pt-[14px] pb-[10px] text-[15.5px] font-semibold text-ink">What you will get</h2>
                <ul aria-label="Results" className="list-none m-0 p-0">
                  {results.map((r) => (
                    <li key={r.id} data-testid={`result-${r.id}`}
                        className="grid grid-cols-[22px_160px_minmax(0,1fr)] gap-x-[14px] items-center px-5 py-3 border-t border-line-soft">
                      <File done />
                      <span className="text-[13.5px] font-semibold text-ink">{r.name}</span>
                      <span className="flex flex-wrap items-baseline gap-x-2 text-[13px] text-ink-2">
                        <span>{r.detail}</span>
                        <span className="text-ink-3">from {r.from}</span>
                      </span>
                    </li>
                  ))}
                  <li className="grid grid-cols-[22px_160px_minmax(0,1fr)] gap-x-[14px] items-center px-5 py-3 border-t border-line-soft">
                    <File />
                    <span className="text-[13.5px] font-semibold text-ink-2">Logs and reports</span>
                    <span className="text-[13px] text-ink-3">from every step, beside its results</span>
                  </li>
                </ul>
              </section>
            )}
          </div>

          <div className="flex flex-col gap-3 min-w-0">
            {!ready && failing.length > 0 && (
              <section aria-label="To fix first" className="bg-surface border border-needs-you-line rounded-panel px-[18px] py-[14px] flex flex-col gap-[10px]">
                <h2 className="m-0 text-[15.5px] font-semibold text-ink">{failing.length} {failing.length === 1 ? "thing" : "things"} to fix first</h2>
                <ol className="m-0 pl-[18px] flex flex-col gap-2 text-[13px] text-ink-2">
                  {failing.map((c) => (
                    <li key={c.key}>{c.title}{c.fix && <> · <Link to={c.fix.to} className="font-semibold text-now-ink no-underline hover:underline">{c.fix.words}</Link></>}</li>
                  ))}
                </ol>
                <span className="text-[12px] text-ink-3">Run comes on by itself once these are done.</span>
              </section>
            )}
            <section aria-label="Where it runs" className="bg-surface border border-line rounded-panel px-[18px] py-[14px] flex flex-col gap-[10px]">
              <h2 className="m-0 text-[15.5px] font-semibold text-ink">Where it runs</h2>
              <label className="flex gap-[10px] px-3 py-[10px] rounded-control border border-now-line bg-now-soft cursor-pointer">
                <input type="radio" name="where" defaultChecked className="mt-[2px] accent-[var(--now)]" />
                <span className="flex flex-col gap-[3px]">
                  <span className="text-[13.5px] font-semibold text-ink">This machine</span>
                  <span className="text-[12px] text-ink-2">
                    {m ? `${m.cpus} cores · ${Math.round(m.memory_gb)} GB memory · ${Math.round(m.memory_free_gb)} GB free now` : "Reading the machine…"}
                  </span>
                </span>
              </label>
              <label className="flex gap-[10px] px-3 py-[10px] rounded-control border border-line opacity-60 cursor-not-allowed">
                <input type="radio" name="where" disabled className="mt-[2px]" />
                <span className="flex flex-col gap-[3px]">
                  <span className="text-[13.5px] font-semibold text-ink">A cluster</span>
                  <span className="text-[12px] text-ink-2">Set one up in Settings</span>
                </span>
              </label>
            </section>
            {previous && (
              <section aria-label="Last time" className="bg-surface border border-line rounded-panel px-[18px] py-[14px] flex flex-col gap-[6px]">
                <h2 className="m-0 text-[15.5px] font-semibold text-ink">Last time</h2>
                <span className="text-[13px] text-ink-2">
                  <Link to={`${base}/run/${encodeURIComponent(previous.id)}`} className="font-semibold text-now-ink no-underline hover:underline">Run {runs.list[0].n}</Link>
                  {" "}{previous.phase === "succeeded" ? "finished" : previous.phase === "failed" ? "went wrong" : previous.phase}
                  {previous.ended_at ? ` in ${spanOf(previous.submitted_at, previous.ended_at)}` : ""}.
                </span>
                <span className="text-[12px] text-ink-3">Finished tasks are reused where nothing changed.</span>
              </section>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

/** A result's mark: a file, green for what the pipeline is for. */
function File({ done = false }: { done?: boolean }) {
  return (
    <svg aria-hidden width="16" height="18" viewBox="0 0 16 18" fill="none" className="shrink-0">
      <path d="M3 1.5h6.5L13 5v11.5H3z" fill={done ? "var(--done-soft)" : "var(--surface-2)"}
            stroke={done ? "var(--done-ink)" : "var(--ink-3)"} strokeWidth="1.3" strokeLinejoin="round" />
      <path d="M9.5 1.5V5H13" stroke={done ? "var(--done-ink)" : "var(--ink-3)"} strokeWidth="1.3" strokeLinejoin="round" />
    </svg>
  );
}

function spanOf(from: string, to: string): string {
  const s = Math.max(0, Math.round((Date.parse(to) - Date.parse(from)) / 1000));
  return s < 60 ? `${s} s` : `${Math.floor(s / 60)} min ${s % 60} s`;
}

/** A check's mark: a tick, an exclamation or a cross, in its meaning's colours. */
function Mark({ state, small = false }: { state: State; small?: boolean }) {
  const look = { ok: ["var(--done-soft)", "var(--done-ink)", "M5 12l5 5 9-10"],
                 warn: ["var(--measured-soft)", "var(--measured-ink)", "M12 7v6M12 17h.01"],
                 fail: ["var(--needs-you-soft)", "var(--needs-you-ink)", "M7 7l10 10M17 7L7 17"] }[state];
  const size = small ? 16 : 28;
  return (
    <span aria-label={state === "ok" ? "passed" : state === "warn" ? "look at this" : "to fix"} role="img"
          className="rounded-full flex items-center justify-center shrink-0" style={{ width: size, height: size, background: look[0], marginTop: small ? 2 : 0 }}>
      <svg aria-hidden width={small ? 10 : 14} height={small ? 10 : 14} viewBox="0 0 24 24" fill="none" stroke={look[1]} strokeWidth={3} strokeLinecap="round">
        <path d={look[2]} />
      </svg>
    </span>
  );
}
