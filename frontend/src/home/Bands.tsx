import { Link } from "react-router";

import { analysisAddress } from "../app/address";
import { Panel } from "../ui/Panel";
import { type Draft, LIVE, type RunRow, elapsed, latestRuns, openChoices } from "./progress";

/** *Running now*: every live run, with how far it has got. Absent when nothing runs. */
export function RunningNow({ runs, drafts }: { runs: RunRow[]; drafts: Draft[] }) {
  const byDigest = new Map(drafts.filter((d) => d.digest).map((d) => [d.digest!, d]));
  // Only the analyses' runs: a Forge test run belongs to the Forge, and names a tool, not a question.
  const live = runs.filter((r) => LIVE.has(r.phase) && r.pipeline_digest && byDigest.has(r.pipeline_digest));
  if (!live.length) return null;
  return (
    <Region title="Running now" count={live.length}>
      <ul className="list-none m-0 p-0 flex flex-col">
        {live.map((run) => {
          const draft = byDigest.get(run.pipeline_digest!)!;
          const share = run.tasks_seen ? run.tasks_done / run.tasks_seen : 0;
          const to = analysisAddress(draft.id, "run", run.id);
          return (
            <li key={run.id} className="px-5 pb-4 pt-1 border-t border-line-soft first:border-t-0">
              <Link to={to} className="no-underline text-ink hover:underline">
                <span className="text-[16px] font-semibold">{draft.name || "Untitled"}</span>
              </Link>
              <span className="ml-3 text-[12.5px] text-ink-3">
                {run.phase === "running" ? elapsed(run.submitted_at) : run.phase === "queued" ? "waiting" : "starting"}
              </span>
              <div role="progressbar" aria-label="tasks finished" aria-valuemin={0} aria-valuemax={run.tasks_seen}
                   aria-valuenow={run.tasks_done}
                   className="mt-2 h-[6px] rounded-full bg-line-soft overflow-hidden">
                <div className="h-full bg-done" style={{ width: `${Math.round(share * 100)}%` }} />
              </div>
              <p className="m-0 mt-2 text-[12.5px] text-ink-2">
                {run.tasks_seen ? `${run.tasks_done} of ${run.tasks_seen} tasks finished` : "No task has started yet"}
              </p>
            </li>
          );
        })}
      </ul>
    </Region>
  );
}

/** *Needs you*: an analysis with something only the person can settle. One row per analysis,
 *  its reasons in words, its button to the first page that settles them. Absent when none. */
export function NeedsYou({ runs, drafts }: { runs: RunRow[]; drafts: Draft[] }) {
  const latest = latestRuns(runs);
  const rows = drafts.flatMap((d) => {
    const reasons: { text: string; to: string; bad?: boolean }[] = [];
    if (d.data?.scan === "failed") reasons.push({ text: "the files could not be read", to: analysisAddress(d.id, "data"), bad: true });
    if (d.data?.checks) reasons.push({ text: `${d.data.checks} to check in Data`, to: analysisAddress(d.id, "data") });
    const open = openChoices(d);
    if (open) reasons.push({ text: `${open} ${open === 1 ? "choice" : "choices"} to review in Build`, to: analysisAddress(d.id, "build") });
    const run = d.digest ? latest.get(d.digest) : undefined;
    if (run && (run.phase === "failed" || run.phase === "lost")) {
      reasons.push({ text: `the last run ${run.phase === "lost" ? "was lost" : "failed"}`,
                     to: analysisAddress(d.id, "run", run.id), bad: true });
    }
    return reasons.length ? [{ d, reasons }] : [];
  });
  if (!rows.length) return null;
  return (
    <Region title="Needs you" count={rows.length}>
      <ul className="list-none m-0 p-0">
        {rows.map(({ d, reasons }) => (
          <li key={d.id} className="flex items-center gap-3 px-5 py-[10px] border-t border-line-soft">
            <div className="min-w-0 grow">
              <div className="text-[13.5px] font-semibold text-ink truncate">{d.name || "Untitled"}</div>
              <div className={`text-[12.5px] ${reasons.some((r) => r.bad) ? "text-needs-you-ink" : "text-ink-2"}`}>
                {reasons.map((r) => r.text).join(" · ")}
              </div>
            </div>
            <Link to={reasons[0].to} aria-label={`Review ${d.name || "Untitled"}`}
                  className="shrink-0 px-3 py-[5px] rounded-button border border-line text-[12.5px] font-medium
                             text-ink no-underline hover:bg-hover">
              Review
            </Link>
          </li>
        ))}
      </ul>
    </Region>
  );
}

function Region({ title, count, children }: { title: string; count: number; children: React.ReactNode }) {
  return (
    // The panel is the region, named by its title.
    <Panel title={title} actions={<span className="text-[12.5px] text-ink-3">{count}</span>}>{children}</Panel>
  );
}
