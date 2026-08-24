import { useQuery } from "@tanstack/react-query";
import { Link, useParams, useSearchParams } from "react-router";

import { useUrlState } from "../app/useUrlState";

import { useTitle } from "../app/useTitle";
import { Failed, Loading } from "../ui/States";
import { get } from "../wiener/api/client";
import { Console } from "./Console";
import { Graph } from "./Graph";
import { OverviewPanel, type OverviewData } from "./Overview";
import { Failure, type Failed as FailureDetail } from "./Failure";
import { Tasks } from "./Tasks";
import { elapsed } from "./elapsed";
import { colourOf, isPhase } from "./phases";
import { useRunStream } from "./useRunStream";

const TERMINAL = new Set(["succeeded", "failed", "cancelled", "lost"]);

type FailedTask = {
  process: string; tag?: string | null; latest_exit?: number | null;
  attempts: number; peak_rss_bytes?: number | null;
};

type RunState = {
  run_id: string;
  phase: string;
  counts: { succeeded: number; failed: number; cached: number; running: number;
            submitted: number };
  started_at_ms: number | null;
  ended_at_ms: number | null;
};

const eyebrow = "font-ui text-label uppercase tracking-[.14em] font-semibold text-ink-3";

/** One run, watched. Built against `wiener-mockups/Main.dc.html`.
 *
 * **The right-hand column is not here, and that is §18.1 rather than an oversight**: there is
 * no chat panel until W3, and stubbing an empty one is how a screen comes to look finished
 * while doing nothing. The `Graph` segment IS drawn, disabled, because a control that goes
 * nowhere *silently* is what `Shell.tsx` records as the mistake 3A shipped six of.
 *
 * The header's counts come from the projection; the console's rows come from the stream. Both
 * are the same events — one folded, one in order — which is why they cannot disagree.
 */
function Segment({ name, active, onPick, disabled = false }: {
  name: string; active: boolean; onPick: () => void; disabled?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onPick}
      aria-pressed={active}
      disabled={disabled}
      title={disabled ? "arrives with the paged tasks endpoint" : undefined}
      className={`text-body disabled:cursor-not-allowed disabled:opacity-40
                  ${active ? "font-semibold text-ink" : "text-ink-3 hover:text-ink"}`}
    >
      {name}
    </button>
  );
}

