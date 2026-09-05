import { Link } from "react-router";

import {
  useOverview,
  useSyncSources,
  type Overview as Counts,
  type SourceRow,
} from "../../api/registry";
import { useTitle } from "../../app/useTitle";
import { Failed, Loading } from "../../ui/States";
import { Mark, RegistrySection } from "./Status";

/** `/forge` — how complete and healthy is the registry, and what needs me now.
 *
 * **It counts and never lists.** `docs/design/forge-review.md` §3 records an Overview page
 * designed and *cut* for answering the same question as the queue, so the moment a tool ref or
 * an adaptation id appears here it has become the page that was cut. `forge_overview.py` holds
 * the same line on the server; this is the consumer half.
 *
 * **Every count is a link into a filtered view.** A number a person cannot follow is a number
 * they have to go and re-find by hand, which is how a dashboard becomes something people read
 * once and stop trusting. §8.1, and it is why nothing here is a bare figure.
 */

/** Four mutually exclusive parts of what is ADAPTABLE.
 *
 * **Unsupported is outside the denominator and stated beneath** — §8.1. A tool the forge cannot
 * adapt is not work outstanding, and counting it as *not adapted yet* makes a source look
 * permanently behind on work nobody can do.
 *
 * **`to` is a real server-side filter, one per segment.** Each is a `Freshness` value the
 * catalogue endpoint filters in SQL, so following a segment lands on exactly the rows it
 * counted — the check that a number and its destination agree is that they are computed from
 * one implementation, `CatalogueItem.freshness`.
 */
function segments(row: SourceRow) {
  const unadapted = Math.max(0, row.adaptable - row.current - row.outdated - row.in_progress);
  const to = (status: string) => `/forge/catalogue?source=${row.source}&status=${status}`;
  return [
    { n: row.current, tone: "var(--pea)", shape: "done" as const, label: "current",
      to: to("current") },
    { n: row.outdated, tone: "var(--measured)", shape: "review" as const, label: "outdated",
      to: to("outdated") },
    { n: row.in_progress, tone: "var(--running)", shape: "run" as const, label: "in progress",
      to: to("in_progress") },
    // **`--surface-2`, not the artboard's `#1C262B`.** The empty part of a bar is the recessed
    // ground behind it — the same role the runs board's track has — and a hex here is a colour
    // that does not move when the theme does. `tokens.test.ts` caught it.
    { n: unadapted, tone: "var(--surface-2)", shape: "open" as const, label: "not adapted",
      to: to("unadapted") },
  ];
}

/** The completeness bar. Segments are laid out by share of `adaptable`, so the four widths
 *  always sum to the whole and a source is legible without reading a single number. */
function Bar({ row }: { row: SourceRow }) {
  const total = Math.max(1, row.adaptable);
  return (
    <div className="flex gap-[2px] h-2.5">
      {segments(row).map((part) => (
        <div
          key={part.label}
          className="grow-x"
          title={`${part.label}: ${part.n}`}
          style={{ flex: `0 0 ${(part.n / total) * 100}%`, background: part.tone }}
        />
      ))}
    </div>
  );
}

function Source({ row }: { row: SourceRow }) {
  const parts = segments(row).slice(0, 3);
  const synced = row.last_synced_at ? new Date(row.last_synced_at) : null;

  return (
    <div
      className="settle border border-line bg-surface rounded-[var(--r)] shadow-e2
                 px-5 py-[18px]"
    >
      <div className="flex items-baseline justify-between pb-3">
        <span className="font-data text-[10.5px] tracking-[.15em] uppercase text-ink-2">
          {row.source}
        </span>
        {row.snapshot_stale ? (
          <span className="font-data text-[10.5px] text-measured">
            stale{synced ? ` · last read ${synced.toLocaleDateString()}` : " · never read"}
          </span>
        ) : (
          <span className="font-data text-[10.5px] text-ink-3">
            synced{" "}
            {synced?.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) ?? ""}
          </span>
        )}
      </div>

      <div className="flex items-baseline gap-2 pb-3">
        <span className="text-[30px] font-semibold tracking-[-.03em] leading-none tnum">
          {row.adapted.toLocaleString()}
        </span>
        <span className="text-body text-ink-2">of {row.adaptable.toLocaleString()} adaptable</span>
      </div>

      <Bar row={row} />

      {/* **Each segment's count is a link, not a legend.** §8.1: clicking a segment opens the
          catalogue filtered to it. A legend that only names colours makes the reader carry the
          number to another screen by hand — which is the step where a dashboard stops being
          used. The shape repeats beside the colour so identity is never colour alone. */}
      <div className="flex flex-wrap gap-3.5 pt-2.5 text-secondary text-ink-2">
        {parts.map((part) => (
          <Link
            key={part.label}
            to={part.to}
            className="inline-flex items-center gap-[5px] no-underline text-ink-2 hover:text-ink"
          >
            <Mark shape={part.shape} />
            <span className="tnum">{part.n.toLocaleString()}</span> {part.label}
          </Link>
        ))}
      </div>

      <div className="font-data text-[10.5px] text-ink-3 pt-2">
        <Link to={`/forge/catalogue?source=${row.source}`} className="text-ink-3 hover:text-ink">
          {row.discovered.toLocaleString()} discovered
        </Link>
        {row.unsupported > 0 && (
          <>
            {" · "}
            <Link
              to={`/forge/catalogue?source=${row.source}&status=unsupported`}
              className="text-ink-3 hover:text-ink"
            >
              {row.unsupported.toLocaleString()} unsupported
            </Link>
          </>
        )}
      </div>
    </div>
  );
}

