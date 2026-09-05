import { useState } from "react";
import { Link } from "react-router";

import {
  useAdaptations,
  useRetryAdaptation,
  type AdaptationRow,
  type AdaptationState,
} from "../../api/registry";
import { useTitle } from "../../app/useTitle";
import { useUrlState } from "../../app/useUrlState";
import { Failed, Loading } from "../../ui/States";
import { LOOK, Mark, Subnav } from "./Status";

/** `/forge/work` — everything in flight, in the order somebody would act on it.
 *
 * **Bands, not one table sorted by date.** The four things a curator does here are different
 * jobs: watch the lane, review a candidate, answer a change request, retry a failure. A single
 * list ordered by `updated_at` interleaves them, so the two adaptations waiting on a human sit
 * between six the machine is still working on.
 *
 * **The AI lane is drawn as one slot with a tail.** Capacity is one, and a queue that did not
 * show the tail would make *1 active* read as *the system is idle* — the number that answers
 * "when will mine start" is the position, and it only exists as a picture of the whole lane.
 */

/** The bands, and what each one is for.
 *
 * `state` is what the server filters on; `band` is the URL's word for it, because a person
 * choosing *Needs review* is choosing a job rather than a state name — and two of these cover
 * more than one state.
 */
const BANDS: Record<string, { label: string; states: AdaptationState[] }> = {
  ai: { label: "AI work", states: ["scaffolding", "queued", "generating", "validating"] },
  review: { label: "Needs review", states: ["review", "changes_requested"] },
  failed: { label: "Failed", states: ["failed"] },
};

const ORDER = ["ai", "review", "failed"] as const;

function bandOf(state: AdaptationState): string | null {
  for (const [key, band] of Object.entries(BANDS)) {
    if (band.states.includes(state)) return key;
  }
  return null;
}

/** How long ago, in the coarsest unit that is still true.
 *
 * **No seconds.** A queue polled every two seconds that counted in seconds would redraw every
 * row on every tick, and the difference between 41s and 43s answers nothing a curator asked.
 */
