import { useQuery, keepPreviousData } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router";

import { useTitle } from "../app/useTitle";
import { Empty, Failed, Loading } from "../ui/States";
import { get as fromMendel } from "../api/client";
import type { components as mendel } from "../api/schema";
import { get } from "../wiener/api/client";
import { isUnauthorized, TokenPrompt } from "../wiener/Token";
import type { components } from "../wiener/api/schema";
import { Menu, copy, useContextMenu, type MenuItem } from "./Menu";
import { elapsed } from "./elapsed";
import { colourOf, isPhase } from "./phases";
import { seconds } from "./units";

type RunRow = components["schemas"]["RunRow"];
type RunsPage = components["schemas"]["RunsPage"];
type Summary = components["schemas"]["BoardSummary"];
type DraftsPage = mendel["schemas"]["DraftsPage"];

const PER_PAGE = 7;

/** The board's columns — the artboard's, shared by the head and every row so the headings sit
 *  over what they name.
 *
 * **An inline style, not a Tailwind class.** `grid-cols-[...]` assembled by concatenation is
 * invisible to Tailwind's scanner, which reads source text and cannot see a string built at
 * runtime — the class is never generated, the grid silently falls back to one column, and the
 * board renders as a vertical stack of every cell. A computed track list belongs in `style`
 * where nothing has to have scanned for it.
 */
const COLUMNS = {
  gridTemplateColumns: "130px minmax(150px,1.4fr) 90px 100px minmax(150px,1fr) 110px",
  gap: "16px",
} as const;

/** *usually 38m* under a row, and **only where that word is earned.**
 *
 * `BoardSummary.by_pipeline` is `{pipeline_digest: median_ms}` over finished runs, and the
 * repository already refuses a group below a floor — *usually 38m* over two runs is one number
 * wearing the clothes of a distribution. So an absent median means **no comparison at all**,
 * never a zero and never a dash pretending to be one.
 *
 * **A delta needs a finished run**, which is the rule the page owns rather than the endpoint.
 * `-43% vs usual` under a live bar reads as *it was faster* — the opposite of what it means,
 * since a run 43% through its usual duration has not been fast at anything yet. A running row
 * gets the bare expectation, `of ~38m`, which is the same number saying something true.
 */
function VsUsual({ run, medianMs }: { run: RunRow; medianMs?: number }) {
  if (medianMs === undefined) return null;

  if (!run.ended_at) {
    return (
      <span data-testid="vs-usual" className="text-label text-ink-3 tabular-nums">
        of ~{seconds(medianMs)}
      </span>
    );
  }

  const took = new Date(run.ended_at).getTime() - new Date(run.submitted_at).getTime();
  const delta = Math.round(((took - medianMs) / medianMs) * 100);
  // Within a tenth of usual is *usual*. A row reading `+3% vs usual` on every run trains a
  // reader to stop looking at the column that is supposed to catch the outlier.
  if (Math.abs(delta) < 10) {
    return (
      <span data-testid="vs-usual" className="text-label text-ink-3">as usual</span>
    );
  }
  return (
    <span data-testid="vs-usual" className="text-label tabular-nums"
          style={{ color: delta > 0 ? "var(--measured)" : "var(--ink-3)" }}>
      {delta > 0 ? "+" : ""}{delta}% vs usual
    </span>
  );
}

function ago(iso: string): string {
  const minutes = Math.max(0, (Date.now() - new Date(iso).getTime()) / 60_000);
  if (minutes < 2) return "now";
  if (minutes < 90) return `${Math.round(minutes)} min ago`;
  if (minutes < 60 * 36) return `${Math.round(minutes / 60)} h ago`;
  return `${Math.round(minutes / 1440)} d ago`;
}

/** The outcome's mark: a dot while going, a diamond for what went wrong, a tick when it worked. */
function Mark({ phase }: { phase: string }) {
  const colour = colourOf[isPhase(phase) ? phase : "queued"];
  if (phase === "succeeded") return <span aria-hidden className="w-[12px] text-center text-ink-2">✓</span>;
  if (phase === "failed" || phase === "lost") {
    return <span aria-hidden className="w-[9px] h-[9px] mx-[1.5px] rotate-45 inline-block" style={{ background: colour }} />;
  }
  if (phase === "cancelled") {
    return <span aria-hidden className="w-[10px] h-[10px] mx-[1px] rounded-full inline-block border-2" style={{ borderColor: colour }} />;
  }
  return <span aria-hidden className="w-[10px] h-[10px] mx-[1px] rounded-full inline-block" style={{ background: colour }} />;
}

