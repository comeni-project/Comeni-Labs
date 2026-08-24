import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router";

import { useUrlState } from "../app/useUrlState";

import { useTitle } from "../app/useTitle";
import { Failed, Loading } from "../ui/States";
import { get } from "../wiener/api/client";
import { Console } from "./Console";
import { Graph } from "./Graph";
import { OverviewPanel } from "./Overview";
import { elapsed } from "./elapsed";
import { colourOf, isPhase } from "./phases";
import { useRunStream } from "./useRunStream";

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
  const [view, setView] = useUrlState("view", "overview");
  useTitle(id ? `Run ${id.slice(0, 8)}` : "Run");

  const state = useQuery({
    queryKey: ["run", id],
    queryFn: () => get<RunState>(`/api/runs/${id}`),
    refetchInterval: 5_000,
  });
  const stream = useRunStream(id);

  if (state.isPending) return <Loading what="the run" />;
  if (state.isError) return <Failed error={state.error} />;

  const run = state.data;
  const phase = isPhase(run.phase) ? run.phase : "queued";
  const now = Date.now();

  return (
    <div className="p-6 max-w-4xl mx-auto flex flex-col gap-4">
      <header className="flex flex-col gap-2">
        <Link to="/runs" className="text-label text-ink-3 no-underline hover:text-ink">
          ← Board
        </Link>
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
      </header>

      <section className="bg-surface border border-line rounded-[var(--r)] shadow-e2 overflow-hidden">
        <div className="flex items-center gap-3 px-4 py-2 border-b border-line bg-surface-2">
          {/* **Two views of one `RunState`, so switching is a render and never a fetch** —
              §9. The view lives in the URL because a link to a failing graph is the thing
              somebody pastes into a message. */}
          {/* **The overview is the front door and the console is a tab** — §18's ending
              condition is that a 400-task run can be read without reading text, which is a
              statement that the console cannot be the answer. It keeps its shape; it stops
              being what opens.

              `Tasks` is drawn DISABLED rather than hidden, the same call this file already
              makes about `Graph`: a control that goes nowhere silently is the mistake
              `Shell.tsx` records 3A shipping six of. It answers *what across the whole run
              retried*, and it arrives with the paged endpoint's screen. */}
          <Segment name="Overview" active={view === "overview"} onPick={() => setView("overview")} />
          <Segment name="Tasks" active={false} onPick={() => {}} disabled />
          <Segment name="Console" active={view === "console"} onPick={() => setView("console")} />
          <Segment name="Graph" active={view === "graph"} onPick={() => setView("graph")} />
          <span className="ml-auto text-label text-ink-3">
            {stream.following ? "following" : "not following"} · read-only until W4
          </span>
        </div>
        {view === "overview" ? (
          <OverviewPanel runId={run.run_id} />
        ) : view === "graph" ? (
          <Graph runId={run.run_id} />
        ) : stream.error ? (
          <p className="px-4 py-3 text-secondary text-ink-3">{stream.error}</p>
        ) : (
          <Console events={stream.events} following={stream.following} />
        )}
      </section>
    </div>
  );
}
