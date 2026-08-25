import { useVirtualizer } from "@tanstack/react-virtual";
import { useMemo, useRef, useState } from "react";

import { Menu, copy, useContextMenu, type MenuItem } from "./Menu";
import { elapsed } from "./elapsed";
import type { RunEvent } from "./useRunStream";

/** What happened, in order. Built against `wiener-mockups/Main.dc.html`.
 *
 * **Only task events draw a row.** `started`, `completed` and `error` are the run's own
 * lifecycle and they are what the header already says — repeating them here as three lines
 * among four hundred is noise, and `error` carries nothing to show (§4.3 finding 1).
 */
const GLYPH: Record<string, string> = {
  COMPLETED: "✓", CACHED: "✓", FAILED: "✗", RUNNING: "●", SUBMITTED: "·", ABORTED: "✗",
};

/** One console line's height, in px. **The virtualiser and the row must agree**: the
 *  artboard sets `line-height: 1.95` on 11.5px text, and a virtualiser estimating anything
 *  else stacks the absolutely-positioned lines with gaps or overlaps. */
const LINE = 22;

const COLOUR: Record<string, string> = {
  COMPLETED: "var(--pea)", CACHED: "var(--ink-3)", FAILED: "var(--undecided)",
  RUNNING: "var(--measured)", SUBMITTED: "var(--ink-3)", ABORTED: "var(--undecided)",
};

/** One line, as text — the same thing the row draws, so a copy and a screenshot agree. */
/** What distinguishes this task from its siblings — and **only that**.
 *
 * Nextflow's `name` is `PROCESS (tag)`, so printing the process beside it read
 * `STAR_GENOMEGENERATE (STAR_GENOMEGENERATE (genome.fasta))` on every line. The old guard was
 * `name !== process`, which cannot catch it: the name is not equal to the process, it *contains*
 * it. The artboard's line is `STAR_ALIGN (sample_01)` — the process once, then what varies.
 *
 * A name that does not take that shape is returned whole rather than parsed into silence.
 */
function tagOf(trace: { process: string; name?: string }): string {
  const name = trace.name;
  if (!name || name === trace.process) return "";
  const inner = name.startsWith(`${trace.process} (`) && name.endsWith(")")
    ? name.slice(trace.process.length + 2, -1)
    : name;
  return inner === trace.process ? "" : inner;
}

function asText(event: RunEvent): string {
  const trace = event.trace;
  return [at(event.at_ms), trace?.status ?? event.kind, trace?.process ?? "",
          trace?.name ?? ""].filter(Boolean).join("  ");
}

function at(ms: number): string {
  return new Date(ms).toLocaleTimeString(undefined, { hour12: false });
}

/** What happened, in order — and **filtered to one process when you arrived from one**.
 *
 * That is §7's zoom-and-filter rung: opening the console from a process row should not mean
 * scrolling four hundred lines to find it again. `process` is a prop rather than local state
 * because the overview is what sets it.
 *
 * **Virtualised**, for the same reason the Tasks tab is: a 5,000-task run is 15,000 events,
 * and putting them all in the DOM is how a console that pages correctly still feels broken.
 */