function since(iso: string): string {
  const ms = Date.now() - new Date(iso).getTime();
  const minutes = Math.round(ms / 60_000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.round(minutes / 60);
  if (hours < 48) return `${hours}h`;
  return `${Math.round(hours / 24)}d`;
}

function Row({ row, children }: { row: AdaptationRow; children?: React.ReactNode }) {
  return (
    <div
      className="lift flex items-center gap-3 py-[11px] border-b border-line-soft"
      data-testid="work-row"
    >
      <Mark shape={LOOK[row.state].shape} />
      <Link
        to={`/forge/adaptations/${row.id}`}
        className="text-body font-medium no-underline text-ink hover:text-link min-w-[210px]"
      >
        {row.display_name || row.ref}
      </Link>
      <span className="font-data text-[10.5px] text-ink-3 min-w-[92px]">{row.source}</span>
      <span className="flex-1 font-data text-[11px] text-ink-3">
        {LOOK[row.state].label} · {since(row.updated_at)}
      </span>
      {children}
      <Link
        to={`/forge/adaptations/${row.id}`}
        className="font-data text-label tracking-[.08em] uppercase no-underline text-ink
                   border border-line-2 rounded-[var(--r)] px-[11px] py-[5px] hover:bg-surface"
      >
        Open
      </Link>
    </div>
  );
}

/** The lane: the one slot, and everything queued behind it drawn as a tail.
 *
 * **`queued` rows carry a position and the word `approximate`.** The worker takes whatever ARQ
 * hands it, so a position derived from `updated_at` is a good guess and not a promise —
 * printing it bare would be inventing an ordering guarantee the queue does not make.
 */
function Lane({ rows }: { rows: AdaptationRow[] }) {
  const held = rows.filter((row) => row.state !== "queued");
  const waiting = rows.filter((row) => row.state === "queued");

  if (rows.length === 0) {
    return (
      <div className="border border-line bg-surface rounded-[var(--r)] px-4 py-3.5">
        <p className="text-body text-ink-2 m-0">The lane is idle.</p>
        <p className="text-secondary text-ink-3 m-0 pt-1">
          Nothing is being scaffolded or generated. Start one from the catalogue.
        </p>
      </div>
    );
  }

  return (
    <>
      {held.map((row) => (
        <div
          key={row.id}
          className="border border-running bg-surface rounded-[var(--r)] px-4 py-[13px]
                     flex items-center gap-3"
        >
          <Mark shape="run" />
          <Link
            to={`/forge/adaptations/${row.id}`}
            className="text-[13.5px] font-medium no-underline text-ink hover:text-link"
          >
            {row.display_name || row.ref}
          </Link>
          <span className="text-body text-ink-2 flex-1">{LOOK[row.state].label}</span>
          <span className="font-data text-[11.5px] text-running">
            {since(row.updated_at)}
            <span className="blink">▮</span>
          </span>
        </div>
      ))}

      {waiting.length > 0 && (
        <>
          <div className="h-2.5 ml-1 border-l border-line-2" aria-hidden="true" />
          {waiting.map((row, i) => (
            <div
              key={row.id}
              className="flex items-center gap-[13px] py-[9px] pl-[25px] ml-1 border-l border-line-2"
            >
              <Mark shape="open" />
              <Link
                to={`/forge/adaptations/${row.id}`}
                className="text-body flex-1 no-underline text-ink hover:text-link"
              >
                {row.display_name || row.ref}
              </Link>
              <span className="font-data text-[10.5px] text-ink-3">
                position {i + 1 + held.length} · approximate
              </span>
            </div>
          ))}
        </>
      )}
    </>
  );
}

/** Retry, with the reason the API requires — asked for rather than invented.
 *
 * **The endpoint takes a reason and this could have sent a constant.** It does not: a retry
 * writes an event that a person reads six months later, and "retried from the work queue"
 * answers nothing that the timestamp beside it did not.
 */
function Retry({ row }: { row: AdaptationRow }) {
  const retry = useRetryAdaptation();
  const [open, setOpen] = useState(false);
  const [why, setWhy] = useState("");

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="font-data text-label tracking-[.08em] uppercase border border-line-2
                   rounded-[var(--r)] px-[11px] py-[5px] bg-transparent text-ink hover:bg-surface"
      >
        Retry
      </button>
    );
  }
  return (
    <span className="flex items-center gap-2">
      <input
        autoFocus
        value={why}
        onChange={(event) => setWhy(event.target.value)}
        placeholder="Why retry?"
        aria-label={`Why retry ${row.display_name}`}
        className="border border-line-2 bg-surface text-ink text-secondary rounded-[var(--r)]
                   px-2.5 py-1 w-[210px] focus-visible:outline-none
                   focus-visible:shadow-[var(--ring)]"
      />
      <button
        type="button"
        disabled={!why.trim() || retry.isPending}
        onClick={() =>
          retry.mutate(
            { id: row.id, reason: why.trim() },
            { onSuccess: () => setOpen(false) },
          )
        }
        className="font-data text-label tracking-[.08em] uppercase border border-pea text-pea
                   rounded-[var(--r)] px-[11px] py-[5px] bg-transparent hover:bg-pea-soft
                   disabled:border-line disabled:text-ink-3 disabled:cursor-not-allowed"
      >
        Go
      </button>
    </span>
  );
}

function Band({
  label,
  rows,
  empty,
  children,
}: {
  label: string;
  rows: AdaptationRow[];
  empty: string;
  children?: (row: AdaptationRow) => React.ReactNode;
}) {
  return (
    <section className="pb-[26px]">
      <div className="font-data text-label tracking-[.15em] uppercase text-ink-3 pb-[11px]">
        {label} ({rows.length})
      </div>
      {rows.length === 0 ? (
        /* **An empty band renders and says what it means.** Dropping it would leave a reader
           unable to tell a band with nothing in it from a band that failed to load — the same
           distinction `main.css`'s layout rules make about a tile that does not fit. */
        <p className="text-body text-ink-3 m-0">{empty}</p>
      ) : (
        <div>
          {rows.map((row) => (
            <Row key={row.id} row={row}>
              {children?.(row)}
            </Row>
          ))}
        </div>
      )}
    </section>
  );
}

