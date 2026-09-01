import { useQuery } from "@tanstack/react-query";
import { Link, useParams, useSearchParams } from "react-router";

import { useUrlState } from "../app/useUrlState";

import { useTitle } from "../app/useTitle";
import { Failed, Loading } from "../ui/States";
import { get } from "../wiener/api/client";
import { Cancel } from "./Cancel";
import { Console } from "./Console";
import { Envelope } from "./Envelope";
import { Graph } from "./Graph";
import { OverviewPanel, type OverviewData } from "./Overview";
import { Panels } from "./Panels";
import { Failure, type Attempt, type Failed as FailureDetail } from "./Failure";
import { Tasks } from "./Tasks";
import { Timeline } from "./Timeline";
import { elapsed } from "./elapsed";
import { colourOf, isPhase } from "./phases";
import { useRunStream } from "./useRunStream";

const TERMINAL = new Set(["succeeded", "failed", "cancelled", "lost"]);

type FailedTask = {
  process: string; tag?: string | null; latest_exit?: number | null;
  attempts: number; peak_rss_bytes?: number | null;
  /** New as of phase 4 — what each try asked for beside what it touched. */
  history?: Attempt[];
};

type RunState = {
  run_id: string;
  phase: string;
  counts: { succeeded: number; failed: number; cached: number; running: number;
            submitted: number };
  started_at_ms: number | null;
  ended_at_ms: number | null;
  /** Where the run went. The artboard puts it under the elapsed — `local · started 21:04` —
   *  because *where* is the other half of *when*, and a run on a cluster and one on this
   *  laptop are different facts about the same duration. */
  executor?: string;
  /** What a person called this pipeline — Plan 6 phase 2.
   *
   *  **Attached beside the projection, never folded into it.** A name came off the upload and
   *  is not in the events, so `wiener-core` never sees it. `""` for an artifact uploaded
   *  without one, and the header draws `run <id>` — never a name derived from the digest,
   *  which a reader could not tell from one somebody chose. */
  name?: string;
  /** When the fold last saw anything happen. **The *moving* panel is the only reader**, and it
   *  is the question a watched run actually raises: four tasks running and nothing completing
   *  for twenty minutes looks identical to a healthy run on every other panel. */
  last_activity_ms?: number | null;
};

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
export function Run() {
  // **The route's id, and never the projection's.** `RunState.run_id` is what the *fold*
  // learned from an event, and it is `""` until the first one lands — which is every run
  // between launch and its first task, and exactly the window somebody watches. Passing it
  // down asked `/api/runs//overview`, a 404 under a header reading `run ` with no id.
  //
  // The tell was that `useTitle` below already used the route id, so the browser tab said
  // `Run bb22cc33` over a page that did not know which run it was.
  const { id = "" } = useParams();
  const [params] = useSearchParams();
  const from = params.get("from");
  const [view, setView] = useUrlState("view", "overview");
  // **In the URL, for the same reason `view` is.** The artboard calls this pair *state, not a
  // second screen*, and state somebody can link to is the whole of the difference.
  const [board, setBoard] = useUrlState("board", "table");
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


  // **`limit: 1` because only the count is read.** `total` answers the same filters, so the
  // badge costs one row rather than a page of them — the A191 rule that a board is a query.
  const retried = useQuery({
    queryKey: ["retried", id],
    queryFn: () => get<{ total: number }>(`/api/runs/${id}/tasks?retried_only=true&limit=1`),
  });

  if (state.isPending) return <Loading what="the run" />;
  if (state.isError) return <Failed error={state.error} />;

  const run = state.data;
  const phase = isPhase(run.phase) ? run.phase : "queued";
  const now = Date.now();

  // **One sentence naming the process the run is actually on.** `STAR_ALIGN - 2 of 6 tasks
  // done, 2 running, 2 waiting for a slot` is the artboard's line, and every number in it is
  // already on the overview — the header was making a reader join them by eye.
  //
  // The process chosen is the one with work in flight, falling back to the last that reported.
  // **Absent rather than invented**: before any row exists there is no process to name, and a
  // sentence about a run that has not started is the page lying for its first minute.
  const rows = overview.data?.rows ?? [];
  const busy = rows.find((row) => row.running > 0) ?? rows.findLast((row) => row.tasks > 0);
  const waiting = busy ? busy.tasks - busy.done - busy.running - busy.failed : 0;
  const sentence = busy ? (
    <>
      <span className="text-ink">{busy.process}</span>{" \u00b7 "}
      {busy.done} of {busy.tasks} tasks done
      {busy.running > 0 && `, ${busy.running} running`}
      {waiting > 0 && `, ${waiting} waiting for a slot`}
      {busy.failed > 0 && `, ${busy.failed} failed`}
    </>
  ) : (
    "no task has reported yet"
  );

  const worst = failedTask.data?.tasks?.[0];
  const report = stream.events.find((event) => event.manifest?.report)?.manifest?.report ?? null;
  const failed: FailureDetail | null = worst
    ? {
        process: worst.process,
        tag: worst.tag,
        exit: worst.latest_exit ?? null,
        attempts: worst.attempts,
        peak_rss_bytes: worst.peak_rss_bytes ?? null,
        // **The ask comes from the failing ATTEMPT now, and falls back to the process row.**
        // The comment above used to read "`TaskOut` has no asked half", which was true until
        // phase 4 projected it — and the process row is an aggregate, so on a task that
        // escalated 36 → 48 → 72 it reported a ceiling that no single attempt was given. The
        // fallback stays for a run whose record predates the projection.
        asked_bytes: worst.history?.[worst.history.length - 1]?.memory_bytes
          ?? (overview.data?.rows ?? []).find((row) => row.process === worst.process)
            ?.memory_asked_bytes ?? null,
        history: worst.history,
        report,
      }
    // No task failed, but the run did. Say so with what the record has.
    : report
      ? { process: null, tag: null, exit: null, attempts: 1,
          peak_rss_bytes: null, asked_bytes: null, report }
      : null;

  return (
    <div className="gutter py-6 flex flex-col gap-4">
      {/* **The artboard's shelf.** Every run screen opens on a `--surface-2` band with an
          `--e1` lip, and the header was sitting bare on `--paper` — which is most of why the
          top of the page read as a different product from the panel below it. Three rows,
          the artboard's: where you came from, what this is, and how far along. */}
      <header className="-mx-[24px] md:-mx-[44px] -mt-6 mb-2 gutter pt-4 pb-3.5 bg-surface-2 border-b border-line
                         shadow-e1 relative z-[2] flex flex-col">
        <span className="flex items-center gap-3 mb-[3px]">
          <Link to="/runs" className="text-secondary text-ink-3 no-underline hover:text-ink">
            ← Board
          </Link>
          {/* Only when you came from one. A link back to a pipeline you never opened is a
              guess about where you were. */}
          {from && (
            <Link to={`/build?draft=${from}`}
                  className="ml-auto text-secondary text-pea no-underline hover:text-ink">
              ↩ pipeline
            </Link>
          )}
        </span>

        {/* **The phase sits beside the id, and the elapsed goes right.** They were the other
            way about — a dot floated at the far edge of a 1500px header, a full column away
            from the thing whose state it describes, and the elapsed on a line of its own as an
            uppercase label. The artboard reads `run 85bbe6a0 ● running ............ 7m12s`. */}
        {/* **A pill, not a dot** — `.design/RunView.dc.html` draws the phase as a bordered
            uppercase chip in its own colour beside the name. A 8px dot beside grey body text
            was legible and said nothing at a glance, which is the opposite of what a header
            whose job is the five-second answer needs.

            **`run <id>` and not a pipeline name.** The artboard's title is `rnaseq-counts`,
            and Wiener surfaces no name for a pipeline — `/runs` has `pipeline_digest` and no
            label anywhere. Inventing one from the digest would be a name nobody chose. */}
        {/* ══ THE HEADER, AGAINST `.design/RunView.dc.html` ══════════════════════════════
            Read the artboard beside the page rather than its annotations — four things were
            wrong here and none was visible from the code:

            **The title is SANS.** The artboard sets `font-size:31px; font-weight:600;
            letter-spacing:-.035em` with no family override, so it inherits the body sans; only
            the id carries `class="m"`. This was `font-data`, which made a pipeline's name read
            like an identifier — the opposite of the distinction the artboard draws between a
            name somebody chose and a hash nobody did.

            **The order is name · pill · id.** The id came second here, which put a hash between
            a name and its state.

            **The elapsed takes the phase's colour** — the artboard draws `21m 40s` in the same
            `#BD6DCD` as the running pill, so the two things that say *this is still going* say
            it together. It was grey.

            **CANCEL is rightmost, after the elapsed**, not tucked beside the pill where it sat
            in the reach of somebody aiming at the phase. */}
        <div className="flex items-baseline gap-3.5">
          <h1 className="font-display text-[31px] font-semibold leading-none text-ink m-0
                         tracking-[-.035em]">
            {run.name || `run ${id.slice(0, 8)}`}
          </h1>
          <span
            data-testid="run-phase"
            className="font-data text-label uppercase tracking-[.1em] px-2 py-[3px]"
            style={{ color: colourOf[phase],
                     background: `color-mix(in srgb, ${colourOf[phase]} 12%, transparent)`,
                     border: `1px solid color-mix(in srgb, ${colourOf[phase]} 27%, transparent)` }}
          >
            {run.phase}
          </span>
          {run.name && (
            <span className="font-data text-body text-ink-4">{id.slice(0, 8)}</span>
          )}

          <span className="ml-auto flex items-center gap-[22px]">
            <span className="text-right">
              <span className="block font-data text-[23px] leading-none tracking-[-.02em]
                               tabular-nums"
                    style={{ color: TERMINAL.has(run.phase) ? "var(--ink-2)" : colourOf[phase] }}>
                {elapsed(run.started_at_ms, run.ended_at_ms, now)}
              </span>
              {/* The artboard reads `local · started 21:04` — **the executor beside the
                  clock time**, because *where* a run went is the other half of *when*. */}
              {run.started_at_ms != null && (
                <span className="block font-data text-label text-ink-4 mt-1">
                  {run.executor ? `${run.executor} \u00b7 ` : ""}started{" "}
                  {new Date(run.started_at_ms).toLocaleTimeString([], {
                    hour: "2-digit", minute: "2-digit",
                  })}
                </span>
              )}
            </span>
            {!TERMINAL.has(run.phase) && <Cancel runId={id} />}
          </span>
        </div>

        {/* **The five-second answer, in one sentence** — `page-5`: *"Band 0 is the header, and
            its one sentence is the five-second answer. If a reader has to look at a chart to
            learn whether the run is fine, the header is wrong."* */}
        <p data-testid="run-sentence" className="text-body text-ink-3 mt-[11px] m-0">
          {sentence}
        </p>

      </header>

      {/* Above the overview, so a failed run says where it stopped without a click — and the
          failed process is what the table opens on beneath it, because the comparison is the
          diagnosis: one task at 63.8 GB beside eleven at 58 says what a single number cannot. */}
      {/* **Band 1 \u2014 four panels, and they come before the failure banner.** The banner is
          the detail of one task; the panels are the run. `page-5`: summary top, granular
          detail bottom. */}
      {view !== "console" && <Panels
        overview={overview.data}
        failed={run.counts.failed}
        retried={retried.data?.total ?? 0}
        lastMs={run.last_activity_ms ?? null}
        now={now}
        live={!TERMINAL.has(run.phase)}
        runId={id}
      />}

      {run.phase === "failed" && failed && <Failure failed={failed} />}

      {/* **What the run held, above the panel and outside the tabs.** It is not a fifth view:
          the envelope answers *how much of the machine was in use* and every tab answers a
          question about a step or a task, so putting it behind a segment would hide the one
          panel that is about the run as a whole. It renders nothing when the record is empty
          — absence is absence — so a stub run's page is simply shorter. */}
      {/* **Between the panels and the envelope**, which is the artboard's own order: summary,
          then when things ran, then what they held. It shares the envelope's x-axis — the run's
          own span — because time is the comparison that matters and `curve.ts` already
          establishes that each series keeps its own y. */}
      {view !== "console" && (
        <Timeline runId={id} live={!TERMINAL.has(run.phase)} onPickLane={setOnly} />
      )}

      <Envelope runId={id} live={!TERMINAL.has(run.phase)} />

      {/* ══ BANDS, NOT TABS — `.design/RunView.dc.html` ═══════════════════════════════════
          **The page was four tabs and the artboard is one scrolling page.** `page-5`'s
          annotation is the argument: *"THE PYRAMID, AND WHY THE ORDER IS FIXED. Summary top,
          trend middle, granular detail bottom"* and *"Drill down IN PLACE. Clicking a timeline
          lane filters the tasks table below it. Never a second page for the same run."*

          A tab IS a second page for the same run. Four of them meant the answer to *is this
          fine* was behind a click, and the table/graph pair — which the artboard names
          explicitly as *"STATE, NOT A SECOND SCREEN... two artboards and that was two chances
          to drift"* — were two of the four.

          **The console stays a separate view**, and that is the artboards' own split:
          `RunConsole.dc.html` is its own board, reached from the tasks band's header. It is
          the one panel that is a stream rather than a summary, and the artboard draws it
          full-height because that is what reading a log needs. */}
      {view === "console" ? (
        <section className="flex flex-col flex-1 min-h-0 bg-surface border border-line
                            rounded-[var(--r)] shadow-e2 overflow-hidden">
          <div className="shrink-0 flex items-center gap-3 px-4 py-[9px]
                          border-b border-line bg-surface-2">
            <span className="text-label uppercase tracking-[.08em] text-ink-3">console</span>
            <button type="button" data-testid="close-console" onClick={() => setView("overview")}
                    className="bg-transparent border-0 cursor-pointer text-label text-ink-3
                               hover:text-ink px-1">
              &larr; back to the run
            </button>
            {/* **`read-only until W4` came down with the first verb.** It was true for as long
                as nothing could act on a run, and the moment `cancel` shipped it became a
                promise the page was breaking. A stale reassurance is worse than none. */}
            <span className="ml-auto text-label text-ink-3">
              {stream.following
                ? "following"
                : TERMINAL.has(run.phase) ? "not following \u00b7 the run is over"
                : "not following"}
            </span>
          </div>
          {stream.error ? (
            <p className="px-4 py-3 text-secondary text-ink-3">{stream.error}</p>
          ) : (
            <Console
              events={stream.events}
              following={stream.following}
              process={only}
              onClearProcess={() => setOnly("")}
              onFilter={(process) => setOnly(process)}
            />
          )}
        </section>
      ) : (
        <>
          {/* --- processes -------------------------------------------------------------
              **The toggle is state, not a second screen.** Both halves read the same
              `RunState`, so switching is a render and never a fetch. */}
          <section data-testid="band-processes"
                   className="flex flex-col bg-surface border border-line
                              rounded-[var(--r)] shadow-e2 overflow-hidden">
            <div className="shrink-0 flex items-center gap-3 px-4 py-[9px]
                            border-b border-line bg-surface-2">
              <span className="text-label uppercase tracking-[.08em] text-ink-3">processes</span>
              <span className="ml-auto flex items-center gap-1">
                {(["table", "graph"] as const).map((name) => (
                  <button
                    key={name}
                    type="button"
                    data-testid={`board-${name}`}
                    aria-pressed={board === name}
                    onClick={() => setBoard(name)}
                    className={`bg-transparent border cursor-pointer px-2.5 py-1
                                text-label uppercase tracking-[.08em]
                                ${board === name
                                  ? "text-ink border-line bg-surface"
                                  : "text-ink-3 border-transparent hover:text-ink"}`}
                    style={{ transition: `color var(--t)` }}
                  >
                    {name}
                  </button>
                ))}
              </span>
            </div>
            {board === "table" ? (
              <OverviewPanel
                runId={id}
                openOn={failed?.process}
                onOpenConsole={(process) => { setOnly(process); setView("console"); }}
                onOpenGraph={() => setBoard("graph")}
              />
            ) : (
              // The graph asks for `flex-1 min-h-0` inside, and this band sizes to content —
              // so without a floor the canvas gets whatever is left over, which is the
              // clipped-to-a-sliver defect the old section carried a note about.
              <div className="flex flex-col min-h-[420px]">
                <Graph
                  runId={id}
                  onOpenConsole={(process) => { setOnly(process); setView("console"); }}
                />
              </div>
            )}
          </section>

          {/* --- tasks, and the console link the artboard puts in its header ------------- */}
          <section data-testid="band-tasks"
                   className="flex flex-col bg-surface border border-line
                              rounded-[var(--r)] shadow-e2 overflow-hidden">
            <div className="shrink-0 flex items-center gap-3 px-4 py-[9px]
                            border-b border-line bg-surface-2">
              <span className="text-label uppercase tracking-[.08em] text-ink-3">tasks</span>
              <button type="button" data-testid="open-console"
                      onClick={() => setView("console")}
                      className="ml-auto bg-transparent border border-line cursor-pointer
                                 px-2.5 py-1 text-label uppercase tracking-[.08em] text-ink-3
                                 hover:text-ink"
                      style={{ transition: `color var(--t)` }}>
                console
              </button>
            </div>
            <Tasks
              runId={id}
              processes={(overview.data?.rows ?? []).map((row) => row.process)}
              openOn={only || undefined}
            />
          </section>
        </>
      )}
    </div>
  );
}