function Row({ run, medianMs, pipeline }: { run: RunRow; medianMs?: number; pipeline: string | null }) {
  const menu = useContextMenu();
  const link = `${window.location.origin}/runs/${run.id}`;
  const bad = run.phase === "failed" || run.phase === "lost";
  const items: MenuItem[] = [
    { label: "Open", onPick: () => { window.location.href = `/runs/${run.id}`; } },
    { label: "Open in a new tab", onPick: () => window.open(`/runs/${run.id}`, "_blank") },
    { label: "Copy run id", onPick: () => void copy(run.id), separated: true },
    { label: "Copy a link to this run", onPick: () => void copy(link) },
    { label: "Copy row as TSV",
      onPick: () => void copy([run.id, pipeline ?? "", run.phase, run.submitted_at].join("\t")) },
    { label: "Cancel", w4: true, separated: true },
  ];

  return (
    <>
    <Link
      data-testid={`run-${run.id}`}
      to={`/runs/${run.id}`}
      {...menu.bind}
      className="grid px-5 py-3 items-center no-underline text-ink border-b border-line last:border-b-0
                 hover:bg-[var(--hover)] focus-visible:shadow-[var(--ring)]"
      style={{ ...COLUMNS, transition: "background-color var(--t)" }}
    >
      <span className={`flex items-center gap-[9px] text-[13.5px] ${bad ? "text-needs-you-ink"
        : run.phase === "running" ? "text-now-ink" : "text-ink-2"}`}>
        <Mark phase={run.phase} />
        {run.phase}
      </span>
      <span className="font-data text-[13px] truncate">
        {pipeline ?? <span className="text-ink-3 font-ui">unknown pipeline</span>}
      </span>
      <span className="font-data text-[12px] text-ink-3">{run.id.slice(0, 8)}</span>
      <time className="text-[13px] text-ink-2" dateTime={run.submitted_at}
            title={new Date(run.submitted_at).toLocaleString()}>
        {ago(run.submitted_at)}
      </time>
      <span className={`text-[13px] tabular-nums ${bad ? "text-needs-you-ink" : "text-ink-2"}`}>
        {run.tasks_seen === 0 ? "—"
          : run.phase === "cancelled" ? `cancelled at ${run.tasks_done} of ${run.tasks_seen}`
          : `${run.tasks_done} of ${run.tasks_seen} tasks`}
      </span>
      <span className="flex flex-col items-end font-data text-[13px] text-ink tabular-nums">
        {run.ended_at
          ? elapsed(new Date(run.submitted_at).getTime(), new Date(run.ended_at).getTime(), 0)
          : "—"}
        {/* **A median in the abstract is trivia; the same median beside a run is a judgement.**
            `rn-board`'s argument for the board's best number, and why it lives on the row. */}
        <VsUsual run={run} medianMs={medianMs} />
      </span>
    </Link>
    {menu.at && <Menu items={items} at={menu.at} onClose={menu.close} />}
    </>
  );
}

/** The outcome tabs: a phase each, and *All* for none. */
const TABS = [
  { label: "All", phase: "" },
  { label: "Going now", phase: "running" },
  { label: "Went wrong", phase: "failed" },
  { label: "Succeeded", phase: "succeeded" },
  { label: "Cancelled", phase: "cancelled" },
] as const;

