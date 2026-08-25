import { useQuery, keepPreviousData } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router";

import { useTitle } from "../app/useTitle";
import { Empty, Failed, Loading } from "../ui/States";
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
  gridTemplateColumns:
    "minmax(170px,1.1fr) minmax(190px,1.3fr) 128px minmax(150px,1fr) 104px minmax(160px,1fr)",
  gap: "18px",
} as const;

/** One stat tile. **The figure IS the tile** — the label above and the note below are both
 *  subordinate to it, which is what lets four of them be read in one sweep. */
function Tile({ label, figure, colour, note, bar }: {
  label: string; figure: string; colour?: string; note: string;
  bar?: { pct: number; colour: string };
}) {
  return (
    <div className="bg-surface border border-line rounded-[var(--r)] shadow-e2
                    px-[15px] pt-[13px] pb-3.5 flex flex-col">
      <span className="text-label uppercase tracking-[.08em] text-ink-3">{label}</span>
      <span className="font-data mt-[7px] leading-[1.15] tracking-[-.02em]"
            style={{ fontSize: "30px", color: colour ?? "var(--ink)" }}>
        {figure}
      </span>
      <span className="text-label text-ink-3 mt-[3px] normal-case tracking-normal">{note}</span>
      {bar && (
        <span className="block h-[7px] mt-[9px] rounded-[3px] overflow-hidden"
              style={{ background: "var(--surface-2)", boxShadow: "var(--well)" }}>
          <span className="block h-full"
                style={{ width: `${bar.pct}%`, background: bar.colour }} />
        </span>
      )}
    </div>
  );
}

/** Runs per day — **stacked, because the two parts sum to something real**: how much this
 * instance ran. Succeeded over failed, both named in the legend so identity is never colour
 * alone, and only the tallest column carries a number — one over every bar is noise the shape
 * already gives you.
 *
 * A day nothing ran draws a 1px rule rather than a zero-height bar, the same distinction the
 * run table makes when it says a dash never means zero.
 */
