import { useState } from "react";

import type { AuthoringSession } from "../../api/types";
import { CallPanel } from "./CallPanel";
import { phaseWords, progressWords, usageWords } from "./format";

/** The page's one strip: the pipeline's name, its mode, where it is, the view toggle, and Run.
 *
 * **One strip and no tabs beneath it.** The builder that ships stacks four bands of chrome above
 * the first sentence anybody wants to read; this has the name at the size of what the page is
 * about, the status line beside it, and nothing between that and the work.
 */
export function LivingHeader({
  session,
  view,
  onView,
  onRun,
  running,
  stage = null,
  runError = null,
  runnable = false,
  openValues = 0,
  views = true,
}: {
  session: AuthoringSession;
  view: "canvas" | "artifact";
  onView: (view: "canvas" | "artifact") => void;
  onRun: () => void;
  running: boolean;
  stage?: string | null;
  runError?: string | null;
  /** Whether Run is connected. **An unconnected Run is disabled** — a live-looking control that
   *  does nothing is the one thing Task 14's walk may not find. */
  runnable?: boolean;
  /** Values nobody has answered yet — said beside the name, as the boards do. */
  openValues?: number;
  /** Whether there is a pipeline to switch views of — not while describing. */
  views?: boolean;
}) {
  const progress = progressWords(session);
  const spent = usageWords(session.usage);
  const [calls, setCalls] = useState(false);
  const waiting = session.phase === "failed" || session.turns.some((t) => t.state === "pending");

  return (
    <div className="flex flex-wrap items-baseline gap-4 px-6 pt-5 pb-4" data-testid="living-header">
      <h1 className="m-0 text-title font-semibold tracking-[-.03em] text-ink">
        {session.name || "Untitled analysis"}
      </h1>
      {openValues > 0 && (
        <span data-testid="needs-you-chip"
              className="self-center px-[8px] py-[2px] rounded-control text-[12px] font-semibold text-needs-you-ink"
              style={{ background: "var(--needs-you-soft)" }}>
          {openValues} {openValues === 1 ? "value needs you" : "values need you"}
        </span>
      )}
      <span className="font-data text-[11px] text-ink-3" data-testid="living-status">
        <span style={{ color: waiting ? "var(--measured)" : undefined }}>{phaseWords(session)}</span>
        {progress && <> · {progress}</>}
        {session.projection_current === false && " · pipeline outdated"}
        {` · revision ${session.revision}`}
      </span>
      {spent && (
        // The session's tokens and calls, carried by the poll the page already makes; the list
        // behind it is fetched only when opened (issue 191).
        <button type="button" data-testid="living-usage" aria-expanded={calls}
                onClick={() => setCalls(!calls)}
                className="bg-transparent border-0 p-0 cursor-pointer font-data text-[11px]
                           text-ink-3 hover:text-ink focus-visible:shadow-[var(--ring)]">
          {spent}
        </button>
      )}

      <div className="ml-auto flex items-center gap-4">
        {views && <div role="group" aria-label="view" className="flex gap-1 p-1 rounded-button" style={{ background: "var(--paper)", border: "1px solid var(--line)" }}>
          {(["canvas", "artifact"] as const).map((which) => (
            <button
              key={which}
              type="button"
              data-testid={`living-view-${which}`}
              aria-pressed={view === which}
              onClick={() => onView(which)}
              className={`px-[14px] py-[6px] rounded-control text-[13px] border cursor-pointer
                          focus-visible:shadow-[var(--ring)] ${view === which
                            ? "bg-surface text-ink font-semibold border-line"
                            : "bg-transparent text-ink-2 border-transparent hover:text-ink"}`}
            >
              {which === "canvas" ? "Canvas" : "Pipeline file"}
            </button>
          ))}
        </div>}
        <button
          type="button"
          data-testid="living-run"
          disabled={!runnable || running || session.graph.nodes.length === 0 || session.phase !== "complete"}
          onClick={onRun}
          className="px-[22px] py-[9px] border-0 rounded-button cursor-pointer font-semibold text-[13.5px]
                     bg-action text-on-action shadow-raise disabled:cursor-not-allowed disabled:opacity-40"
        >
          <span aria-hidden className="mr-[8px] text-[10px]">▶</span>
          {stage === "keeping" ? "Keeping…" : stage === "linting" ? "Checking…" : "Run"}
        </button>
        {runError && (
          <span role="alert" data-testid="living-run-error" className="text-secondary text-needs-you-ink">
            {runError}
          </span>
        )}
      </div>
      <CallPanel sessionId={session.id} calls={session.usage?.calls ?? 0} open={calls} />
    </div>
  );
}
