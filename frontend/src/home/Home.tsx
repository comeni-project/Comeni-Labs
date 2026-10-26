import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router";

import { get } from "../api/client";
import type { components } from "../api/schema";
import { useTitle } from "../app/useTitle";
import { Failed, Loading } from "../ui/States";
import { get as fromWiener } from "../wiener/api/client";
import type { components as wiener } from "../wiener/api/schema";
import { Describe } from "./Describe";
import { First } from "./First";
import { NeedsYouCard, ResultsCard, RunningCard, WentWrongCard } from "./Cards";
import { useAiConfigured } from "./useAiConfigured";
import { ByPipeline, ByRun } from "./Work";

type DraftsPage = components["schemas"]["DraftsPage"];
type RunsPage = wiener["schemas"]["RunsPage"];

/** The front door: **the lab's work**, not the product's inventory.
 *
 * ═══ WHAT THIS PAGE REPLACED, AND WHY ═════════════════════════════════════════════════════
 *
 * Until 2026-08-30 this was a landing page — a hero, a tagline, *Open the forge*, *Browse the
 * tools*, and a `standing` block reporting 12 contracts and 22 types. Every one of its calls to
 * action pointed at the forge, which phase 0 removed from the navigation, and the block that
 * made it feel substantial was reporting **the product's state rather than the reader's**.
 * `ov-settled` is blunt about it: *that is why the old page read as slop — information with no
 * question behind it.*
 *
 * **`forge-review.md` §3 said this page may not exist.** An Overview was designed and CUT once
 * for answering the same question as the forge Queue, and two tests held the rule that `/`
 * counts and links and never renders an item. The operator ruled that constraint dead; §3 now
 * records the lift, and the **narrower** rule survives and is still enforced — this page renders
 * pipelines and runs, and may never render a contract id, a question subject or a drift row.
 *
 * ═══ THE ONE RULE THAT GOVERNS EVERY BLOCK ════════════════════════════════════════════════
 *
 * **ABSENCE IS ABSENCE.** Compare the `Overview` and `OverviewQuiet` artboards: the difference
 * is not a different empty state, it is that the NOW band **does not exist**. The page is simply
 * shorter. If every block is empty, the page is the shell plus Work plus *New pipeline* — a
 * legitimate page, not a broken one.
 *
 * ═══ THE BROWSER IS THE COURIER ═══════════════════════════════════════════════════════════
 *
 * This is the **second** place in the product that touches both halves — `useSubmit.ts` was the
 * first, and its header carries the argument. Neither API learns the other exists; the join is
 * done here, on the **pipeline digest**, which is content-addressed and therefore the only key
 * that does not require one server to know the other's identifiers (`wiener.md` §12).
 */
