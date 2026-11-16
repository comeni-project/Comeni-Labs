import { useState } from "react";
import { Link } from "react-router";

import { analysisAddress } from "../app/address";
import {
  type Draft, type RunRow, type Stage, STAGE_WORDS, buildStage, dataLine, dataStage, latestRuns, runStage, when,
} from "./progress";
import { useStart } from "./useStart";

const STAGE_COLOUR: Record<Stage, string> = {
  done: "bg-done", now: "bg-now-mid", look: "bg-measured", failed: "bg-needs-you", none: "bg-line",
};

/** Every analysis as a card: its name, its data in a line, a Data / Build / Run strip, and when it
 *  last changed. A search narrows them by name; *+ New analysis* is the last card. */
export function Analyses({ drafts, runs }: { drafts: Draft[]; runs: RunRow[] }) {
  const [query, setQuery] = useState("");
  const latest = latestRuns(runs);
  const start = useStart("data");
  const shown = drafts.filter((d) => (d.name || "Untitled").toLowerCase().includes(query.trim().toLowerCase()));
  return (
    <section aria-label="Analyses" className="flex flex-col gap-3 min-w-0">
      <header className="flex items-center gap-3 flex-wrap">
        <h2 className="m-0 text-[15.5px] font-semibold text-ink">Analyses</h2>
        <span className="text-[12.5px] text-ink-3">{drafts.length}</span>
        <input type="search" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search"
               aria-label="Search analyses"
               className="ml-auto w-[200px] max-w-full px-3 py-[6px] rounded-control border border-line bg-surface
                          text-[13px] text-ink outline-none focus:shadow-[var(--ring)]" />
      </header>
      <ul className="list-none m-0 p-0 grid gap-3 [grid-template-columns:repeat(auto-fill,minmax(280px,1fr))]">
        {shown.map((d) => {
          const run = d.digest ? latest.get(d.digest) : undefined;
          const stages: [string, Stage][] = [["Data", dataStage(d)], ["Build", buildStage(d)], ["Run", runStage(run)]];
          return (
            <li key={d.id} className="min-w-0">
              <Link to={analysisAddress(d.id)}
                    className="flex flex-col gap-3 h-full p-4 rounded-panel border border-line bg-surface no-underline
                               hover:border-line-2 focus-visible:shadow-[var(--ring)] outline-none">
                <div className="min-w-0">
                  <div className="text-[14.5px] font-semibold text-ink truncate">{d.name || "Untitled"}</div>
                  <div className="text-[12.5px] text-ink-2 truncate">{dataLine(d)}</div>
                </div>
                <ul aria-label="Data, Build, Run" className="list-none m-0 p-0 grid grid-cols-3 gap-[6px]">
                  {stages.map(([label, stage]) => (
                    <li key={label} aria-label={`${label}: ${STAGE_WORDS[stage]}`} className="flex flex-col gap-1">
                      <span className={`h-[4px] rounded-full ${STAGE_COLOUR[stage]}`} />
                      <span className="text-[11px] text-ink-3">{label}</span>
                    </li>
                  ))}
                </ul>
                <div className="mt-auto flex items-center gap-2 text-[12px] text-ink-3">
                  <span>{d.steps ? `${d.steps} ${d.steps === 1 ? "step" : "steps"}` : "Not built"}</span>
                  <span className="ml-auto">{when(d.updated_at)}</span>
                </div>
              </Link>
            </li>
          );
        })}
        <li className="min-w-0">
          <button type="button" onClick={() => start.mutate()} disabled={start.isPending}
                  className="w-full h-full min-h-[120px] rounded-panel border border-dashed border-line bg-transparent
                             text-[13.5px] text-ink-2 cursor-pointer hover:bg-hover hover:text-ink">
            + New analysis
          </button>
        </li>
      </ul>
      {query && !shown.length && <p className="m-0 text-[13px] text-ink-3">No analysis is called that.</p>}
      {start.error && <p role="alert" className="m-0 text-[12.5px] text-needs-you-ink">{start.error.message}</p>}
    </section>
  );
}
