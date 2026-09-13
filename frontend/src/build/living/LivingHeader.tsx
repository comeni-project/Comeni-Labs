import type { AuthoringSession } from "../../api/types";
import { phaseWords, progressWords } from "./format";

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
}: {
  session: AuthoringSession;
  view: "canvas" | "artifact";
  onView: (view: "canvas" | "artifact") => void;
  onRun: () => void;
  running: boolean;
}) {
  const progress = progressWords(session);
  const waiting = session.phase === "failed" || session.turns.some((t) => t.state === "pending");

  return (
    <div className="flex flex-wrap items-baseline gap-4 px-6 pt-5 pb-4" data-testid="living-header">
      <h1 className="m-0 text-title font-semibold tracking-[-.03em] text-ink">
        {session.name || "Untitled analysis"}
      </h1>
      <span
        data-testid="mode"
        className="font-data text-[9.5px] tracking-[.12em] uppercase text-ink-2 px-2 py-[3px] border"
        style={{ borderColor: "var(--line-2)" }}
      >
        {session.mode}
      </span>
      <span className="font-data text-[11px] text-ink-3" data-testid="living-status">
        <span style={{ color: waiting ? "var(--measured)" : undefined }}>{phaseWords(session)}</span>
        {progress && <> · {progress}</>}
        {` · revision ${session.revision}`}
      </span>

      <div className="ml-auto flex items-center gap-4">
        <div className="flex border" style={{ borderColor: "var(--line-2)" }}>
          {(["canvas", "artifact"] as const).map((which) => (
            <button
              key={which}
              type="button"
              data-testid={`living-view-${which}`}
              aria-pressed={view === which}
              onClick={() => onView(which)}
              className={`font-data px-[15px] py-[7px] text-label uppercase tracking-[.09em] border-0
                          cursor-pointer ${view === which
                            ? "bg-[var(--link-soft)] text-link"
                            : "bg-transparent text-ink-3 hover:text-ink"}`}
            >
              {which}
            </button>
          ))}
        </div>
        <button
          type="button"
          data-testid="living-run"
          disabled={running || session.graph.nodes.length === 0 || session.phase !== "complete"}
          onClick={onRun}
          className="px-[26px] py-[9px] border-0 cursor-pointer font-semibold text-[13.5px]
                     bg-[var(--link)] text-paper disabled:cursor-not-allowed disabled:opacity-40"
        >
          Run
        </button>
      </div>
    </div>
  );
}
