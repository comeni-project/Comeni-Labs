import { Link } from "react-router";

import type { components } from "../api/schema";
import type { components as wiener } from "../wiener/api/schema";

type DraftRow = components["schemas"]["DraftRow"];
type RunRow = wiener["schemas"]["RunRow"];

/** **Home's cards** (#378): what is running, what needs you, what went wrong, what came out.
 *
 * Each card says one thing and **is not drawn when it has nothing to say** — absence is absence.
 * The page with no running run, nothing waiting and nothing failed is simply shorter; no card
 * says *nothing is waiting on you*. Runs are named by their pipeline (joined on the pipeline's
 * digest), because a run id is how the machine addresses it. Nobody's name appears: the MVP has
 * no labs, so there is no *started by* and no owner.
 */

const CARD = "settle rounded-panel border border-line bg-surface px-5 py-4 flex flex-col gap-3 min-w-0";
const TITLE = "m-0 text-heading font-semibold text-ink";
const LINK = "text-now-ink no-underline font-semibold text-[13px] hover:underline focus-visible:shadow-[var(--ring)]";

const nameOf = (run: RunRow, named: Map<string, string>) =>
  (run.pipeline_digest && named.get(run.pipeline_digest)) || run.name || run.id.slice(0, 8);

const newest = (a: RunRow, b: RunRow) => (b.ended_at ?? b.submitted_at).localeCompare(a.ended_at ?? a.submitted_at);

export function elapsed(since: string): string {
  const seconds = Math.max(0, Math.floor((Date.now() - new Date(since).getTime()) / 1000));
  const minutes = Math.floor(seconds / 60);
  const hours = Math.floor(minutes / 60);
  if (hours) return `${hours}h ${(minutes % 60).toString().padStart(2, "0")}m`;
  return `${minutes}m ${(seconds % 60).toString().padStart(2, "0")}s`;
}

function ago(iso: string): string {
  const hours = Math.max(0, (Date.now() - new Date(iso).getTime()) / 3_600_000);
  if (hours < 1) return "just now";
  if (hours < 36) return `${Math.round(hours)} h ago`;
  return `${Math.round(hours / 24)} d ago`;
}

export function RunningCard({ runs, named }: { runs: RunRow[]; named: Map<string, string> }) {
  const running = runs.filter((run) => run.phase === "running");
  if (running.length === 0) return null;
  return (
    <section aria-label="Running now" className={CARD}>
      <h2 className={`${TITLE} flex items-center gap-2`}>
        Running now
        <span aria-hidden className="w-[8px] h-[8px] rounded-full" style={{ background: "var(--now)" }} />
      </h2>
      {running.map((run) => (
        <Link key={run.id} to={`/runs/${run.id}`} className="no-underline text-ink flex flex-col gap-2 rounded-button
                                                             focus-visible:shadow-[var(--ring)]">
          <span className="flex items-baseline gap-2 flex-wrap">
            <span className="font-data text-[14px] font-semibold">{nameOf(run, named)}</span>
            <span className="font-data text-[11.5px] text-ink-3">{run.id.slice(0, 8)}</span>
          </span>
          {/* The done share, a marker for what is in flight, and what has not started. */}
          <span aria-hidden className="flex gap-[3px] h-[7px]">
            <i className="bg-done rounded-full"
               style={{ flex: run.tasks_seen ? `0 0 ${(run.tasks_done / run.tasks_seen) * 100}%` : "0 0 0%" }} />
            <i className="flow bg-now rounded-full w-[36px] shrink-0" />
            <i className="bg-surface-2 rounded-full grow" />
          </span>
          <span className="text-[13px] text-ink-2 tnum">
            {run.tasks_done} of {run.tasks_seen} tasks · {elapsed(run.submitted_at)}
          </span>
        </Link>
      ))}
    </section>
  );
}

