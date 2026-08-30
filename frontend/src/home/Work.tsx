import { Link } from "react-router";

import type { components } from "../api/schema";
import type { components as wiener } from "../wiener/api/schema";

type DraftRow = components["schemas"]["DraftRow"];
type RunRow = wiener["schemas"]["RunRow"];

/** The Work block: one question at two depths, never two lists rendered twice.
 *
 * **The same table shape for both, with columns that differ by object** — `ov-work`. Cards for
 * one and a table for the other was the tell, and the actual bug underneath it was that RUN
 * information had leaked onto the PIPELINE cards (*"last run 2d ago · M. Silva"*). Two different
 * objects rendered as the same thing.
 *
 *   by pipeline — makes · provenance · runs · last outcome · owner   READINESS
 *   by run      — started by · when · outcome · took · results       HISTORY
 *
 * **By pipeline is the default**, because *what do we have and is any of it waiting on us* is
 * the question somebody opening the front door has. By-run is the follow-up.
 */

/** The artboards' `.lb`: mono, 9.5px, `.15em`, uppercase. It shipped at `.14em` in the UI face,
 *  which is the same idea drawn with the wrong tool — every label on every board is monospaced. */
const HEAD = "font-data text-[9.5px] uppercase tracking-[.15em] text-ink-3 font-normal "
  + "text-left py-2";
const CELL = "py-3 border-t border-line align-middle";

/** How Mendel decided, as one stacked bar per pipeline — a proportion of one whole.
 *
 * **One bar per PIPELINE, never one per value.** It is the only chart shape that earns a place
 * on a page with four rows, and `Provenance.tsx` on the builder draws the same idea from the
 * same numbers.
 *
 * **Four bands, and the artboard drew three.** A hand-drawn pipeline records every step as
 * `tier: 4, source: human` — a person chose it — so a fourth band is what stops four settled
 * choices being reported as four things needing attention. `drafts.Provenance` carries the
 * argument at length.
 */
function Bar({ of }: { of: DraftRow["provenance"] }) {
  // **Absent, not three empty segments.** A bar of zeroes claims a pipeline with nothing open,
  // which is the opposite of *nobody has looked*. A dash never means zero.
  if (!of) return <span className="text-ink-3">—</span>;

  const bands = [
    { n: of.settled, className: "bg-pea", what: "settled without judgement" },
    { n: of.by_person, className: "bg-pea opacity-[.45]", what: "answered by a person" },
    { n: of.by_model, className: "bg-running", what: "answered by a model" },
    { n: of.measured, className: "bg-measured", what: "measured" },
    { n: of.open, className: "bg-undecided", what: "waiting on a person" },
  ].filter((band) => band.n > 0);
  const total = bands.reduce((sum, band) => sum + band.n, 0);

  return (
    <span
      className="grow-x flex h-[7px] w-[120px] rounded-[1px] overflow-hidden bg-surface-2"
      title={bands.map((b) => `${b.n} ${b.what}`).join(" · ")}
    >
      {bands.map((band) => (
        <i key={band.what} className={band.className} style={{ width: `${band.n / total * 100}%` }} />
      ))}
    </span>
  );
}

