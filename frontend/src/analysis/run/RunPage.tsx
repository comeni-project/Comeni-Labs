import { Link, Navigate, NavLink, useParams, useSearchParams } from "react-router";

import { useAnalysis } from "../../app/AnalysisFrame";
import { RailControls } from "../../app/rail/RailContext";
import { useTitle } from "../../app/useTitle";
import { Failed, Loading } from "../../ui/States";
import { Cancel } from "./Cancel";
import { ConsolePage } from "./ConsolePage";
import { DeleteRun } from "./DeleteRun";
import { elapsed } from "./elapsed";
import { dotOf, phaseWords, TERMINAL, type RunRow } from "./model";
import { Outputs } from "./Outputs";
import { Overview } from "./Overview";
import { Send } from "./Send";
import { Steps } from "./Steps";
import { useAnalysisRuns, useRun } from "./useRuns";

const SUBS = new Set(["steps", "outputs", "console"]);

/** Run (#511), at `/a/:draft/run[/:id[/:sub]]`: the analysis's runs, in its frame. Without a run
 *  open, the latest one opens; with none yet, or `?new`, the page that sends one. */
export function RunPage() {
  const { draftId } = useAnalysis();
  const { id, sub } = useParams();
  const [params] = useSearchParams();
  const runs = useAnalysisRuns(draftId);
  const base = `/a/${encodeURIComponent(draftId)}/run`;
  const rail = <RunsRail base={base} runs={runs.list} open={id} />;

  if (!id) {
    if (params.has("new") || (!runs.loading && runs.list.length === 0)) {
      return <>{rail}<Send draftId={draftId} kept={!!runs.row?.kept && !runs.row.changed_since_kept} /></>;
    }
    if (runs.loading) return <Loading what="the runs" />;
    return <Navigate to={`${base}/${encodeURIComponent(runs.list[0].run.id)}`} replace />;
  }
  const n = runs.list.find(({ run }) => run.id === id)?.n;
  return <>{rail}<RunView key={id} draftId={draftId} runId={id} n={n}
                          sub={sub && SUBS.has(sub) ? sub : undefined} base={`${base}/${encodeURIComponent(id)}`} /></>;
}

/** *Runs of this analysis*, in the rail: each with its state, and a new one. */
function RunsRail({ base, runs, open }: { base: string; runs: { run: RunRow; n: number }[]; open?: string }) {
  return (
    <RailControls label="Runs of this analysis">
      <ul aria-label="Runs of this analysis" className="list-none m-0 p-0 flex flex-col">
        {runs.map(({ run, n }) => (
          <li key={run.id}>
            <NavLink to={`${base}/${encodeURIComponent(run.id)}`} aria-current={run.id === open ? "page" : undefined}
                     className={`flex items-center gap-2 px-[10px] py-[6px] rounded-control text-[13px] no-underline
                                 ${run.id === open ? "bg-now-soft text-now-ink font-semibold" : "text-ink-2 hover:bg-surface-2"}`}>
              <span aria-hidden className="w-[7px] h-[7px] rounded-full shrink-0" style={{ background: dotOf(run.phase) }} />
              Run {n}
              <span className="ml-auto text-[11.5px] font-normal text-ink-3">{whenOf(run)}</span>
            </NavLink>
          </li>
        ))}
        <li>
          <Link to={`${base}?new`} className="flex items-center px-[10px] py-[6px] text-[13px] text-now-ink no-underline hover:underline">
            + New run
          </Link>
        </li>
      </ul>
    </RailControls>
  );
}

/** *now*, *failed · 12:40*, *done · yesterday*. */
function whenOf(run: RunRow): string {
  if (!TERMINAL.has(run.phase)) return "now";
  const at = new Date(run.ended_at ?? run.submitted_at);
  const today = new Date();
  const day = at.toDateString() === today.toDateString() ? at.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
    : at.toDateString() === new Date(today.getTime() - 86_400_000).toDateString() ? "yesterday"
    : at.toLocaleDateString([], { day: "numeric", month: "short" });
  return `${run.phase === "succeeded" ? "done" : phaseWords(run.phase).toLowerCase()} · ${day}`;
}

function RunView({ draftId, runId, n, sub, base }: {
  draftId: string; runId: string; n?: number; sub?: string; base: string;
}) {
  const run = useRun(runId);
  const title = n ? `Run ${n}` : `Run ${runId.slice(0, 8)}`;
  useTitle(title);
  if (run.state.isPending) return <Loading what="the run" />;
  if (run.state.isError) return <Failed error={run.state.error} />;
  const state = run.state.data;
  const now = Date.now();

  return (
    <div className="overflow-y-auto h-full">
      <div className="px-4 sm:px-6 pt-4 pb-10 flex flex-col gap-3 min-h-full">
        <header className="flex flex-wrap items-center gap-x-3 gap-y-1">
          <h1 className="m-0 text-[22px] font-semibold tracking-[-.015em] text-ink">{title}</h1>
          <span data-testid="run-phase" className="flex items-center gap-[6px] px-2 py-[3px] rounded-control text-[12px] font-semibold"
                style={{ color: inkOf(state.phase), background: `color-mix(in srgb, ${dotOf(state.phase)} 13%, transparent)` }}>
            <span aria-hidden className="w-[6px] h-[6px] rounded-full" style={{ background: dotOf(state.phase) }} />
            {phaseWords(state.phase)}
          </span>
          <span className="text-[13px] text-ink-2">
            {state.started_at_ms != null && `started ${new Date(state.started_at_ms).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })} · `}
            <span className="tabular-nums">{elapsed(state.started_at_ms, state.ended_at_ms, now)}</span>
            {state.executor === "local" ? " · this machine" : state.executor ? ` · ${state.executor}` : ""}
          </span>
          <span className="ml-auto flex items-center gap-2">
            {!run.live && <DeleteRun runId={runId} phase={state.phase} />}
          </span>
        </header>
        {state.work_cleared && (
          <p className="m-0 text-[12.5px] text-ink-3">
            Working files cleared by this installation's retention setting. The results and the record stay.
          </p>
        )}
        {sub === "steps" ? <Steps draftId={draftId} runId={runId} live={run.live} />
          : sub === "outputs" ? <Outputs draftId={draftId} runId={runId} live={run.live} />
          : sub === "console" ? <ConsolePage runId={runId} phase={state.phase} />
          : <Overview draftId={draftId} runId={runId} base={base} state={state} live={run.live}
                      stop={run.live ? <Cancel runId={runId} /> : null} />}
      </div>
    </div>
  );
}

function inkOf(phase: string): string {
  if (phase === "succeeded") return "var(--done-ink)";
  if (phase === "failed" || phase === "lost") return "var(--needs-you-ink)";
  if (phase === "cancelled") return "var(--ink-2)";
  return "var(--now-ink)";
}
