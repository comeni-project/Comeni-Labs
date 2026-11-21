import { useQueries, useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router";

import { get } from "../api/client";
import type { components } from "../api/schema";
import { useTitle } from "../app/useTitle";
import { toneOf } from "../registry/families";
import { Failed, Loading } from "../ui/States";
import { forgeName, ForgeSlot, useForgings } from "./ForgeSlot";
import { progressOfSummary, releasedOf, stagesOf, statusOf, type StageState } from "./stages";
import { useStartForge } from "./useForgeActions";

type CataloguePage = components["schemas"]["CataloguePage"];
type ModuleRow = components["schemas"]["ModuleRow"];
type ModuleDetail = components["schemas"]["ModuleDetail"];
type Summary = components["schemas"]["AdaptationSummary"];
type Unreachable = components["schemas"]["UnreachableWants"];

const SHOWN = 6;
const BAR: Record<StageState, string> = { done: "bg-done", now: "bg-measured", failed: "bg-needs-you", later: "bg-line" };
const DOT: Record<StageState, string> = { done: "bg-now-mid", now: "bg-measured", failed: "bg-needs-you", later: "bg-mark" };
const control = "inline-flex items-center justify-center h-[32px] px-[13px] rounded-control text-[13px] font-medium no-underline whitespace-nowrap cursor-pointer";
const quiet = `${control} border border-line-2 bg-surface text-ink hover:bg-surface-2`;
const loud = `${control} border-0 bg-action text-on-action shadow-raise font-semibold`;

function useDebounced(value: string, ms = 250) {
  const [v, setV] = useState(value);
  useEffect(() => { const t = setTimeout(() => setV(value), ms); return () => clearTimeout(t); }, [value, ms]);
  return v;
}

function Fmt({ id }: { id: string }) {
  const tone = toneOf(id);
  return <span className="pill" style={{ background: tone.soft, color: tone.ink }}>{id}</span>;
}

/** `/forge` · **Forge** (board "5 · Forge"): what tool do you need — searched in nf-core, each
 *  match saying how it fits your registry — then what needs you, and your forgings with how far
 *  each is through Tool · Tests · Publish. */
export function ForgeHome() {
  useTitle("Forge");
  const forgings = useForgings();
  const list = forgings.data?.adaptations ?? [];
  const [find, setFind] = useState("");
  const box = useRef<HTMLInputElement>(null);
  const q = useDebounced(find.trim());

  return (
    <div className="overflow-y-auto h-full">
      <ForgeSlot />
      <div className="page">
        <label className="flex items-center gap-[10px] h-11 px-4 rounded-panel border border-line bg-surface">
          <svg aria-hidden="true" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="text-ink-3">
            <path d="M14 4l6 6-8 8-6-6zM4 20l4-4" />
          </svg>
          <input ref={box} aria-label="What tool do you need?" value={find} onChange={(e) => setFind(e.target.value)}
                 placeholder="What tool do you need? Search nf-core, or describe what it should do"
                 className="flex-1 min-w-0 border-0 outline-0 bg-transparent text-[14px] text-ink" />
          {find && (
            <button type="button" onClick={() => setFind("")} className="border-0 bg-transparent text-[12.5px] text-ink-2 cursor-pointer">Clear</button>
          )}
        </label>
        <CantYet query={q} pick={setFind} />
        {q && <Results q={q} forgings={list} />}
        <NeedsYou forgings={list} />
        <section aria-label="Forgings" className="flex flex-col gap-3">
          <h2 className="m-0 text-[15px] font-semibold">Forgings</h2>
          {forgings.isError && <Failed error={forgings.error} />}
          <div className="grid gap-3 grid-cols-[repeat(auto-fill,minmax(220px,1fr))]">
            {list.map((f) => <Card key={f.id} forging={f} />)}
            <button type="button" onClick={() => box.current?.focus()}
                    className="min-h-[106px] rounded-panel border border-dashed border-line-2 bg-transparent text-[13px] text-ink-2 cursor-pointer hover:text-ink">
              + Forge a tool by hand
            </button>
          </div>
        </section>
      </div>
    </div>
  );
}

/** *Your registry can't yet* (board "5 · Forge", #534): what analyses want that nothing in the
 *  registry makes, each with how many ask, derived by the API from their current wants. A chip
 *  searches the catalogue for it. Nothing to show, no strip. */
export function CantYet({ query, pick }: { query: string; pick: (q: string) => void }) {
  const wants = useQuery({
    queryKey: ["forge-unreachable"],
    queryFn: () => get<Unreachable>("/forge/unreachable"),
  });
  const rows = wants.data?.wants ?? [];
  if (rows.length === 0) return null;
  return (
    <div aria-label="Your registry can't yet" className="flex flex-wrap items-center gap-[6px]">
      <span className="mr-1 text-[12px] text-ink-3">Your registry can’t yet</span>
      {rows.map((w) => {
        const on = query === w.name;
        return (
          <button key={w.type_id} type="button" onClick={() => pick(on ? "" : w.name)}
                  className={`inline-flex items-center h-[30px] px-3 rounded-full border text-[12.5px] cursor-pointer ${
                    on ? "bg-now-soft border-now-line text-now-ink font-semibold"
                       : "bg-surface border-line-2 text-ink-2 hover:border-now-line"}`}>
            Make {w.name}
            <span className="ml-[6px] text-[11px] font-semibold text-measured-ink">
              asked in {w.builds} {w.builds === 1 ? "build" : "builds"}
            </span>
          </button>
        );
      })}
    </div>
  );
}

function Results({ q, forgings }: { q: string; forgings: Summary[] }) {
  const page = useQuery({
    queryKey: ["catalogue-search", q],
    queryFn: () => get<CataloguePage>(`/forge/catalogue?q=${encodeURIComponent(q)}&limit=${SHOWN}`),
  });
  const rows = page.data?.rows ?? [];
  const details = useQueries({
    queries: rows.map((r) => ({
      queryKey: ["catalogue-module", r.source, r.path],
      queryFn: () => get<ModuleDetail>(`/forge/catalogue/${r.source}/${r.path}`),
    })),
  });
  return (
    <section aria-label="Matches" className="bg-surface border border-line rounded-panel overflow-hidden">
      <div className="flex items-center gap-2 px-4 py-3">
        <span className="text-[13.5px] font-semibold">{page.data ? `${page.data.total} ${page.data.total === 1 ? "match" : "matches"} in nf-core` : "Searching nf-core"}</span>
        <Link to={`/registry?q=${encodeURIComponent(q)}`} className="ml-auto text-[12.5px] text-now-ink no-underline">See all in Registry →</Link>
      </div>
      {page.isError && <p className="m-0 px-4 pb-3 text-[13px] text-needs-you-ink">The catalogue cannot be searched right now.</p>}
      {rows.map((row, n) => (
        <Match key={row.path} row={row} detail={details[n]?.data} forging={forgings.find((f) => f.path === row.path)} />
      ))}
    </section>
  );
}

function fitOf(row: ModuleRow, detail: ModuleDetail | undefined, forging: Summary | undefined): string | null {
  if (forging) return "already forging";
  if (row.state === "imported") return "in your registry";
  const fits = detail?.fits;
  if (fits?.takes_from[0]) return `takes what ${fits.takes_from[0].path} makes`;
  if (fits?.feeds[0]) return `feeds ${fits.feeds[0].path}`;
  return null;
}

function Match({ row, detail, forging }: { row: ModuleRow; detail?: ModuleDetail; forging?: Summary }) {
  const start = useStartForge();
  const navigate = useNavigate();
  const fit = fitOf(row, detail, forging);
  const held = row.state === "imported" || row.state === "update_available";
  return (
    <div className="grid gap-x-4 gap-y-2 items-center px-4 py-3 border-t border-line-soft sm:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)_minmax(0,0.9fr)_auto]">
      <span className="flex flex-col min-w-0">
        <span className="font-data text-[13px] font-semibold text-ink truncate">{row.path}</span>
        {row.description && <span className="text-[12px] text-ink-3 truncate">{row.description}</span>}
      </span>
      <span className="flex flex-wrap items-center gap-1">
        {row.formats_in.slice(0, 2).map((f) => <Fmt key={`i${f}`} id={f} />)}
        {(row.formats_in.length > 0 || row.formats_out.length > 0) && <span className="text-[12px] text-ink-3">→</span>}
        {row.formats_out.slice(0, 2).map((f) => <Fmt key={`o${f}`} id={f} />)}
      </span>
      <span className={`text-[12px] ${forging || held ? "text-ink-3" : "text-measured-ink"}`}>{fit}</span>
      {forging ? (
        <Link to={`/forge/${encodeURIComponent(forging.id)}`} className={quiet}>Open</Link>
      ) : held ? (
        <Link to={`/registry?q=${encodeURIComponent(row.path)}`} className={quiet}>In Registry</Link>
      ) : (
        <button type="button" disabled={start.isPending} className={`${loud} disabled:opacity-60`}
                onClick={() => start.mutate({ source: row.source, path: row.path },
                                             { onSuccess: (v) => navigate(`/forge/${encodeURIComponent(v.id)}`) })}>
          Forge
        </button>
      )}
    </div>
  );
}

interface Call { key: string; tool: string; what: string; detail?: string; tone: string; action: string; to: string; primary?: boolean }

function NeedsYou({ forgings }: { forgings: Summary[] }) {
  const newer = useQuery({
    queryKey: ["catalogue-search", "state:update_available"],
    queryFn: () => get<CataloguePage>("/forge/catalogue?state=update_available&limit=4"),
  });
  const merged = forgings.filter((f) => f.phase === "merged");
  const states = useQueries({
    queries: merged.map((f) => ({
      queryKey: ["catalogue-module", "nf-core", f.path],
      queryFn: () => get<ModuleDetail>(`/forge/catalogue/nf-core/${f.path}`),
      retry: false,
    })),
  });
  const waitingRelease = new Set(merged.filter((_, n) => states[n]?.data?.row?.state === "merged_not_released").map((f) => f.id));
  const calls: Call[] = [];
  for (const f of forgings) {
    const name = forgeName(f.path, f.version);
    const at = `/forge/${encodeURIComponent(f.id)}`;
    if (f.waiting > 0) calls.push({ key: `${f.id}-r`, tool: name, what: `${f.waiting} AI choice${f.waiting === 1 ? "" : "s"} to review`, tone: "bg-measured", action: "Review", to: at });
    if ((f.tests_failed ?? 0) > 0) calls.push({ key: `${f.id}-t`, tool: name, what: `${f.tests_failed === 1 ? "a test" : `${f.tests_failed} tests`} failed`, tone: "bg-needs-you", action: "See test", to: `${at}/tests` });
    if (waitingRelease.has(f.id)) calls.push({ key: `${f.id}-m`, tool: name, what: "merged, waiting for a release", detail: "the builder can use it after the next release", tone: "bg-now-mid", action: "Cut a release", to: "/registry/releases", primary: true });
  }
  const total = newer.data?.total ?? 0;
  if (total > 0) {
    const names = (newer.data?.rows ?? []).map((r) => r.path);
    calls.push({ key: "newer", tool: `${total} tool${total === 1 ? "" : "s"}`, what: "newer in nf-core", tone: "bg-mark", action: "See in Registry", to: "/registry?state=update_available",
                 detail: names.join(", ") + (total > names.length ? ` and ${total - names.length} more` : "") });
  }
  if (forgings.length === 0 && !newer.data) return <Loading what="what needs you" />;
  return (
    <section aria-label="Needs you" className="bg-surface border border-line rounded-panel overflow-hidden">
      <div className="flex items-center gap-2 px-4 py-3">
        <span className="text-[13.5px] font-semibold">Needs you</span>
        <span className="text-[12px] text-ink-3">{calls.length}</span>
      </div>
      {calls.length === 0 && <p className="m-0 px-4 pb-4 text-[13px] text-ink-3">Nothing is waiting for you.</p>}
      {calls.map((c) => (
        <div key={c.key} className="flex items-center gap-3 px-4 py-[10px] border-t border-line-soft">
          <span aria-hidden="true" className={`w-[7px] h-[7px] rounded-full shrink-0 ${c.tone}`} />
          <span className="flex flex-col min-w-0 flex-1">
            <span className="text-[13px] text-ink"><b className="font-data">{c.tool}</b> · {c.what}</span>
            {c.detail && <span className="text-[12px] text-ink-3 truncate">{c.detail}</span>}
          </span>
          <Link to={c.to} className={c.primary ? loud : quiet}>{c.action}</Link>
        </div>
      ))}
    </section>
  );
}

function Card({ forging: f }: { forging: Summary }) {
  const detail = useQuery({
    queryKey: ["catalogue-module", "nf-core", f.path],
    queryFn: () => get<ModuleDetail>(`/forge/catalogue/nf-core/${f.path}`),
    retry: false,
  });
  const does = detail.data?.row?.description;
  const stages = stagesOf({ ...progressOfSummary(f), released: releasedOf(detail.data?.row?.state) });
  const status = statusOf(stages);
  return (
    <Link to={`/forge/${encodeURIComponent(f.id)}`}
          className="flex flex-col gap-2 p-[14px] rounded-panel border border-line bg-surface no-underline hover:border-line-2">
      <span className="flex items-center gap-2">
        <span aria-hidden="true" className={`w-[7px] h-[7px] rounded-full ${DOT[status.state]}`} />
        <span className="font-data text-[13px] font-semibold text-ink">{forgeName(f.path, f.version)}</span>
      </span>
      {does && <span className="text-[12.5px] text-ink-2 line-clamp-2">{does}</span>}
      <span aria-label={stages.map((s) => `${s.label} ${s.state}`).join(", ")} className="grid grid-cols-3 gap-1">
        {stages.map((s) => <span key={s.name} className={`h-[3px] rounded-full ${BAR[s.state]}`} />)}
      </span>
      <span className="flex items-baseline justify-between gap-2 text-[11.5px] text-ink-3">
        <span>Tool · Tests · Publish</span>
        <span className={status.state === "failed" ? "text-needs-you-ink" : ""}>{status.note}</span>
      </span>
    </Link>
  );
}