export function ByPipeline({ rows, runs }: { rows: DraftRow[]; runs: RunRow[] }) {
  // **Joined in the browser on the pipeline digest**, which is why this component takes both.
  // `useSubmit.ts` was the only place in the product touching both halves; this is the second,
  // and it is deliberate that neither server knows the other exists (`wiener.md` §12).
  const outcome = new Map<string, RunRow>();
  for (const run of runs) {
    if (run.pipeline_digest && !outcome.has(run.pipeline_digest)) {
      outcome.set(run.pipeline_digest, run);
    }
  }
  const count = new Map<string, number>();
  for (const run of runs) {
    if (run.pipeline_digest) {
      count.set(run.pipeline_digest, (count.get(run.pipeline_digest) ?? 0) + 1);
    }
  }

  return (
    <div className="tbl">
      {/* **The artboard's column widths, and they were inverted.** `.pr` is
          `14px 156px 1fr 118px 74px 96px 78px` — the name is NARROW and *Makes* takes the
          slack, because the sentence describing what a pipeline produces is the long thing on
          the row. Auto layout gave the name 840px and squeezed the sentence, so the eye ran
          across a gap to reach the columns that matter. */}
      <table className="w-full border-collapse table-fixed min-w-[860px]">
        <colgroup>
          <col className="w-[28px]" />
          <col className="w-[170px]" />
          <col />
          <col className="w-[132px]" />
          <col className="w-[88px]" />
          <col className="w-[110px]" />
          <col className="w-[92px]" />
        </colgroup>
        <thead>
          <tr>
            {/* **The status dot is a column of its own**, 14px wide, and the table had none.
                The artboard leads every row with it — it is what lets somebody read *is any of
                this waiting on me* down a column instead of across six. */}
            <th className={HEAD} aria-label="state" />
            <th className={HEAD}>Pipeline</th>
            <th className={HEAD}>Makes</th>
            <th className={HEAD}>Settled · measured · open</th>
            <th className={`${HEAD} text-right`}>Runs</th>
            <th className={`${HEAD} text-right`}>Last outcome</th>
            <th className={`${HEAD} text-right`}>Owner</th>
          </tr>
        </thead>
        <tbody className="stagger">
          {rows.map((row) => {
            const last = row.digest ? outcome.get(row.digest) : undefined;
            const waiting = row.open_values.length + row.open_not_named;
            return (
              <tr key={row.id} className="settle">
                {/* Green when nothing is waiting, `--undecided` when something is. It reads the
                    same number the *last outcome* cell does, so the two can never disagree. */}
                <td className={CELL}>
                  <i aria-hidden className="block w-[7px] h-[7px] rounded-full"
                     style={{ background: waiting > 0 ? "var(--undecided)" : "var(--pea)" }} />
                </td>
                <td className={CELL}>
                  <Link to={`/build?draft=${row.id}`} className="text-ink no-underline lift
                                                                 inline-block px-1 -mx-1 rounded-r">
                    {row.name || row.id.slice(0, 8)}
                  </Link>
                </td>
                <td className={`${CELL} text-ink-2 font-data text-secondary`}>
                  {row.makes.length ? row.makes.join(", ") : <span className="text-ink-3">—</span>}
                </td>
                <td className={CELL}><Bar of={row.provenance} /></td>
                <td className={`${CELL} text-right tnum text-ink-2`}>
                  {row.digest ? (count.get(row.digest) ?? 0) : <span className="text-ink-3">—</span>}
                </td>
                <td className={`${CELL} text-right`}>
                  {/* **What needs a person outranks what a run did.** A pipeline you cannot run
                      has no useful last outcome, and saying `succeeded` beside two open values
                      reads as *ready*. */}
                  {waiting > 0 ? (
                    <span className="text-[var(--undecided)]">
                      {waiting} open
                    </span>
                  ) : last ? (
                    <span className={last.phase === "running" ? "text-running" : "text-ink-2"}>
                      {last.phase}
                    </span>
                  ) : (
                    <span className="text-ink-3">{row.kept ? "never run" : "not kept"}</span>
                  )}
                </td>
                <td className={`${CELL} text-right text-secondary text-ink-2`}>{row.who}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function ago(iso: string): string {
  const seconds = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (seconds < 90) return "just now";
  const minutes = seconds / 60;
  if (minutes < 90) return `${Math.round(minutes)}m ago`;
  const hours = minutes / 60;
  if (hours < 36) return `${Math.round(hours)}h ago`;
  return `${Math.round(hours / 24)}d ago`;
}

function took(run: RunRow): string {
  if (!run.ended_at) return "—";
  const ms = new Date(run.ended_at).getTime() - new Date(run.submitted_at).getTime();
  const minutes = Math.floor(ms / 60000);
  const seconds = Math.round((ms % 60000) / 1000);
  return minutes ? `${minutes}m ${seconds.toString().padStart(2, "0")}s` : `${seconds}s`;
}

export function ByRun({ runs, named }: { runs: RunRow[]; named: Map<string, string> }) {
  return (
    <div className="tbl">
      {/* **The artboard's column widths, and they were inverted.** `.pr` is
          `14px 156px 1fr 118px 74px 96px 78px` — the name is NARROW and *Makes* takes the
          slack, because the sentence describing what a pipeline produces is the long thing on
          the row. Auto layout gave the name 840px and squeezed the sentence, so the eye ran
          across a gap to reach the columns that matter. */}
      <table className="w-full border-collapse table-fixed min-w-[860px]">
        <colgroup>
          <col className="w-[28px]" />
          <col className="w-[170px]" />
          <col />
          <col className="w-[132px]" />
          <col className="w-[88px]" />
          <col className="w-[110px]" />
          <col className="w-[92px]" />
        </colgroup>
        <thead>
          <tr>
            {/* **The status dot is a column of its own**, 14px wide, and the table had none.
                The artboard leads every row with it — it is what lets somebody read *is any of
                this waiting on me* down a column instead of across six. */}
            <th className={HEAD} aria-label="state" />
            <th className={HEAD}>Pipeline</th>
            <th className={HEAD}>Started by</th>
            <th className={HEAD}>When</th>
            <th className={HEAD}>Outcome</th>
            <th className={`${HEAD} text-right w-[110px]`}>Took</th>
          </tr>
        </thead>
        <tbody className="stagger">
          {runs.map((run) => (
            <tr key={run.id} className="settle">
              <td className={CELL}>
                <Link to={`/runs/${run.id}`} className="text-ink no-underline lift
                                                        inline-block px-1 -mx-1 rounded-r">
                  {(run.pipeline_digest && named.get(run.pipeline_digest))
                    || <span className="text-ink-3">unknown pipeline</span>}
                </Link>
              </td>
              {/* **The person slot, and no `who` filter** — operator's decision 2026-08-30.
                  `submitted_by` is hardcoded "operator" at submit, so the value is a constant.
                  The column stays so accounts arrive as a filter rather than a re-layout, and
                  it renders as visibly not-yet-real; shipping a filter that filters nothing is
                  what `rn-board` and `ov-scope` both forbid. */}
              <td className={`${CELL} text-secondary text-ink-3`} title="attribution is not wired yet">
                {run.submitted_by}
              </td>
              <td className={`${CELL} text-secondary text-ink-2`}>{ago(run.submitted_at)}</td>
              <td className={CELL}>
                <span className={run.phase === "failed" ? "text-[var(--undecided)]"
                  : run.phase === "running" ? "text-running" : "text-ink-2"}>
                  {run.phase}
                </span>
                <span className="text-ink-3 text-secondary tnum">
                  {" · "}{run.tasks_done} of {run.tasks_seen} tasks
                </span>
              </td>
              <td className={`${CELL} text-right tnum text-ink-2`}>{took(run)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
