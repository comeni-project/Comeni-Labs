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

export function Console({ events, following }: { events: RunEvent[]; following: boolean }) {
  const rows = events.filter((event) => event.trace);

  return (
    <div data-testid="console" className="flex flex-col">
      <ol className="font-data text-secondary max-h-[60dvh] overflow-y-auto">
        {rows.map((event) => {
          const trace = event.trace!;
          return (
            <li
              key={event.seq}
              data-testid={`event-${event.seq}`}
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
      <p className="px-4 py-2 text-label text-ink-3 text-center border-t border-line">
        — {events.length} {events.length === 1 ? "event" : "events"} ·{" "}
        {following ? "tailing" : "not following"} —
      </p>
    </div>
  );
}
