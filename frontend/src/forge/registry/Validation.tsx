import type { Origins, Revision } from "../../api/registry";
import { Refusal } from "../../ui/Refusal";
import { Mark } from "./Status";

/** What the checks said, and where each value came from — §8.5's two lower panels.
 *
 * **`ran: false` is a third state and not a failure.** `_record_verdict` stores it deliberately
 * while nothing runs the ladder, precisely so a page can say *not yet checked* rather than
 * *failed*. A screen that drew those the same way would tell a reviewer a candidate is broken
 * when what is broken is that nobody has looked.
 */

type Verdict = {
  ran?: boolean;
  why?: string;
  diagnostics?: string[];
};

/** The five rungs `verify.py` walks, named here so an unrun ladder can still be drawn as a
 *  ladder. They come back in `validation.rungs` once the worker runs them. */
const RUNGS = ["contract loads", "conforms to the module", "Nextflow parses", "types resolve", "routes"];

export function Validation({ revision }: { revision: Revision | undefined }) {
  const verdict = (revision?.validation ?? {}) as Verdict;
  const ran = verdict.ran === true;

  return (
    <div className="border border-line bg-surface rounded-[var(--r)] px-[18px] py-4">
      <div className="font-data text-label tracking-[.15em] uppercase text-ink-3 pb-[9px]">
        Validation
      </div>

      {!revision && <p className="text-body text-ink-3 m-0">No revision has been produced yet.</p>}

      {revision && !ran && (
        <>
          {/* The code says which of the two this is, so it is rendered through `Refusal`
              rather than as a red sentence — the same renderer every other coded message on
              this product uses, which is what keeps `MI0108` looking up. */}
          {verdict.why ? (
            <Refusal message={verdict.why} />
          ) : (
            <p className="text-body text-ink-3 m-0">The checks have not run against this yet.</p>
          )}
          <p className="text-secondary text-ink-3 m-0 pt-2">
            Approval stays unavailable while this is true — a green verdict is a statement about
            a check that happened.
          </p>
        </>
      )}

      {revision && ran && (
        <div className="flex flex-col">
          {RUNGS.map((rung) => {
            // A rung with a diagnostic against it failed; the rest ran and passed. Reading the
            // codes rather than a per-rung boolean is what stops the page inventing a shape the
            // stored verdict does not have.
            const failed = (verdict.diagnostics ?? []).some((code) => code.includes(rung));
            return (
              <span key={rung} className="flex items-center gap-[9px] py-[7px] text-body">
                <Mark shape={failed ? "fail" : "done"} />
                {rung}
              </span>
            );
          })}
        </div>
      )}

      {(verdict.diagnostics ?? []).length > 0 && (
        <div className="pt-3 border-t border-line-soft mt-3 flex flex-col gap-2">
          {verdict.diagnostics?.map((code) => <Refusal key={code} message={code} />)}
        </div>
      )}
    </div>
  );
}

/** Where each value came from — §8.5's provenance summary, as one bar and three counts.
 *
 * **Open is counted beside the three settled origins.** A bar showing only what was decided
 * makes a candidate with nine open holes look as finished as one with none.
 */
export function Provenance({ origins }: { origins: Origins }) {
  const parts = [
    { n: origins.derived, tone: "var(--pea)", what: "derived from the source" },
    { n: origins.model, tone: "var(--link)", what: "proposed by the model" },
    { n: origins.human, tone: "var(--measured)", what: "edited by hand" },
    { n: origins.open, tone: "var(--fault)", what: "still open" },
  ];
  const total = Math.max(1, parts.reduce((sum, part) => sum + part.n, 0));

  return (
    <div className="border border-line bg-surface rounded-[var(--r)] px-[18px] py-4">
      <div className="font-data text-label tracking-[.15em] uppercase text-ink-3 pb-3">
        Where each value came from
      </div>
      <div className="flex gap-[3px] h-[9px]">
        {parts
          .filter((part) => part.n > 0)
          .map((part) => (
            <div
              key={part.what}
              className="grow-x"
              style={{ flex: `0 0 ${(part.n / total) * 100}%`, background: part.tone }}
            />
          ))}
      </div>
      <div className="flex flex-col gap-1.5 pt-[11px] text-body text-ink-2">
        {parts.map((part) => (
          <span key={part.what} className={part.n === 0 ? "text-ink-3" : ""}>
            <span className="tnum">{part.n}</span> {part.what}
          </span>
        ))}
      </div>
    </div>
  );
}