function Activity({ days }: { days: Summary["days"] }) {
  const top = Math.max(1, ...days.map((d) => d.succeeded + d.failed));
  return (
    <div className="bg-surface border border-line rounded-[var(--r)] shadow-e2
                    px-[15px] pt-[13px] pb-[11px] flex flex-col">
      <div className="flex items-baseline gap-3">
        <span className="text-label uppercase tracking-[.08em] text-ink-3">runs per day</span>
        <span className="ml-auto flex items-center gap-3.5">
          <Swatch colour="var(--pea)" label="succeeded" />
          <Swatch colour="var(--undecided)" label="failed" />
        </span>
      </div>
      <div className="flex-1 min-h-0 flex items-end gap-[3px] mt-2 border-b border-line">
        {days.map((day, i) => {
          const total = day.succeeded + day.failed;
          const bar = (n: number) => Math.max(3, Math.round((n / top) * 92));
          return (
            <div key={day.day}
                 className="flex-1 flex flex-col items-center gap-1 justify-end min-w-0">
              <span className="font-data text-[10px] text-ink-2 h-[13px]">
                {total === top ? total : ""}
              </span>
              <div className="w-full max-w-[24px] flex flex-col justify-end">
                {total === 0 && <i className="block h-[2px] bg-line" />}
                {day.failed > 0 && (
                  <>
                    <i className="block rounded-t-[3px]"
                       style={{ height: bar(day.failed), background: "var(--undecided)" }} />
                    {/* A 2px gap, so the boundary between the two fills is a gap and never a
                        hairline that reads as a third value. */}
                    <i className="block h-[2px]" style={{ background: "var(--surface)" }} />
                  </>
                )}
                {day.succeeded > 0 && (
                  <i className="block"
                     style={{ height: bar(day.succeeded), background: "var(--pea)",
                              borderRadius: day.failed ? "0 0 3px 3px" : "3px" }} />
                )}
              </div>
              {/* **Four ticks, not fourteen.** One under every column is fourteen numbers
                  nobody reads; four is enough to place any bar in the month. */}
              <span className="font-data text-[9.5px] text-ink-3 whitespace-nowrap">
                {i % 4 === 3 ? new Date(day.day).toLocaleDateString(undefined,
                  { day: "numeric", month: "short" }) : " "}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function Swatch({ colour, label }: { colour: string; label: string }) {
  return (
    <span className="flex items-center gap-1.5 text-label uppercase tracking-[.08em] text-ink-3">
      <span aria-hidden className="inline-block w-2 h-2 rounded-[2px]"
            style={{ background: colour }} />
      {label}
    </span>
  );
}

/** One run.
 *
 * **Phase is drawn as a colour AND a word.** The colour is the same vocabulary the builder and
 * the forge use; the word is what makes `failed` and `lost` — which share a hue on purpose —
 * distinguishable, and what makes the row legible to somebody who cannot separate the two.
 *
 * **`tasks` is a bar and a fraction**, the same pair the run overview uses, so a board row and
 * a process row say a number the same way. It is TASKS rather than steps because
 * `steps_declared` lives in the artifact: reading one per row is the expensive thing this
 * board could never afford, and how many tasks a run has seen is one GROUP BY.
 */
function Row({ run }: { run: RunRow }) {
  const phase = isPhase(run.phase) ? run.phase : "queued";
  const menu = useContextMenu();
  const link = `${window.location.origin}/runs/${run.id}`;
  const pct = run.tasks_seen ? Math.round((run.tasks_done / run.tasks_seen) * 100) : 0;
  const colour = colourOf[phase];

  /** §12.3's board-row menu. Every item duplicates the row's own click or is a clipboard
   *  action — nothing is reachable only by right-click. */
  const items: MenuItem[] = [
    { label: "Open", onPick: () => { window.location.href = `/runs/${run.id}`; } },
    { label: "Open in a new tab", onPick: () => window.open(`/runs/${run.id}`, "_blank") },
    { label: "Copy run id", onPick: () => void copy(run.id), separated: true },
    { label: "Copy a link to this run", onPick: () => void copy(link) },
    { label: "Copy row as TSV",
      onPick: () => void copy([run.id, run.phase, run.executor, run.submitted_by,
                               run.submitted_at].join("\t")) },
    { label: "Cancel", w4: true, separated: true },
    { label: "Relaunch", w4: true },
  ];

  return (
    <>
    <Link
      data-testid={`run-${run.id}`}
      to={`/runs/${run.id}`}
      {...menu.bind}
      className="grid pl-6 pr-[18px] py-3 items-center no-underline
                 text-ink border-b border-line last:border-b-0 hover:bg-[var(--hover)]"
      style={{ ...COLUMNS, transition: "background-color var(--t)" }}
    >
      <span className="font-data text-body">{run.id.slice(0, 8)}</span>
      <span className="text-secondary text-ink-2">{run.executor}</span>
      <span className="flex items-center gap-[7px] text-secondary text-ink-2">
        <span aria-hidden className="inline-block w-2 h-2 rounded-full"
              style={{ background: colour }} />
        {run.phase}
      </span>
      <span className="flex flex-col gap-1">
        <span className="block h-[7px] rounded-[3px] overflow-hidden"
              style={{ background: "var(--surface-2)", boxShadow: "var(--well)" }}>
          {run.tasks_seen > 0 && (
            <span className="block h-full" style={{ width: `${pct}%`, background: colour }} />
          )}
        </span>
        <span className="font-data text-secondary text-ink-2 tabular-nums">
          {run.tasks_seen ? `${run.tasks_done} of ${run.tasks_seen}` : "—"}
        </span>
      </span>
      <span className="font-data text-secondary text-ink-2 tabular-nums">
        {run.ended_at
          ? elapsed(new Date(run.submitted_at).getTime(), new Date(run.ended_at).getTime(), 0)
          : "—"}
      </span>
      <span className="flex flex-col">
        <span className="text-secondary text-ink-2">{run.submitted_by}</span>
        <time className="text-label text-ink-3 tabular-nums normal-case tracking-normal"
              dateTime={run.submitted_at}>
          {new Date(run.submitted_at).toLocaleString()}
        </time>
      </span>
    </Link>
    {menu.at && <Menu items={items} at={menu.at} onClose={menu.close} />}
    </>
  );
}

export function Board() {
  useTitle("Runs");
  const [page, setPage] = useState(0);
  const [phase, setPhase] = useState("");
  const [who, setWho] = useState("");

  const query = new URLSearchParams({ after: String(page * PER_PAGE), limit: String(PER_PAGE) });
  if (phase) query.set("phase", phase);
  if (who) query.set("who", who);

  const runs = useQuery({
    queryKey: ["runs", query.toString()],
    queryFn: () => get<RunsPage>(`/api/runs?${query}`),
    // A board of live runs goes stale by itself. Five seconds is a guess like `MAXLEN ~ 10000`
    // is a guess, and it is cheap to be wrong about: the run PAGE tails a socket, so this is
    // only how fast the list of runs catches up, never how fast a run does.
    refetchInterval: 5_000,
    // **The page does not blank between pages.** Turning to page 2 with `undefined` data would
    // unmount the table and drop the reader back to a spinner they have to wait out.
    placeholderData: keepPreviousData,
  });
  const summary = useQuery({
    queryKey: ["runs-summary"],
    queryFn: () => get<Summary>("/api/runs/summary?days=14"),
    refetchInterval: 30_000,
  });

  if (runs.isPending) return <Loading what="runs" />;
  // **A 401 is not a failure to report, it is a thing to fix** — and the board is where
  // somebody first meets it, because it is the first Wiener page anybody opens. `Failed` would
  // print `/api/runs → 401`, which is true and useless.
  if (isUnauthorized(runs.error)) {
    return (
      <div className="p-6 max-w-4xl mx-auto">
        <TokenPrompt onSaved={() => void runs.refetch()} />
      </div>
    );
  }
  if (runs.isError) return <Failed error={runs.error} />;

  const s = summary.data;
  const rate = s && s.succeeded + s.failed > 0
    ? Math.round((s.succeeded / (s.succeeded + s.failed)) * 100)
    : null;
  const pages = Math.max(1, Math.ceil(runs.data.total / PER_PAGE));
  const lo = page * PER_PAGE + 1;
  const people = [...new Set(runs.data.runs.map((r) => r.submitted_by))].sort();

  return (
    <div className="p-6 flex flex-col gap-3.5 h-full">
      {/* The same `--surface-2` shelf every run page opens with, so the board and the run are
          one product rather than two designs. */}
      <header className="-mx-6 -mt-6 px-6 pt-4 pb-3.5 bg-surface-2 border-b border-line
                         shadow-e1 relative z-[2] flex items-baseline gap-3.5">
        <h1 className="font-data text-title text-ink m-0 tracking-[-.01em]">runs</h1>
        <p className="text-body text-ink-2 m-0">every pipeline this instance has executed</p>
        <span className="ml-auto text-label text-ink-3">last 14 days</span>
      </header>

      {/* **Four tiles and a fortnight**, in the order somebody asks: is anything broken, what
          is running, is this getting better or worse, and how long should a run take. */}
      <div className="shrink-0 grid gap-3.5 h-[172px]
                      grid-cols-[repeat(4,minmax(0,1fr))_minmax(0,2.4fr)]">
        {/* **A zero is not an alarm.** These two tiles wear their status colour only when
            they have something to report — a red `0` failures and an amber `0` running are
            both the good news, painted as the bad. */}
        <Tile label="needs you" figure={String(s?.failed ?? 0)}
              colour={s?.failed ? "var(--undecided)" : "var(--ink-3)"}
              note={s?.failed ? "failed, and nobody has looked" : "nothing is waiting on you"} />
        <Tile label="running now" figure={String(s?.running ?? 0)}
              colour={s?.running ? "var(--measured)" : "var(--ink-3)"}
              note={s?.running ? "on this instance" : "the instance is idle"} />
        <Tile label="succeeded · 14 days" figure={rate === null ? "—" : `${rate}%`}
              note={s ? `${s.succeeded} of ${s.succeeded + s.failed} runs` : "—"}
              bar={rate === null ? undefined : { pct: rate, colour: "var(--pea)" }} />
        <Tile label="typical run" figure={s?.median_ms == null ? "—" : seconds(s.median_ms)}
              note={s?.p95_ms == null ? "no run has finished" : `p95 ${seconds(s.p95_ms)}`} />
        {s ? <Activity days={s.days} />
           : <div className="bg-surface border border-line rounded-[var(--r)] shadow-e2" />}
      </div>

      <section className="flex flex-col flex-1 min-h-0 bg-surface border border-line
                          rounded-[var(--r)] shadow-e2 overflow-hidden">
        {/* **Filters, because 49 rows already needs them** — and the board was the one screen
            with more rows than fit and no way to narrow them. */}
        <div className="shrink-0 flex items-center gap-3 px-4 py-2 border-b border-line
                        bg-surface-2">
          <label className="flex items-center gap-1.5 text-label text-ink-3">
            phase
            <select aria-label="phase" className={control} value={phase}
                    onChange={(e) => { setPhase(e.target.value); setPage(0); }}>
              <option value="">all</option>
              {["running", "succeeded", "failed", "queued", "cancelled", "lost"].map((p) => (
                <option key={p} value={p}>{p}</option>
              ))}
            </select>
          </label>
          <label className="flex items-center gap-1.5 text-label text-ink-3">
            who
            <select aria-label="who" className={control} value={who}
                    onChange={(e) => { setWho(e.target.value); setPage(0); }}>
              <option value="">all</option>
              {people.map((name) => <option key={name} value={name}>{name}</option>)}
            </select>
          </label>
          <span data-testid="runs-count" className="ml-auto text-label text-ink-3">
            {runs.data.total} {runs.data.total === 1 ? "run" : "runs"}
          </span>
        </div>

        <div style={COLUMNS}
             className="shrink-0 grid pl-6 pr-[18px] py-2
                        border-b border-line bg-surface-2 shadow-e1
                        font-ui text-label uppercase tracking-[.08em] font-semibold text-ink-3">
          <span>run</span><span>executor</span><span>phase</span>
          <span>tasks</span><span>elapsed</span><span>submitted</span>
        </div>

        <div className="flex-1 min-h-0 overflow-auto">
          {/* **Two different emptinesses.** Nothing has ever run here, or nothing matches
              what you asked for — and telling somebody to "run a gated pipeline" when they
              have forty runs and a filter on is telling them to fix the wrong thing. */}
          {runs.data.runs.length === 0 ? (
            phase || who ? (
              <Empty title="No runs match." next="Widen the filters to see the rest." />
            ) : (
              <Empty title="No runs yet."
                     next="Wiener runs a pipeline the Builder has gated." />
            )
          ) : (
            runs.data.runs.map((run) => <Row key={run.id} run={run} />)
          )}
        </div>

        {/* `1-7 of 49` before the arrows: a bare `1 / 7` makes you do arithmetic to know
            whether the run you want is behind you. */}
        <div className="mt-auto shrink-0 flex items-center gap-4 px-6 py-2.5 border-t
                        border-line bg-surface-2 text-label text-ink-3">
          <span>newest first</span>
          <span className="ml-auto flex items-center gap-3">
            <span>{lo}–{Math.min(lo + PER_PAGE - 1, runs.data.total)} of {runs.data.total}</span>
            <span className="flex items-center gap-[3px]">
              <button type="button" aria-label="previous page" className={pageBtn}
                      disabled={page === 0} onClick={() => setPage((n) => n - 1)}>‹</button>
              <span className="font-data px-1 tabular-nums">{page + 1} / {pages}</span>
              <button type="button" aria-label="next page" className={pageBtn}
                      disabled={page + 1 >= pages} onClick={() => setPage((n) => n + 1)}>›</button>
            </span>
          </span>
        </div>
      </section>
    </div>
  );
}

const control = "text-secondary bg-surface border border-line rounded-[var(--r)] px-2 py-1";
const pageBtn =
  "px-2 py-0.5 rounded-[var(--r)] border border-line bg-surface text-ink-2 cursor-pointer "
  + "hover:text-ink hover:bg-[var(--hover)] disabled:cursor-not-allowed disabled:opacity-40";