/** The flow, as a left-to-right count graph — §8.1.
 *
 * **Not a Sankey and not five cards.** The AI node carries its capacity and its waiting tail,
 * because a single lane is only understandable when the queue behind it is visible; without
 * that number *1 active* reads as *the system is barely busy*.
 *
 * `Registry` is the terminal stage and it counts what has landed, which is the one figure here
 * that is history rather than work. It is on the graph because a flow whose last node is
 * `Review` never shows that anything finishes.
 */
function Flow({ data }: { data: Counts }) {
  const stages: { label: string; value: string; to: string; ai?: boolean; tail?: string }[] = [
    {
      label: "Discovered",
      value: data.sources.reduce((n, row) => n + row.discovered, 0).toLocaleString(),
      to: "/forge/catalogue",
    },
    {
      label: "Scaffold",
      value: String(data.stages.scaffolding),
      to: "/forge/work?band=ai",
    },
    {
      label: "AI lane",
      value: `${data.ai_lane.active} active`,
      to: "/forge/work?band=ai",
      ai: true,
      tail: `capacity ${data.ai_lane.concurrency} · ${data.ai_lane.waiting} waiting`,
    },
    { label: "Review", value: String(data.stages.review), to: "/forge/work?band=review" },
    {
      label: "Registry",
      value: data.sources.reduce((n, row) => n + row.adapted, 0).toLocaleString(),
      to: "/forge/catalogue?status=adapted",
    },
  ];

  return (
    <div className="pt-[30px]">
      <div className="font-data text-label tracking-[.15em] uppercase text-ink-3 pb-[13px]">
        The flow
      </div>
      {/* Scrolls inside itself rather than crushing its labels — `main.css`'s table rule, which
          is the only horizontal scrolling allowed anywhere in the product. */}
      <div className="overflow-x-auto">
        <div className="flex items-stretch min-w-[900px]">
          {stages.map((stage, i) => (
            <div key={stage.label} className="flex items-stretch">
              {/* **The edge has to be visible or the flow is five boxes.** It was drawn on the
                  artboard as a 1px line inside a `flex:1` gap and rendered as nothing at
                  1400px; a fixed width and an arrowhead are what make it read as a direction. */}
              {i > 0 && (
                <div className="flex-[0_0_46px] self-center flex items-center" aria-hidden="true">
                  <div className={`flex-1 h-px bg-[var(--port-line)] ${stage.ai ? "flow" : ""}`} />
                  <span
                    className="w-0 h-0 border-l-4 border-l-[var(--port-line)]
                               border-y-[3px] border-y-transparent"
                  />
                </div>
              )}
              <Link
                to={stage.to}
                className={`lift no-underline text-ink px-[15px] py-[11px] min-w-[118px]
                            bg-surface rounded-[var(--r)] border ${
                              stage.ai ? "border-running" : "border-line"
                            }`}
              >
                <div className="font-data text-label tracking-[.15em] uppercase text-ink-3 pb-1.5">
                  {stage.label}
                </div>
                <div className="text-[18px] font-semibold tracking-[-.02em] tnum">
                  {stage.value}
                </div>
                {stage.tail && (
                  <div className="font-data text-label text-ink-3 pt-[5px]">{stage.tail}</div>
                )}
              </Link>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

/** One line of *Needs you*: a count, what it is, and what happens when you go there. */
function Needs(props: { to: string; tone: string; count: number; what: string; note: string }) {
  return (
    <Link
      to={props.to}
      className="lift block no-underline text-ink pl-3.5 pr-3 py-[9px] mb-3 border-l-2"
      style={{ borderLeftColor: props.tone }}
    >
      <div className="text-[14px] font-medium">
        <span className="tnum">{props.count.toLocaleString()}</span> {props.what}
      </div>
      <div className="text-body text-ink-2 pt-[3px]">{props.note}</div>
    </Link>
  );
}

/** Whether each source's last look upstream worked, and the one action that answers a failure.
 *
 * **The stored code, never upstream's message** — `MI0104`, and the reason is on that entry.
 * The service already refuses to carry the provider's text; this renders what it does carry.
 */
function Health({ data }: { data: Counts }) {
  const sync = useSyncSources();
  return (
    <div className="border border-line bg-surface rounded-[var(--r)] shadow-e2 px-4 py-3.5">
      {data.sources.map((row) => (
        <div key={row.source} className="flex items-start gap-[9px] text-body pt-[11px] first:pt-0">
          <span className="mt-[5px]">
            <Mark shape={row.sync_error ? "fail" : row.snapshot_stale ? "review" : "done"} />
          </span>
          <span className="flex-1">
            {row.source} —{" "}
            {row.sync_error ? "last sync failed" : row.snapshot_stale ? "stale" : "synced"}
            {row.sync_error && (
              <span className="font-data block text-[10.5px] text-ink-3 pt-1">
                {row.sync_error}
              </span>
            )}
          </span>
          {(row.sync_error || row.snapshot_stale) && (
            <button
              type="button"
              className="border border-line-2 bg-transparent text-ink text-secondary px-3 py-1
                         rounded-[var(--r)] hover:bg-surface-2"
              onClick={() => sync.mutate(row.source)}
              disabled={sync.isPending}
            >
              Retry
            </button>
          )}
        </div>
      ))}
      {sync.error && (
        <div className="pt-3">
          <Failed error={sync.error} padded={false} />
        </div>
      )}
    </div>
  );
}

export function Overview() {
  useTitle("Registry");
  const { data, isPending, error } = useOverview();
  const sync = useSyncSources();

  return (
    <RegistrySection>
      <div className="gutter pb-10 overflow-y-auto">
        <div className="settle flex items-end justify-between pt-[26px] pb-[22px]">
          <div>
            <h1 className="text-title font-semibold tracking-[-.03em] m-0 leading-none">
              Registry
            </h1>
            <p className="text-body text-ink-2 m-0 pt-[5px]">
              Keep the tool catalogue supplied and current.
            </p>
          </div>
          <button
            type="button"
            className="border border-line-2 bg-transparent text-ink text-[12px] px-3.5 py-[7px]
                       rounded-[var(--r)] hover:bg-surface disabled:text-ink-3
                       disabled:border-line disabled:cursor-not-allowed"
            onClick={() => data?.sources.forEach((row) => sync.mutate(row.source))}
            disabled={sync.isPending || !data?.sources.length}
          >
            {sync.isPending ? "Syncing…" : "Sync sources"}
          </button>
        </div>

        {isPending && <Loading what="the registry" />}
        {error && <Failed error={error} />}

        {data && (
          <>
            {/* **An empty registry says what to do, not that it is empty.** Nothing synced yet
                is a first-run state, and the action that ends it is the button above — so this
                names that action rather than describing an absence. */}
            {data.sources.length === 0 ? (
              <div className="border border-line bg-surface rounded-[var(--r)] p-6">
                <p className="text-body text-ink m-0">No source has been read yet.</p>
                <p className="text-secondary text-ink-3 m-0 pt-1">
                  Sync a source to discover what can be adapted. Nothing else on this page can
                  say anything until one has been read.
                </p>
              </div>
            ) : (
              <div className="grid gap-5 grid-cols-1 min-[1180px]:grid-cols-2">
                {data.sources.map((row) => (
                  <Source key={row.source} row={row} />
                ))}
              </div>
            )}

            <Flow data={data} />

            <div className="grid gap-5 pt-[30px] grid-cols-1 min-[1180px]:grid-cols-2">
              <div>
                <div className="font-data text-label tracking-[.15em] uppercase text-ink-3 pb-[13px]">
                  Needs you
                </div>
                <Needs
                  to="/forge/work?band=review"
                  tone="var(--measured)"
                  count={data.stages.review}
                  what="ready for review"
                  note={
                    data.attention.stale_review_count > 0
                      ? `${data.attention.stale_review_count} have waited more than three days.`
                      : "Waiting on a person — nothing moves until somebody reads them."
                  }
                />
                <Needs
                  to="/forge/work?band=failed"
                  tone="var(--fault)"
                  count={data.attention.failed_adaptations}
                  what="failed"
                  note="Each retries at the stage it stopped, not from the beginning."
                />
                <Needs
                  to="/forge/catalogue?status=outdated"
                  tone="var(--line-2)"
                  count={data.attention.outdated_count}
                  what="tools outdated"
                  note="Upstream moved since these were adapted."
                />
              </div>

              <div>
                <div className="font-data text-label tracking-[.15em] uppercase text-ink-3 pb-[13px]">
                  Source health
                </div>
                <Health data={data} />
                {/* **No tokens and no cost anywhere on this page.** §8.1: those are operational
                    diagnostics rather than whether the registry is useful, and leading with them
                    teaches a person to read the front door as a bill. */}
              </div>
            </div>
          </>
        )}
      </div>
    </RegistrySection>
  );
}