export function Console({ events, following, process = "", onClearProcess, onFilter }: {
  events: RunEvent[]; following: boolean; process?: string;
  onClearProcess?: () => void;
  onFilter?: (process: string) => void;
}) {
  const menu = useContextMenu();
  const [line, setLine] = useState<RunEvent | null>(null);
  const [status, setStatus] = useState("");
  const control = "text-secondary bg-surface border border-line rounded-[var(--r)] px-2 py-1";

  // **Both lists come from the events in hand**, not from a constant. A status the run never
  // reported is a filter that can only ever empty the view, and a process list that outlives
  // the run it describes is the kind of thing that goes stale without anything failing.
  const seen = useMemo(
    () => [...new Set(events.map((e) => e.trace?.process).filter(Boolean) as string[])].sort(),
    [events],
  );
  const statuses = useMemo(
    () => [...new Set(events.map((e) => e.trace?.status).filter(Boolean) as string[])].sort(),
    [events],
  );

  const rows = useMemo(
    () => events.filter((event) => event.trace
      && (!process || event.trace.process === process)
      && (!status || event.trace.status === status)),
    [events, process, status],
  );
  const scroller = useRef<HTMLDivElement>(null);
  const virtual = useVirtualizer({
    count: rows.length,
    getScrollElement: () => scroller.current,
    estimateSize: () => LINE,
    overscan: 16,
    initialRect: { width: 1200, height: 600 },
  });

  /** §12.3's console-line menu. **`copy everything shown`, not everything** — a console
   *  filtered to STAR_ALIGN that copied all 412 lines would be lying about what you were
   *  looking at. */
  const itemsFor = (event: RunEvent): MenuItem[] => [
    { label: "Copy this line", onPick: () => void copy(asText(event)) },
    { label: "Copy the task's work directory", w4: true },
    { label: "Filter to this process",
      onPick: onFilter && event.trace ? () => onFilter(event.trace!.process) : undefined,
      separated: true },
    { label: "Show it in the overview", w4: true },
    { label: "Copy everything shown",
      onPick: () => void copy(rows.map(asText).join("\n")), separated: true },
  ];

  return (
    <div data-testid="console" className="flex flex-col">
      {/* **The way back out.** A console that arrived filtered and offers no way to widen is a
          view you can get stuck in — and the count below says `38 of 412`, so the reader can
          see there is something to widen to. */}
      {/* **`Console.dc.html`'s own caption is "zoom and filter, not tail -f"**, and the console
          shipped with neither control — which left it as tail -f. `process` and `status` are
          the artboard's two, and they use the Tasks tab's controls rather than a second
          spelling of the same thing. */}
      <div className="shrink-0 flex items-center gap-3 px-4 py-2 border-b border-line
                      bg-surface-2">
        <label className="flex items-center gap-1.5 text-label text-ink-3">
          process
          <select aria-label="process" className={control}
                  value={process} onChange={(e) => onFilter?.(e.target.value)}>
            <option value="">all</option>
            {seen.map((name) => <option key={name} value={name}>{name}</option>)}
          </select>
        </label>

        <label className="flex items-center gap-1.5 text-label text-ink-3">
          status
          <select aria-label="status" className={control}
                  value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">all</option>
            {statuses.map((name) => <option key={name} value={name}>{name}</option>)}
          </select>
        </label>

        {process && (
          <span className="flex items-baseline gap-2 text-label text-ink-3">
            filtered from the overview
            <button type="button" onClick={onClearProcess}
                    className="bg-transparent border-0 p-0 cursor-pointer text-ink-3
                               hover:text-ink underline">
              show everything
            </button>
          </span>
        )}
      </div>
      {/* **A console is flowing text, not a table.** Every line was a bordered grid row,
          which is what made it read as a spreadsheet of events rather than a log. The
          artboard is one `mono` block at `line-height:1.95`, no rules between lines, the
          duration floated right, and a failed line lifted out as a tinted block. */}
      <div ref={scroller}
           className="font-data text-secondary text-ink-2 max-h-[60dvh] overflow-y-auto
                      px-[18px] py-3.5">
       <ol style={{ height: virtual.getTotalSize(), position: "relative", margin: 0,
                    padding: 0, listStyle: "none" }}>
        {virtual.getVirtualItems().map((item) => {
          const event = rows[item.index];
          const trace = event.trace!;
          // **FAILED only, and ABORTED deliberately not.** Both draw a red `✗`, but only a
          // FAILED task is the cause — ABORTED is what Nextflow does to a task's siblings
          // once the run is already going down. Blocking every aborted line would turn one
          // failure into a wall of red and bury the line that explains it.
          // (Note that `wiener_core.overview` counts both in its `failed` tally, so a
          // process row can say "1 failed" for a line the console does not block.)
          const failed = trace.status === "FAILED";
          const tag = tagOf(trace);
          return (
            <li
              key={event.seq}
              data-testid={`event-${event.seq}`}
              {...menu.bind}
              onContextMenu={(e) => { setLine(event); menu.bind.onContextMenu(e); }}
              onKeyDown={(e) => { setLine(event); menu.bind.onKeyDown(e); }}
              style={{ position: "absolute", top: 0, left: 0, width: "100%",
                       height: LINE, lineHeight: `${LINE}px`,
                       transform: `translateY(${item.start}px)`,
                       // A failed line is a BLOCK: tinted, rounded, bled 8px into the gutter
                       // and struck with a 2px rule. The artboard's treatment, and what lets
                       // a failure be found by shape instead of by reading every line.
                       ...(failed
                         ? { background: "var(--undecided-soft)",
                             borderRadius: "var(--r)",
                             marginLeft: "-8px", paddingLeft: "8px", paddingRight: "8px",
                             width: "calc(100% + 16px)",
                             boxShadow: "inset 2px 0 0 var(--undecided)" }
                         : {}) }}
            >
              <time className="text-ink-3 tabular-nums">{at(event.at_ms)}</time>
              {"  "}
              <span className={trace.status === "RUNNING" ? "breathe" : undefined}
                    style={{ color: COLOUR[trace.status] ?? "var(--ink-3)" }}>
                {GLYPH[trace.status] ?? "\u00b7"}
              </span>
              {"  "}
              <span className={failed ? "text-[var(--undecided)]" : "text-ink"}>
                {trace.process}
              </span>
              {tag && <span className="text-ink-3"> ({tag})</span>}
              <span style={{ float: "right" }}
                    className={failed ? "text-[var(--undecided)]" : "text-ink-3"}>
                {trace.status === "RUNNING"
                  ? "running"
                  : trace.realtime_ms
                    ? elapsed(0, trace.realtime_ms, 0)
                    : "\u2014"}
              </span>
            </li>
          );
        })}
       </ol>
      </div>
      {menu.at && line && <Menu items={itemsFor(line)} at={menu.at} onClose={menu.close} />}

      {/* The end of the text, in the log's own voice and typeface — the artboard sets it
          below the last line rather than in a bordered bar, because it is where the log stops
          and not a summary of it. */}
      <p data-testid="event-count"
         className="font-data text-secondary text-ink-3 px-[18px] pb-3.5 pt-0 m-0">
        {/* **What is SHOWN, when a filter is on** — §12.3 makes the same point about copying:
            a console filtered to STAR_ALIGN that reported all 412 events would be lying about
            what you are looking at. */}
        {/* **`N of M` whenever anything is narrowing the view**, not only a process. The count
            read the process filter alone, so adding the status filter would have left the foot
            of a four-line console claiming fourteen events — a filter that lies about what it
            filtered. `[process, status]` is the list of things that hide a line; anything added
            to it belongs here too. */}
        — {[process, status].some(Boolean)
             ? `${rows.length} of ${events.length} events · ${[process, status]
                 .filter(Boolean).join(" · ")}`
             : `${events.length} ${events.length === 1 ? "event" : "events"}`} ·{" "}
        {following ? "tailing" : "not following"} —
      </p>
    </div>
  );
}