export function Home() {
  useTitle();
  const [view, setView] = useState<"pipeline" | "run">("pipeline");

  const drafts = useQuery({
    queryKey: ["drafts"],
    queryFn: () => get<DraftsPage>("/pipeline/drafts"),
  });
  // **Wiener may simply not be there**, and that must not take the page down: reading which
  // pipelines you have does not need the execution half to be up. `retry: false` so an absent
  // Wiener costs one request rather than four.
  const runs = useQuery({
    queryKey: ["runs", "board"],
    queryFn: () => fromWiener<RunsPage>("/api/runs?limit=25"),
    retry: false,
  });

  // **Whether a model is configured is waited for with the rest** (issue 268): it decides
  // whether the describe box is drawn, and a box arriving after the page lost what was typed.
  const model = useAiConfigured();

  if (drafts.isLoading || model.pending) return <Loading what="your work" />;
  if (drafts.error) return <Failed error={drafts.error} />;

  const pipelines = drafts.data?.drafts ?? [];
  const board = runs.data?.runs ?? [];

  // **The first-run state is its own composition**, not this page with everything hidden.
  if (pipelines.length === 0) return <First />;

  const named = new Map(
    pipelines.filter((p) => p.digest).map((p) => [p.digest!, p.name || p.id.slice(0, 8)]),
  );
  const running = board.filter((run) => run.phase === "running").length;
  const open = pipelines.reduce((n, p) => n + (p.open_values ?? []).length + p.open_not_named, 0);
  const summary = [
    `${pipelines.length} ${pipelines.length === 1 ? "pipeline" : "pipelines"}`,
    running > 0 && `${running} running`,
    open > 0 && `${open} ${open === 1 ? "value needs" : "values need"} you`,
  ].filter(Boolean).join(" · ");

  return (
    <div className="overflow-auto">
      <div className="gutter pt-7 pb-10 flex flex-col gap-6">
        <header className="flex flex-wrap items-end gap-4">
          <div className="flex-1 min-w-0">
            <h1 className="m-0 text-title font-semibold tracking-[-.02em] text-ink">Your work</h1>
            <p data-testid="home-summary" className="m-0 mt-1 text-body text-ink-2">{summary}</p>
          </div>
          {/* **One action, top right. The same button whether you have none or fifty.** */}
          <Link to="/build"
                className="px-[18px] py-[9px] rounded-button no-underline text-[13.5px] font-semibold
                           bg-action text-on-action shadow-raise focus-visible:shadow-[var(--ring)]">
            New analysis
          </Link>
        </header>

        {/* **A new conversation starts here once there is work** (issue 229); `First` is where
            it starts before there is any. It renders nothing without a model. */}
        <Describe />

        {/* **Each card only when it has something** — absence is absence, so the quiet page is
            simply shorter. They wrap into one column on a narrow screen. */}
        <div className="grid gap-4 [grid-template-columns:repeat(auto-fit,minmax(300px,1fr))] empty:hidden">
          <RunningCard runs={board} named={named} />
          <NeedsYouCard drafts={pipelines} />
          <WentWrongCard runs={board} named={named} />
        </div>

        <div className="grid gap-4 items-start grid-cols-1 xl:grid-cols-[minmax(0,1fr)_340px]">
          <section aria-label="Your pipelines" className="min-w-0 flex flex-col gap-3">
            <div className="flex items-center gap-4 flex-wrap">
              <h2 className="m-0 text-heading font-semibold text-ink">Your pipelines</h2>
              <div role="group" aria-label="list by" className="flex gap-1 p-1 rounded-button"
                   style={{ background: "var(--paper)", border: "1px solid var(--line)" }}>
                {(["pipeline", "run"] as const).map((which) => (
                  <button
                    key={which}
                    type="button"
                    onClick={() => setView(which)}
                    aria-pressed={view === which}
                    className={`px-[12px] py-[4px] rounded-control text-[13px] border cursor-pointer
                                focus-visible:shadow-[var(--ring)] ${view === which
                                  ? "bg-surface text-ink font-semibold border-line"
                                  : "bg-transparent text-ink-2 border-transparent hover:text-ink"}`}
                  >
                    By {which}
                  </button>
                ))}
              </div>
            </div>
            <div className="rounded-panel border border-line bg-surface overflow-x-auto px-4">
              {view === "pipeline"
                ? <ByPipeline rows={pipelines} runs={board} />
                : <ByRun runs={board} named={named} />}
            </div>
            {view === "pipeline" && (
              <p className="m-0 text-[13px] text-ink-3">
                "How it was decided" counts every value in the pipeline: settled by a rule, a convention or you,
                measured from your files, or still open.
              </p>
            )}
            {/* **Wiener being unreachable is said once, quietly, and never as a broken page.**
                The pipelines half is complete without it; what is missing is history. */}
            {runs.error && (
              <p className="text-secondary text-ink-3 m-0">
                Run history is unavailable — Wiener did not answer.
              </p>
            )}
          </section>
          <ResultsCard runs={board} named={named} />
        </div>
      </div>
    </div>
  );
}
