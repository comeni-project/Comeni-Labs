import { useVirtualizer } from "@tanstack/react-virtual";
import { useMemo, useRef } from "react";

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

const COLOUR: Record<string, string> = {
  COMPLETED: "var(--pea)", CACHED: "var(--ink-3)", FAILED: "var(--undecided)",
  RUNNING: "var(--measured)", SUBMITTED: "var(--ink-3)", ABORTED: "var(--undecided)",
};

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
export function Console({ events, following, process = "" }: {
  events: RunEvent[]; following: boolean; process?: string;
}) {
  const rows = useMemo(
    () => events.filter((event) => event.trace && (!process || event.trace.process === process)),
    [events, process],
  );
  const scroller = useRef<HTMLDivElement>(null);
  const virtual = useVirtualizer({
    count: rows.length,
    getScrollElement: () => scroller.current,
    estimateSize: () => 25,
    overscan: 16,
    initialRect: { width: 1200, height: 600 },
  });

  return (
    <div data-testid="console" className="flex flex-col">
      <div ref={scroller} className="font-data text-secondary max-h-[60dvh] overflow-y-auto">
       <ol style={{ height: virtual.getTotalSize(), position: "relative", margin: 0,
                    padding: 0, listStyle: "none" }}>
        {virtual.getVirtualItems().map((item) => {
          const event = rows[item.index];
          const trace = event.trace!;
          return (
            <li
              key={event.seq}
              data-testid={`event-${event.seq}`}
              style={{ position: "absolute", top: 0, left: 0, width: "100%",
                       transform: `translateY(${item.start}px)` }}
              className="grid grid-cols-[auto_auto_1fr_auto] items-baseline gap-3 px-4 py-1
                         border-b border-line last:border-b-0"
            >
              <time className="text-ink-3 tabular-nums">{at(event.at_ms)}</time>
              <span style={{ color: COLOUR[trace.status] ?? "var(--ink-3)" }}>
                {GLYPH[trace.status] ?? "·"}
              </span>
              <span className="text-ink">
                {trace.process}
                {trace.name && trace.name !== trace.process && (
                  <span className="text-ink-3"> ({trace.name})</span>
                )}
              </span>
              <span className="text-ink-3 tabular-nums">
                {trace.status === "RUNNING"
                  ? "running"
                  : trace.realtime_ms
                    ? elapsed(0, trace.realtime_ms, 0)
                    : "—"}
              </span>
            </li>
          );
        })}
       </ol>
      </div>
      <p data-testid="event-count"
         className="px-4 py-2 text-label text-ink-3 text-center border-t border-line">
        {/* **What is SHOWN, when a filter is on** — §12.3 makes the same point about copying:
            a console filtered to STAR_ALIGN that reported all 412 events would be lying about
            what you are looking at. */}
        — {process
             ? `${rows.length} of ${events.length} events · ${process}`
             : `${events.length} ${events.length === 1 ? "event" : "events"}`} ·{" "}
        {following ? "tailing" : "not following"} —
      </p>
    </div>
  );
}