export function Run() {
  const { id } = useParams();
  const [params] = useSearchParams();
  const from = params.get("from");
  const [view, setView] = useUrlState("view", "overview");
  // §7's zoom-and-filter rung: the overview's right-click lands here, and the URL
  // carries it so a filtered console is a link somebody can paste.
  const [only, setOnly] = useUrlState("process", "");
  useTitle(id ? `Run ${id.slice(0, 8)}` : "Run");

  const state = useQuery({
    queryKey: ["run", id],
    queryFn: () => get<RunState>(`/api/runs/${id}`),
    refetchInterval: 5_000,
  });
  const stream = useRunStream(id);
  // The same query key `OverviewPanel` uses, so react-query serves both from one request —
  // the header needs the denominator and the table needs the rows, and they are one fact.
  const overview = useQuery({
    queryKey: ["overview", id],
    queryFn: () => get<OverviewData>(`/api/runs/${id}/overview`),
    refetchInterval: 4_000,
  });

  // **Assembled from the record, and only when the run actually failed.** The failed task
  // comes from the tasks projection, the memory it was ALLOWED from the overview row for its
  // process — `TaskOut` has no asked half — and the report from the error event the console
  // already holds. Three sources because they are three different facts, not because the
  // banner is doing arithmetic.
  const failedTask = useQuery({
    queryKey: ["failed-task", id],
    queryFn: () => get<{ tasks: FailedTask[] }>(
      `/api/runs/${id}/tasks?status=FAILED&sort=-peak_rss_bytes&limit=1`,
    ),
    enabled: state.data?.phase === "failed",
  });


  if (state.isPending) return <Loading what="the run" />;
  if (state.isError) return <Failed error={state.error} />;

  const run = state.data;
  const phase = isPhase(run.phase) ? run.phase : "queued";
  const now = Date.now();

  const worst = failedTask.data?.tasks?.[0];
  const report = stream.events.find((event) => event.manifest?.report)?.manifest?.report ?? null;
  const failed: FailureDetail | null = worst
    ? {
        process: worst.process,
        tag: worst.tag,
        exit: worst.latest_exit ?? null,
        attempts: worst.attempts,
        peak_rss_bytes: worst.peak_rss_bytes ?? null,
        asked_bytes: (overview.data?.rows ?? []).find((row) => row.process === worst.process)
          ?.memory_asked_bytes ?? null,
        report,
      }
    // No task failed, but the run did. Say so with what the record has.
    : report
      ? { process: null, tag: null, exit: null, attempts: 1,
          peak_rss_bytes: null, asked_bytes: null, report }
      : null;

  const declared = overview.data?.steps_declared ?? 0;
  const finished = overview.data?.steps_finished ?? 0;

  return (
    <div className="p-6 flex flex-col gap-4">
      <header className="flex flex-col gap-2">
        <span className="flex items-center gap-4">
          <Link to="/runs" className="text-label text-ink-3 no-underline hover:text-ink">
            ← Board
          </Link>
          {/* Only when you came from one. A link back to a pipeline you never opened is a
              guess about where you were. */}
          {from && (
            <Link to={`/build?draft=${from}`}
                  className="text-label text-ink-3 no-underline hover:text-ink">
              ↩ pipeline
            </Link>
          )}
        </span>
        <div className="flex items-baseline justify-between gap-4">
          <h1 className="font-data text-title text-ink">run {run.run_id.slice(0, 8)}</h1>
          <span className="flex items-center gap-2 text-body">
            <span
              aria-hidden
              className="inline-block w-2 h-2 rounded-full"
              style={{ background: colourOf[phase] }}
            />
            {run.phase}
          </span>
        </div>
        <p className={eyebrow}>
          {elapsed(run.started_at_ms, run.ended_at_ms, now)} elapsed
        </p>

        {/* **Steps finished of steps DECLARED** — §5, and the only denominator anybody can
            source. Nextflow discovers tasks as channels emit, so a task-level percentage is a
            number that grows under you; the artifact declares its steps before the run starts.

            **Drawn from the current numbers on every render, and never from a remembered
            maximum.** This count is not monotonic and cannot be: a step with three tasks done
            is finished until a fourth is submitted, and Checkpoint 1 asked exactly this. A bar
            that only ever fills would be monotonic and false.

            Absent when `steps_declared` is 0 — A192: the artifact could not be read, and a bar
            over a denominator of zero is an invented number. */}
        {declared > 0 && (
          <span data-testid="run-progress" className="flex flex-col gap-1.5 mt-1">
            <span className="flex items-baseline gap-2">
              <span className="text-secondary text-ink-2 tabular-nums">
                {finished} of {declared} steps finished
              </span>
              {/* Where the denominator came from, said out loud — §5's whole argument is that
                  this is the only one anybody can source. */}
              <span className="text-label text-ink-3">declared by the artifact</span>
            </span>
            <span className="block h-1.5 rounded-full overflow-hidden max-w-md"
                  style={{ background: "var(--line)", boxShadow: "var(--well)" }}>
              <span
                className="block h-full"
                style={{ width: `${(finished / declared) * 100}%`,
                         background: "var(--pea)", transition: `width var(--t)` }}
              />
            </span>
          </span>
        )}
      </header>

      {/* Above the overview, so a failed run says where it stopped without a click — and the
          failed process is what the table opens on beneath it, because the comparison is the
          diagnosis: one task at 63.8 GB beside eleven at 58 says what a single number cannot. */}
      {run.phase === "failed" && failed && <Failure failed={failed} />}

      <section className="bg-surface border border-line rounded-[var(--r)] shadow-e2 overflow-hidden">
        <div className="flex items-center gap-3 px-4 py-2 border-b border-line bg-surface-2">
          {/* **Two views of one `RunState`, so switching is a render and never a fetch** —
              §9. The view lives in the URL because a link to a failing graph is the thing
              somebody pastes into a message. */}
          {/* **The overview is the front door and the console is a tab** — §18's ending
              condition is that a 400-task run can be read without reading text, which is a
              statement that the console cannot be the answer. It keeps its shape; it stops
              being what opens.

              §6's two questions, one row component: `Overview` expands a process to ask *what
              did this process do*, and `Tasks` spans the run to ask *what retried*. */}
          <Segment name="Overview" active={view === "overview"} onPick={() => setView("overview")} />
          <Segment name="Console" active={view === "console"} onPick={() => setView("console")} />
          <Segment name="Graph" active={view === "graph"} onPick={() => setView("graph")} />
          <Segment name="Tasks" active={view === "tasks"} onPick={() => setView("tasks")} />
          <span className="ml-auto text-label text-ink-3">
            {stream.following
              ? "following · read-only until W4"
              : TERMINAL.has(run.phase) ? "not following · the run is over"
              : "not following · read-only until W4"}
          </span>
        </div>
        {view === "overview" ? (
          <OverviewPanel runId={run.run_id} openOn={failed?.process} />
        ) : view === "tasks" ? (
          <Tasks
            runId={run.run_id}
            processes={(overview.data?.rows ?? []).map((row) => row.process)}
          />
        ) : view === "graph" ? (
          <Graph runId={run.run_id} />
        ) : stream.error ? (
          <p className="px-4 py-3 text-secondary text-ink-3">{stream.error}</p>
        ) : (
          <Console
            events={stream.events}
            following={stream.following}
            process={only}
            onClearProcess={() => setOnly("")}
          />
        )}
      </section>
    </div>
  );
}
