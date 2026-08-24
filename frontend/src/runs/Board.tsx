import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router";

import { useTitle } from "../app/useTitle";
import { Empty, Failed, Loading } from "../ui/States";
import { get } from "../wiener/api/client";
import { isUnauthorized, TokenPrompt } from "../wiener/Token";
import type { components } from "../wiener/api/schema";
import { colourOf, isPhase } from "./phases";

type RunRow = components["schemas"]["RunRow"];

const eyebrow = "font-ui text-label uppercase tracking-[.14em] font-semibold text-ink-3";

/** One row per run — and a gate is not one.
 *
 * Built against `docs/design/wiener-mockups/Board.dc.html` rather than invented. Two things the
 * mockup shows are **deliberately absent**, and both are absences with reasons rather than
 * omissions:
 *
 * - **"12 samples"**. Nothing here can say how many samples a run has, because §7.1 forbids a
 *   table holding a samplesheet and the parameters ride to the launcher as a job argument. The
 *   mockup was drawn before that rule had teeth; the executor is what remains true.
 * - **task progress**. The board reads `GET /api/runs`, which is one row per run and no fold.
 *   Counts per run would mean folding every run's events on every page load, which §7.1 calls
 *   out as the reason `run_task` exists at all. It belongs on the run page, where one fold
 *   serves one run.
 *
 * **Phase is drawn as a colour AND a word.** The colour is the same vocabulary the builder and
 * the forge use; the word is what makes `failed` and `lost` — which share a hue on purpose —
 * distinguishable, and what makes the row legible to somebody who cannot separate the two.
 */
function Row({ run }: { run: RunRow }) {
  const phase = isPhase(run.phase) ? run.phase : "queued";
  return (
    <Link
      data-testid={`run-${run.id}`}
      to={`/runs/${run.id}`}
      className="grid grid-cols-[1fr_auto_auto] items-center gap-4 px-4 py-3.5 no-underline
                 text-ink border-b border-line last:border-b-0
                 transition-colors hover:bg-surface-2"
    >
      <span className="flex flex-col gap-0.5">
        <span className="font-data text-body">{run.id.slice(0, 8)}</span>
        <span className="text-label text-ink-3">{run.executor}</span>
      </span>
      <span className="flex items-center gap-2 text-body">
        <span
          aria-hidden
          className="inline-block w-2 h-2 rounded-full"
          style={{ background: colourOf[phase] }}
        />
        {run.phase}
      </span>
      <time className="text-label text-ink-3 tabular-nums" dateTime={run.submitted_at}>
        {new Date(run.submitted_at).toLocaleString()}
      </time>
    </Link>
  );
}

export function Board() {
  useTitle("Runs");
  const runs = useQuery({
    queryKey: ["runs"],
    queryFn: () => get<RunRow[]>("/api/runs"),
    // A board of live runs goes stale by itself. Five seconds is a guess like `MAXLEN ~ 10000`
    // is a guess, and it is cheap to be wrong about: the run PAGE tails a socket, so this is
    // only how fast the list of runs catches up, never how fast a run does.
    refetchInterval: 5_000,
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

  return (
    <div className="p-6 max-w-4xl mx-auto flex flex-col gap-4">
      <header className="flex flex-col gap-1">
        <h1 className={eyebrow}>Runs</h1>
        <p className="text-body text-ink-2">
          One row per run — a gate is not a run, and none of these is one.
        </p>
      </header>

      <section className="bg-surface border border-line rounded-[var(--r)] shadow-e2 overflow-hidden">
        {runs.data.length === 0 ? (
          <Empty title="No runs yet." next="Wiener runs a pipeline the Builder has gated." />
        ) : (
          runs.data.map((run) => <Row key={run.id} run={run} />)
        )}
      </section>

      <footer className="text-label text-ink-3">
        {runs.data.length} {runs.data.length === 1 ? "run" : "runs"} · the record is kept
        forever; the live tail is not
      </footer>
    </div>
  );
}
