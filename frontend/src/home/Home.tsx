import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router";

import { get } from "../api/client";
import type { components } from "../api/schema";
import { useTitle } from "../app/useTitle";
import { Failed, Loading } from "../ui/States";
import { get as fromWiener } from "../wiener/api/client";
import type { components as wiener } from "../wiener/api/schema";
import { First } from "./First";
import { Now } from "./Now";
import { ByPipeline, ByRun } from "./Work";

type Attention = components["schemas"]["Attention"];
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

  const attention = useQuery({
    queryKey: ["attention"],
    queryFn: () => get<Attention>("/attention"),
  });
  const drafts = useQuery({
    queryKey: ["drafts"],
    queryFn: () => get<DraftsPage>("/pipeline/drafts"),
  });
  // **Wiener may simply not be there**, and that must not take the page down: a laboratory
  // reading which pipelines it has does not need the execution half to be up. `retry: false` so
  // an absent Wiener costs one request rather than four.
  const runs = useQuery({
    queryKey: ["runs", "board"],
    queryFn: () => fromWiener<RunsPage>("/api/runs?limit=25"),
    retry: false,
  });

  if (attention.isLoading || drafts.isLoading) return <Loading what="the lab's work" />;
  if (attention.error) return <Failed error={attention.error} />;
  if (drafts.error) return <Failed error={drafts.error} />;

  const pipelines = drafts.data?.drafts ?? [];
  const board = runs.data?.runs ?? [];

  // **The first-run state is its own composition**, not this page with everything hidden and
  // not a page of onboarding cards.
  if (pipelines.length === 0) return <First />;

  const named = new Map(
    pipelines.filter((p) => p.digest).map((p) => [p.digest!, p.name || p.id.slice(0, 8)]),
  );


  return (
    <div className="overflow-auto">
      {/* **Full-bleed at 44px, which is the artboards' page inset** — `padding: 28px 44px 40px`
          on every board. It was a centred `max-w-[1180px]` column, so on a wide screen the
          wordmark sat at x=44 and the table it belongs to started at x=318: the shell and the
          page read as two documents. */}
      <div className="px-11 pt-1 pb-10">
        <Now
          running={board.filter((run) => run.phase === "running")}
          waiting={attention.data?.mendel ?? []}
          named={named}
        />

        {/* **A hairline between what is happening and what you have.** The artboard rules the
            two apart — `height:1px; background:#141C20; margin:28px 0 0` — and without it the
            Work block reads as a continuation of the running run rather than as the other half
            of the page. It renders only when there IS a NOW band: a rule under nothing is a
            line drawn for its own sake, and the quiet page is meant to be shorter. */}
        {(board.some((run) => run.phase === "running") || (attention.data?.mendel ?? []).length > 0)
          && <div className="mt-7 h-px bg-line" />}

        <section className="mt-6">
          <div className="flex items-center gap-5 flex-wrap">
            <p className="font-data text-[9.5px] uppercase tracking-[.15em] text-ink-3 m-0">
              Work
            </p>
            {/* **A segmented control in a hairline box, and the live half is TINTED rather than
                filled.** `--link-soft` behind `--link` is the artboard's pairing; it shipped as
                `--surface-2` behind `--ink`, which is a grey chip that reads as pressed rather
                than as selected. Square, because nothing in this row has a radius. */}
            <div className="flex border border-surface-2">
              {(["pipeline", "run"] as const).map((which) => (
                <button
                  key={which}
                  type="button"
                  onClick={() => setView(which)}
                  aria-pressed={view === which}
                  className={`font-data text-[10px] uppercase tracking-[.08em] px-[13px] py-1.5
                              border-0 cursor-pointer transition-colors
                              ${view === which
                                ? "bg-[var(--link-soft)] text-[var(--link)]"
                                : "bg-transparent text-ink-3 hover:text-ink"}`}
                >
                  By {which}
                </button>
              ))}
            </div>

            {/* **One action, top right. The same button whether you have none or fifty.** */}
            <Link
              to="/build"
              className="ml-auto px-[13px] py-1.5 no-underline text-[12.5px]
                         border border-[var(--link-line)] text-[var(--link)] lift"
            >
              New pipeline
            </Link>
          </div>

          <div className="mt-5">
            {view === "pipeline"
              ? <ByPipeline rows={pipelines} runs={board} />
              : <ByRun runs={board} named={named} />}
          </div>

          {/* **Wiener being unreachable is said once, quietly, and never as a broken page.**
              The pipelines half is complete without it; what is missing is history. */}
          {runs.error && (
            <p className="text-secondary text-ink-3 mt-4 mb-0">
              Run history is unavailable — Wiener did not answer.
            </p>
          )}
        </section>
      </div>
    </div>
  );
}
