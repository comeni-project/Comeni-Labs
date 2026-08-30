import { Link } from "react-router";

import type { components } from "../api/schema";
import type { components as wiener } from "../wiener/api/schema";

type Call = components["schemas"]["Call"];
type RunRow = wiener["schemas"]["RunRow"];

const EYEBROW = "text-label uppercase tracking-[.14em] text-ink-3 m-0";

/** What is happening right now, and what is stopped until somebody decides.
 *
 * **This whole band does not render when both halves are empty** — and that is the difference
 * between the ACTIVE and QUIET artboards, which is not a different empty state but a shorter
 * page. No card, no *"nothing is waiting on you"*, no *"the instance is idle"*.
 *
 * `ov-absence` is the whole argument: an empty region is faster to read than a paragraph
 * explaining that it is empty, and the instinct to fill it with a reassuring sentence is exactly
 * what made the old page read as generated.
 */
function elapsed(since: string): string {
  const seconds = Math.max(0, Math.floor((Date.now() - new Date(since).getTime()) / 1000));
  const minutes = Math.floor(seconds / 60);
  const hours = Math.floor(minutes / 60);
  if (hours) return `${hours}h ${(minutes % 60).toString().padStart(2, "0")}m`;
  return `${minutes}m ${(seconds % 60).toString().padStart(2, "0")}s`;
}

export function Now({ running, waiting, named }: {
  running: RunRow[]; waiting: Call[]; named: Map<string, string>;
}) {
  if (running.length === 0 && waiting.length === 0) return null;

  return (
    <section className="band mt-7">
      {running.length > 0 && (
        <div>
          <p className={EYEBROW}>Running now</p>
          <div className="mt-4 flex flex-col gap-4 stagger">
            {running.map((run) => (
              <Link
                key={run.id}
                to={`/runs/${run.id}`}
                className="settle no-underline text-ink block lift px-2 -mx-2 py-1 rounded-r"
              >
                {/* **Named by its PIPELINE, not by its id.** A run id is how the machine
                    addresses it; what somebody scanning the front door recognises is what it is
                    a run OF. The id is still where the link goes. */}
                <span className="flex items-baseline gap-3 flex-wrap">
                  <span className="font-display text-title">
                    {(run.pipeline_digest && named.get(run.pipeline_digest)) || run.id.slice(0, 8)}
                  </span>
                  {/* Elapsed SNAPS, in tabular figures — numbers never tween. */}
                  <span className="text-running tnum text-object">{elapsed(run.submitted_at)}</span>
                </span>
                {/* **`flow` is a MARKER, not a fill.** The first draft gave it `grow`, so it
                    filled the entire remainder — which says *everything not yet done is running
                    right now*. 9 of 24 done means 15 remain and only a handful are in flight;
                    the rest have not started, and the bar was claiming to know something it
                    does not. Found by rendering the page and looking at it.

                    `flow` is also the page's ONE claim that something is happening now, and it
                    is worthless if anything else wears it. */}
                <span className="mt-2 flex h-[7px] rounded-[1px] overflow-hidden bg-surface-2">
                  <i
                    className="bg-pea"
                    style={{
                      width: run.tasks_seen
                        ? `${(run.tasks_done / run.tasks_seen) * 100}%`
                        : "0%",
                    }}
                  />
                  <i className="flow bg-running w-[44px] shrink-0" />
                </span>
                <span className="mt-2 flex justify-between gap-4 text-secondary text-ink-3">
                  <span className="tnum">{run.tasks_done} of {run.tasks_seen} tasks</span>
                  <span>started by {run.submitted_by}</span>
                </span>
              </Link>
            ))}
          </div>
        </div>
      )}

      {waiting.length > 0 && (
        <div>
          <p className={EYEBROW}>Waiting on a person</p>
          <div className="mt-4 flex flex-col gap-4 stagger">
            {waiting.map((call) => (
              <Link
                key={call.where}
                to={call.where}
                className="settle no-underline block border-l-2 border-[var(--undecided)] pl-4
                           lift py-1 rounded-r"
              >
                {/* **It names the values.** `strandedness and fragment size`, not `2 items` —
                    a count is what you write when you have not looked (`ov-settled`). The
                    sentence is composed server-side, in `attention._waiting_on_a_person`. */}
                <span className="text-body text-ink">{call.what}</span>
                <span className="block text-secondary text-ink-3 mt-1">
                  nothing runs until they do
                </span>
              </Link>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