export function NeedsYouCard({ drafts }: { drafts: DraftRow[] }) {
  const waiting = drafts.filter((d) => (d.open_values ?? []).length + d.open_not_named > 0);
  if (waiting.length === 0) return null;
  const total = waiting.reduce((n, d) => n + (d.open_values ?? []).length + d.open_not_named, 0);
  return (
    <section aria-label="Needs you" className={CARD}>
      <h2 className={`${TITLE} flex items-center gap-2`}>
        Needs you
        <span className="ml-auto px-[8px] py-[1px] rounded-control text-[12px] font-semibold text-needs-you-ink"
              style={{ background: "var(--needs-you-soft)" }}>
          {total} {total === 1 ? "value" : "values"}
        </span>
      </h2>
      <ul className="m-0 p-0 flex flex-col">
        {waiting.map((d) => {
          const settings = (d.open_values ?? []).map((v) => v.setting);
          return (
            <li key={d.id} className="list-none flex items-baseline gap-3 py-[7px]" style={{ borderTop: "1px solid var(--line)" }}>
              <span aria-hidden className="w-[10px] h-[10px] rounded-full shrink-0 self-center"
                    style={{ border: "2px solid var(--needs-you)" }} />
              <span className="font-data text-[13px] text-ink shrink-0">{d.name || d.id.slice(0, 8)}</span>
              <span className="text-[13px] text-ink-2 truncate min-w-0">
                {settings.length ? settings.join(", ") : `${d.open_not_named} ${d.open_not_named === 1 ? "value" : "values"}`}
                {settings.length > 0 && d.open_not_named > 0 && ` and ${d.open_not_named} more`}
              </span>
              <Link to={`/build?draft=${d.id}`} className={`${LINK} ml-auto shrink-0`}>Answer</Link>
            </li>
          );
        })}
      </ul>
      <p className="m-0 text-[12.5px] text-ink-3">No rule could settle these, so nothing runs until someone answers.</p>
    </section>
  );
}

export function WentWrongCard({ runs, named }: { runs: RunRow[]; named: Map<string, string> }) {
  const failed = runs.filter((run) => run.phase === "failed").sort(newest).slice(0, 3);
  if (failed.length === 0) return null;
  return (
    <section aria-label="Went wrong" className={CARD}>
      <h2 className={`${TITLE} flex items-center gap-2`}>
        Went wrong
        <span aria-hidden className="ml-auto w-[9px] h-[9px] rotate-45" style={{ background: "var(--needs-you)" }} />
      </h2>
      {failed.map((run) => (
        <div key={run.id} className="flex items-baseline gap-3 flex-wrap">
          <span className="font-data text-[13px] text-ink">{nameOf(run, named)}</span>
          <span className="font-data text-[11.5px] text-ink-3">{run.id.slice(0, 8)}</span>
          <span className="text-[12.5px] text-ink-3">{run.ended_at ? ago(run.ended_at) : ""}</span>
          <Link to={`/runs/${run.id}`} aria-label={`Open the run ${run.id.slice(0, 8)}`}
                className={`${LINK} ml-auto`}>Open the run</Link>
        </div>
      ))}
    </section>
  );
}

export function ResultsCard({ runs, named }: { runs: RunRow[]; named: Map<string, string> }) {
  const done = runs.filter((run) => run.phase === "succeeded").sort(newest).slice(0, 3);
  if (done.length === 0) return null;
  return (
    <section aria-label="Results ready" className={CARD}>
      <h2 className={TITLE}>Results ready</h2>
      <ul className="m-0 p-0 flex flex-col">
        {done.map((run) => (
          <li key={run.id} className="list-none" style={{ borderTop: "1px solid var(--line)" }}>
            <Link to={`/runs/${run.id}`} className="flex items-baseline gap-3 py-[8px] no-underline text-ink
                                                    rounded-button focus-visible:shadow-[var(--ring)]">
              <span className="font-data text-[13px]">{nameOf(run, named)}</span>
              <span className="ml-auto text-[12.5px] text-ink-3">{run.ended_at ? ago(run.ended_at) : ""}</span>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
