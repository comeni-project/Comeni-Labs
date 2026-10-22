import { useState } from "react";

import type { AuthoringSession } from "../../api/types";
import { CallPanel } from "./CallPanel";
import { phaseWords, stepWords, usageWords } from "./format";

/** The page's one strip: the pipeline's name, its mode, where it is, the view toggle, and Run.
 *
 * **One strip and no tabs beneath it.** The builder that ships stacks four bands of chrome above
 * the first sentence anybody wants to read; this has the name at the size of what the page is
 * about, the status line beside it, and nothing between that and the work.
 */
type Tone = "now" | "done" | "needs-you";

/** A chip's colours by meaning: its words in the `-ink`, on the `-soft`. */
const TONE: Record<Tone, React.CSSProperties> = {
  now: { background: "var(--now-soft)", color: "var(--now-ink)" },
  done: { background: "var(--done-soft)", color: "var(--done-ink)" },
  "needs-you": { background: "var(--needs-you-soft)", color: "var(--needs-you-ink)" },
};

/** **Where the build is, as the boards' chip**: the phase in its words, and the step being
 *  offered. *Complete* in the done colour — never *Valid*, which only the gate can say. Amber means
 *  *measured*, so a reply in flight is *now*; a failed call that needs a retry, and a stop, need
 *  the person. Drawn in the header, and on the describe page, which has no header. */
export function StatusChip({ session, open = 0 }: { session: AuthoringSession; open?: number }) {
  const active = session.progress?.active ?? null;
  // **Complete only when nothing needs you** (issue 385): every step added with a value still open is
  // *built*, in the now colour, beside the chip that says what is open.
  const built = session.phase === "complete" && open > 0;
  const tone: Tone = session.phase === "stopped" || session.phase === "failed" ? "needs-you"
    : session.phase === "complete" && !built ? "done" : "now";
  return (
    <span data-testid="living-status" data-tone={tone}
          className="self-center px-[8px] py-[3px] rounded-control text-[12px] font-semibold first-letter:capitalize"
          style={TONE[tone]}>
      {built ? "built" : phaseWords(session)}{active && session.phase === "building" ? ` · ${stepWords(active).toLowerCase()}` : ""}
    </span>
  );
}

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
  onRename,
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
  /** Rename the pipeline: the name becomes a field, saved when it loses focus. */
  onRename?: (name: string) => void;
}) {
  const spent = usageWords(session.usage);
  const [calls, setCalls] = useState(false);
  // **Locked while a value needs you** (issue 385); an optional open value does not count (issue 384).
  const ready = runnable && !running && session.graph.nodes.length > 0 && session.phase === "complete"
    && openValues === 0;


  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-2 px-[28px] pt-[22px] pb-[14px]" data-testid="living-header">
      <h1 className="m-0 text-[25px] leading-tight font-semibold tracking-[-.02em] text-ink">
        {onRename ? (
          <input aria-label="pipeline name" defaultValue={session.name} placeholder="Untitled analysis"
                 key={session.name}
                 onBlur={(e) => {
                   const name = e.target.value.trim();
                   if (name !== session.name) onRename(name);
                 }}
                 onKeyDown={(e) => { if (e.key === "Enter") e.currentTarget.blur(); }}
                 className="m-0 p-0 border-0 bg-transparent text-[25px] leading-tight font-semibold
                            tracking-[-.02em] text-ink placeholder:text-ink-3 focus-visible:outline-none
                            focus-visible:shadow-[var(--ring)] rounded-control"
                 style={{ width: `${Math.max(12, (session.name || "Untitled analysis").length + 1)}ch` }} />
        ) : (session.name || "Untitled analysis")}
      </h1>
      {/* Where the build is, then what it needs from you — the boards' order. */}
      <StatusChip session={session} open={openValues} />
      {openValues > 0 && (
        <span data-testid="needs-you-chip"
              className="self-center px-[8px] py-[2px] rounded-control text-[12px] font-semibold text-needs-you-ink"
              style={{ background: "var(--needs-you-soft)" }}>
          {openValues} {openValues === 1 ? "value needs you" : "values need you"}
        </span>
      )}
      {session.projection_current === false && (
        <span className="self-center px-[8px] py-[3px] rounded-control text-[12px] font-semibold"
              style={TONE["needs-you"]}>
          Pipeline outdated
        </span>
      )}
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
          disabled={!ready}
          onClick={onRun}
          className={`px-[22px] py-[9px] rounded-button font-semibold text-[13.5px] ${ready
            ? "border-0 cursor-pointer bg-action text-on-action shadow-raise"
            : "border-0 text-ink-2 cursor-not-allowed"}`}
          style={ready ? undefined : { background: "var(--line-soft)" }}
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