export function Board() {
  useTitle("Runs");
  const [page, setPage] = useState(0);
  const [phase, setPhase] = useState("");
  const query = new URLSearchParams({ after: String(page * PER_PAGE), limit: String(PER_PAGE) });
  if (phase) query.set("phase", phase);

  const runs = useQuery({
    queryKey: ["runs", query.toString()],
    queryFn: () => get<RunsPage>(`/api/runs?${query}`),
    refetchInterval: 5_000,
    placeholderData: keepPreviousData,
  });
  // The usual duration per pipeline, which the rows compare a finished run against.
  const summary = useQuery({
    queryKey: ["runs-summary"],
    queryFn: () => get<Summary>("/api/runs/summary?days=14"),
    refetchInterval: 30_000,
  });
  // **Mendel's drafts, for names only.** The runs come from Wiener; a run is named by the
  // pipeline it ran, joined on the content digest as Home joins them. Mendel not answering
  // leaves every run *unknown pipeline* and the board otherwise whole.
  const drafts = useQuery({
    queryKey: ["drafts"],
    queryFn: () => fromMendel<DraftsPage>("/pipeline/drafts"),
    retry: false,
  });
  const named = new Map((drafts.data?.drafts ?? []).filter((d) => d.digest)
    .map((d) => [d.digest!, d.name || d.id.slice(0, 8)]));

  if (runs.isPending) return <Loading what="runs" />;
  if (isUnauthorized(runs.error)) {
    return (
      <div className="p-6 max-w-4xl mx-auto">
        <TokenPrompt onSaved={() => void runs.refetch()} />
      </div>
    );
  }
  if (runs.isError) return <Failed error={runs.error} />;

  const s = summary.data;
  const pages = Math.max(1, Math.ceil(runs.data.total / PER_PAGE));
  const lo = page * PER_PAGE + 1;

  return (
    <div className="gutter py-7 flex flex-col gap-4 min-w-0">
      <header className="flex items-baseline gap-3 flex-wrap">
        <h1 className="m-0 text-title font-semibold tracking-[-.02em] text-ink">Runs</h1>
        <p data-testid="runs-count" className="m-0 text-body text-ink-2">
          {runs.data.total} {runs.data.total === 1 ? "run" : "runs"}, newest first
        </p>
      </header>

      <div role="tablist" aria-label="outcome" className="flex gap-1 flex-wrap border-b border-line">
        {TABS.map((tab) => {
          const on = phase === tab.phase;
          return (
            <button key={tab.label} type="button" role="tab" aria-selected={on}
                    onClick={() => { setPhase(tab.phase); setPage(0); }}
                    className={`-mb-px px-3 py-2 bg-transparent border-0 border-b-2 cursor-pointer text-[13.5px]
                                focus-visible:shadow-[var(--ring)] ${on
                                  ? "text-ink font-semibold border-[var(--ink)]"
                                  : "text-ink-2 border-transparent hover:text-ink"}`}>
              {tab.label}
              {on && (
                <span className="ml-2 px-[7px] py-[1px] rounded-full text-[11.5px] font-semibold"
                      style={{ background: "var(--ink)", color: "var(--surface)" }}>
                  {runs.data.total}
                </span>
              )}
            </button>
          );
        })}
      </div>

      <section className="rounded-panel border border-line bg-surface overflow-x-auto">
        <div style={{ minWidth: 760 }}>
          <div style={COLUMNS}
               className="grid px-5 py-2 border-b border-line text-[12px] text-ink-3">
            <span>Outcome</span><span>Pipeline</span><span>Run</span>
            <span>When</span><span>Detail</span><span className="text-right">Took</span>
          </div>
          {/* **Two different emptinesses.** Nothing has ever run here, or nothing matches the
              tab — telling somebody to run a gated pipeline when they have forty runs and a
              tab on is telling them to fix the wrong thing. */}
          {runs.data.runs.length === 0 ? (
            phase ? (
              <Empty title="No runs match." next="Choose All to see the rest." />
            ) : (
              <Empty title="No runs yet." next="Wiener runs a pipeline the Builder has gated." />
            )
          ) : (
            runs.data.runs.map((run) => (
              <Row key={run.id} run={run}
                   pipeline={(run.pipeline_digest && named.get(run.pipeline_digest)) || null}
                   medianMs={run.pipeline_digest ? s?.by_pipeline?.[run.pipeline_digest] : undefined} />
            ))
          )}
        </div>
      </section>

      {/* `1-7 of 49` before the arrows: a bare `1 / 7` makes you do arithmetic to know
          whether the run you want is behind you. */}
      {pages > 1 && (
        <div className="flex items-center gap-3 justify-end text-[12.5px] text-ink-3">
          <span>{lo}–{Math.min(lo + PER_PAGE - 1, runs.data.total)} of {runs.data.total}</span>
          <button type="button" aria-label="previous page" className={pageBtn}
                  disabled={page === 0} onClick={() => setPage((n) => n - 1)}>‹</button>
          <span className="font-data tabular-nums">{page + 1} / {pages}</span>
          <button type="button" aria-label="next page" className={pageBtn}
                  disabled={page + 1 >= pages} onClick={() => setPage((n) => n + 1)}>›</button>
        </div>
      )}
    </div>
  );
}

const pageBtn =
  "px-2 py-0.5 rounded-button border border-line bg-surface text-ink-2 cursor-pointer "
  + "hover:text-ink hover:bg-[var(--hover)] disabled:cursor-not-allowed disabled:opacity-40";
