import { Link } from "react-router";

import type { components } from "../api/schema";
import type { components as wiener } from "../wiener/api/schema";
import { DeleteDraft } from "./DeleteDraft";
import { pipelineAddress } from "../build/address";

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

/** A column head: a label in the interface face, `--ink-3`. */
const HEAD = "text-label text-ink-3 font-normal "
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
    { n: of.settled, className: "bg-line-2", what: "settled without judgement" },
    { n: of.by_person, className: "bg-ink-3", what: "answered by a person" },
    { n: of.by_model, className: "bg-measured opacity-[.55]", what: "answered by a model" },
    { n: of.measured, className: "bg-measured", what: "measured" },
    { n: of.open, className: "bg-needs-you", what: "waiting on a person" },
  ].filter((band) => band.n > 0);
  const total = bands.reduce((sum, band) => sum + band.n, 0);

  return (
    <span
      className="grow-x flex h-[7px] w-[120px] rounded-xs overflow-hidden bg-surface-2"
      title={bands.map((b) => `${b.n} ${b.what}`).join(" · ")}
    >
      {bands.map((band) => (
        <i key={band.what} className={band.className} style={{ width: `${band.n / total * 100}%` }} />
      ))}
    </span>
  );
}

/** The bar in words: tiers 1–2 settled, tier 3 measured, tier 4 open, and who answered the rest. */
function decidedWords(of: NonNullable<DraftRow["provenance"]>): string {
  return [
    `${of.settled} settled`, `${of.measured} measured`, `${of.open} open`,
    of.optional > 0 && `${of.optional} optional`,
    of.by_person > 0 && `${of.by_person} answered by you`,
    of.by_model > 0 && `${of.by_model} answered by a model`,
  ].filter(Boolean).join(" · ");
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
      <table className="w-full border-collapse table-fixed" style={{ minWidth: 720 }}>
        <colgroup>
          <col className="w-[28px]" />
          <col />
          <col className="w-[230px]" />
          <col className="w-[64px]" />
          <col className="w-[120px]" />
          <col className="w-[92px]" />
        </colgroup>
        <thead>
          <tr>
            {/* **The status dot is a column of its own** — it is what lets somebody read *is any
                of this waiting on me* down a column instead of across five. No owner column: the
                MVP has no labs, so there is nobody else's pipeline (#378). */}
            <th className={HEAD} aria-label="state" />
            <th className={HEAD}>Pipeline</th>
            <th className={HEAD}>How it was decided</th>
            <th className={`${HEAD} text-right`}>Runs</th>
            <th className={`${HEAD} text-right`}>Last outcome</th>
            <th className={HEAD} aria-label="actions" />
          </tr>
        </thead>
        <tbody className="stagger">
          {rows.map((row) => {
            const last = row.digest ? outcome.get(row.digest) : undefined;
            const waiting = row.open_values.length + row.open_not_named;
            return (
              <tr key={row.id} className="settle">
                {/* Green when nothing is waiting, `--needs-you` when something is. It reads the
                    same number the *last outcome* cell does, so the two can never disagree. */}
                <td className={CELL}>
                  <i aria-hidden className="block w-[7px] h-[7px] rounded-full"
                     style={{ background: waiting > 0 ? "var(--needs-you)" : "var(--done)" }} />
                </td>
                <td className={CELL}>
                  <Link to={pipelineAddress(row)} className="text-ink no-underline lift
                                                                 inline-block px-1 -mx-1 rounded-button">
                    {row.name || row.id.slice(0, 8)}
                  </Link>
                  {/* The outputs and the bar describe the kept artifact; an edit since has left
                      them behind (issue 277). */}
                  {row.changed_since_kept && (
                    <span className="ml-2 text-secondary text-ink-3">changed since kept</span>
                  )}
                  {/* What it makes and how big it is, under its name, as the boards set it. */}
                  <span className="block mt-[2px] text-[12.5px] text-ink-2">
                    {row.makes.length ? <span className="font-data">{row.makes.join(", ")}</span> : "makes nothing yet"}
                    {` · ${row.steps} ${row.steps === 1 ? "step" : "steps"}`}
                  </span>
                </td>
                <td className={CELL}>
                  <Bar of={row.provenance} />
                  {row.provenance && (
                    <span className="block mt-[5px] text-[12px] text-ink-3">{decidedWords(row.provenance)}</span>
                  )}
                </td>
                <td className={`${CELL} text-right tnum text-ink-2`}>
                  {row.digest ? (count.get(row.digest) ?? 0) : <span className="text-ink-3">—</span>}
                </td>
                <td className={`${CELL} text-right`}>
                  {/* **What needs a person outranks what a run did.** A pipeline you cannot run
                      has no useful last outcome, and saying `succeeded` beside two open values
                      reads as *ready*. */}
                  {waiting > 0 ? (
                    <span className="text-needs-you-ink">
                      {waiting} open
                    </span>
                  ) : last ? (
                    <span className={last.phase === "running" ? "text-now-ink" : "text-ink-2"}>
                      {last.phase}
                    </span>
                  ) : (
                    <span className="text-ink-3">{row.kept ? "never run" : "not kept"}</span>
                  )}
                </td>
                {/* After the row's link, never inside it: a delete is its own act (Part H). */}
                <td className={`${CELL} text-right`}><DeleteDraft id={row.id} name={row.name} /></td>
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
      <table className="w-full border-collapse table-fixed" style={{ minWidth: 720 }}>
        <colgroup>
          <col />
          <col className="w-[120px]" />
          <col className="w-[220px]" />
          <col className="w-[110px]" />
        </colgroup>
        <thead>
          <tr>
            {/* **The status dot is a column of its own**, 14px wide, and the table had none.
                The artboard leads every row with it — it is what lets somebody read *is any of
                this waiting on me* down a column instead of across six. */}
            <th className={HEAD}>Pipeline</th>
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
                                                        inline-block px-1 -mx-1 rounded-button">
                  {(run.pipeline_digest && named.get(run.pipeline_digest))
                    || <span className="text-ink-3">unknown pipeline</span>}
                </Link>
              </td>
              <td className={`${CELL} text-secondary text-ink-2`}>{ago(run.submitted_at)}</td>
              <td className={CELL}>
                <span className={run.phase === "failed" ? "text-needs-you-ink"
                  : run.phase === "running" ? "text-now-ink" : "text-ink-2"}>
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
