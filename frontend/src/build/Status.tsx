import { Failed } from "../ui/States";

/** `saved 4s ago · valid · 2 values need you` — three facts, derived, and silent when clean.
 *
 * ═══ IT REPLACES `Walk.tsx`, AND KEEPS THE ONE THING WALK GOT RIGHT ═══════════════════════
 *
 * Draw → Keep → Gate → Run was four steps in a rail, and the four verbs **still happen** — they
 * stop being UI. `impl-walk`: `Run` is keep → lint → open the run sheet → submit → navigate.
 *
 * **Every fact reads the world, never a counter.** That is the property `Walk` had and the
 * reason it was worth keeping: a rail that advances an index tells you where the *interface*
 * thinks you are, and this tells you what is true — so editing after keeping moves it
 * **backwards**, which is the honest answer and the one a counter cannot give.
 *
 * **It says nothing when nothing is wrong.** Absence is absence here as everywhere else on this
 * product: a status line that always has three things to say is a status line nobody reads.
 *
 * ═══ THE ERROR IS REQUIRED, NOT OPTIONAL ══════════════════════════════════════════════════
 *
 * Phase 0 made `Walk`'s error prop required and `tsc` immediately named three call sites in
 * `Builder.tsx` that had dropped it — including the one behind the 2026-08-29 walk's worst
 * defect, where *Keep* answered 500 and the rail sat there unchanged. Whatever replaces `Walk`
 * inherits that: a required field, so forgetting it is a compile error rather than a silence.
 */
export function Status({ savedAt, saving, dirty, error, valid, open, stale }: {
  savedAt: Date | null;
  saving: boolean;
  /** Whether there are unsaved changes. Read from `useGraph`, which clears it only on a
   *  successful write — so a failed save leaves this true and the work pending. */
  dirty: boolean;
  /** What went wrong saving, or `null`. **Required.** */
  error: string | null;
  /** Whether the verdict currently holds. `null` before the first one arrives. */
  valid: boolean | null;
  /** How many values nobody has answered. */
  open: number;
  /** Whether the verdict is being recomputed — the graph has moved and this describes the one
   *  before it. */
  stale: boolean;
}) {
  // **The failure comes first and replaces the rest.** A line reading `saved 4s ago · valid`
  // beside a save that just failed is worse than no line: it is the same lie the rail told.
  if (error) {
    return (
      <span data-testid="status-error" className="text-secondary">
        <Failed error={error} padded={false} />
      </span>
    );
  }

  const parts: { key: string; node: React.ReactNode }[] = [];

  if (saving) {
    parts.push({ key: "saving", node: <span className="text-ink-3">saving…</span> });
  } else if (dirty) {
    // Not "unsaved" as an alarm — it is the ordinary state five seconds out of every six.
    parts.push({ key: "dirty", node: <span className="text-ink-3">unsaved</span> });
  } else if (savedAt) {
    parts.push({
      key: "saved",
      node: <span className="text-ink-3">saved {ago(savedAt)}</span>,
    });
  }

  if (stale) {
    // **The verdict lags the graph by 2–3s and used to say nothing.** Mid-edit it read
    // `UNMET MD0506 star_align.index` while `star_align` had already been deleted — describing
    // a graph that no longer existed, with nothing marking it.
    parts.push({ key: "stale", node: <span className="text-ink-3">checking…</span> });
  } else if (valid === false) {
    parts.push({ key: "invalid", node: <span className="text-[var(--undecided)]">not valid</span> });
  } else if (valid === true) {
    parts.push({ key: "valid", node: <span className="text-pea">valid</span> });
  }

  if (open > 0) {
    parts.push({
      key: "open",
      node: (
        <span className="text-[var(--undecided)]">
          {open} value{open === 1 ? "" : "s"} need{open === 1 ? "s" : ""} you
        </span>
      ),
    });
  }

  if (parts.length === 0) return null;

  return (
    <span data-testid="status" className="text-secondary flex items-center gap-2 tnum">
      {parts.map((part, n) => (
        <span key={part.key} className="flex items-center gap-2">
          {n > 0 && <span aria-hidden className="text-ink-3">·</span>}
          {part.node}
        </span>
      ))}
    </span>
  );
}

/** Coarse on purpose. A status line that counts seconds is a status line that re-renders every
 *  second, and the number nobody needs to that precision. */
function ago(when: Date): string {
  const seconds = Math.max(0, Math.round((Date.now() - when.getTime()) / 1000));
  if (seconds < 10) return "just now";
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  return `${Math.round(minutes / 60)}h ago`;
}