export function Work() {
  useTitle("Work queue");
  const [band, setBand] = useUrlState("band", "");
  const [source] = useUrlState("source", "");
  const [state] = useUrlState("state", "");

  // **One request for every band, filtered here.** The queue is what is *in flight* — tens of
  // rows, not thousands — so four filtered requests would be four round trips answering one
  // question, and their four snapshots could disagree about a row that moved between them.
  const { data, isPending, error } = useAdaptations({ source: source || undefined });
  const rows = data?.items ?? [];

  const shown = rows.filter((row) => {
    if (state) return row.state === state;
    if (!band) return true;
    return bandOf(row.state) === band;
  });

  const of = (key: string) =>
    shown.filter((row) => bandOf(row.state) === key);

  return (
    <>
      <Subnav />
      <div className="gutter pb-10 overflow-y-auto">
        <div className="settle flex items-center justify-between pt-[26px] pb-5">
          <h1 className="text-[22px] font-semibold tracking-[-.025em] m-0">Work queue</h1>
          <div className="flex gap-0.5">
            {[["", "All"], ...ORDER.map((key) => [key, BANDS[key].label])].map(([key, label]) => (
              <button
                key={key || "all"}
                type="button"
                aria-current={band === key}
                onClick={() => setBand(key)}
                className={`font-data text-label tracking-[.08em] uppercase px-[13px] py-1.5
                            border-0 ${
                              band === key ? "bg-surface text-ink" : "bg-transparent text-ink-3 hover:text-ink"
                            }`}
              >
                {label}
              </button>
            ))}
          </div>
        </div>

        {isPending && <Loading what="the work queue" />}
        {error && <Failed error={error} />}

        {data && (
          <>
            {(!band || band === "ai") && (
              <div className="pb-[26px]">
                <div className="flex items-baseline gap-3 pb-3">
                  <span className="font-data text-label tracking-[.15em] uppercase text-ink-3">
                    AI lane
                  </span>
                  <span className="font-data text-[10.5px] text-ink-3">capacity 1</span>
                </div>
                <Lane rows={of("ai")} />
              </div>
            )}

            {(!band || band === "review") && (
              <>
                <Band
                  label="Ready for review"
                  rows={shown.filter((row) => row.state === "review")}
                  empty="Nothing is waiting on a person."
                />
                <Band
                  label="Changes requested"
                  rows={shown.filter((row) => row.state === "changes_requested")}
                  empty="No candidate has been sent back."
                />
              </>
            )}

            {(!band || band === "failed") && (
              <Band
                label="Failed"
                rows={shown.filter((row) => row.state === "failed")}
                empty="Nothing has failed."
              >
                {(row) => <Retry row={row} />}
              </Band>
            )}

            {/* **A `state=` link from the overview shows exactly that state**, and the bands
                above cover only what a person acts on. Anything else — published, archived,
                publishing — lands here rather than in an empty page. */}
            {state && !bandOf(state as AdaptationState) && (
              <Band
                label={LOOK[state as AdaptationState]?.label ?? state}
                rows={shown}
                empty="Nothing is in this state."
              />
            )}

            {shown.length === 0 && !state && (
              <p className="text-body text-ink-3">
                Nothing is in flight. The catalogue is where work starts.
              </p>
            )}

            {data.next_cursor && (
              /* **Honest about the cut rather than paging here.** The queue is meant to be
                 short; a next page means something is wrong upstream, and saying so is more
                 use than a button that walks a list nobody should have. */
              <p className="font-data text-[10.5px] text-ink-3">
                More than {rows.length} adaptations are in flight — the oldest are not shown.
              </p>
            )}
          </>
        )}
      </div>
    </>
  );
}
