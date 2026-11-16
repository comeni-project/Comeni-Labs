import { Link } from "react-router";

import { useTypeNames } from "../../build/living/useTypeNames";
import { chipName } from "../../build/living/CollectionChannel";
import { Panel } from "../../ui/Panel";
import { useBuildCanvas } from "../run/useRuns";
import type { AnalysisData, DataFix } from "./types";
import { withUnit } from "./values";

/** **Data, read** (board 2026-11-16): the pieces around the samples table — the scan's state,
 *  what to check one row a sample, the references the pipeline needs, and the facts across the
 *  samples. The samples themselves are the page (`Samples`). */

export function ScanState({ data, onRescan }: { data: AnalysisData; onRescan?: () => void }) {
  if (data.scan.state === "scanning") {
    return <p role="status" className="m-0 text-[13px] text-now-ink">Reading the files: {data.scan.done} of {data.scan.total}…</p>;
  }
  if (data.scan.state !== "failed") return null;
  return (
    <p role="alert" className="m-0 flex flex-wrap items-center gap-3 text-[13px] text-needs-you-ink">
      <span className="flex-1 min-w-0">The scan stopped: {data.scan.error}</span>
      {onRescan && (
        <button type="button" onClick={onRescan}
                className="h-[30px] px-[11px] rounded-control border border-line-2 bg-surface text-[12.5px] text-ink cursor-pointer">
          Read again
        </button>
      )}
    </p>
  );
}

function fixName(fix: DataFix): string {
  if (fix.kind === "use_file") return `Use ${fix.file} as ${fix.sample}'s mate`;
  if (fix.kind === "keep") return `Keep ${fix.sample} as it is`;
  return `Leave ${fix.sample} out`;
}

/** **Check these, one row a sample**: a sample odd in two measurements is one thing to look at,
 *  kept or left out once. */
export function Checks({ data, onFix }: { data: AnalysisData; onFix: (fix: DataFix) => void }) {
  const bySample = new Map<string, AnalysisData["checks"]>();
  for (const check of data.checks) bySample.set(check.sample, [...(bySample.get(check.sample) ?? []), check]);
  if (bySample.size === 0) return null;
  const button = "h-9 px-[14px] rounded-control text-[13px] cursor-pointer";
  return (
    <Panel title="Check these" hint="found from what was measured">
      {[...bySample].map(([sample, checks]) => {
        const uses = checks.flatMap((c) => c.fixes.filter((f) => f.kind === "use_file"));
        const keeps = checks.filter((c) => c.kind === "odd_fact" && c.measurement)
          .map((c) => ({ kind: "keep", sample, measurement: c.measurement } as DataFix));
        const leave = { kind: "leave_out", sample } as DataFix;
        return (
          <div key={sample} data-testid="check"
               className="grid grid-cols-[28px_minmax(0,1fr)] sm:grid-cols-[28px_minmax(0,1fr)_auto] gap-3 items-center px-4 py-[10px] border-t border-line-soft">
            <span aria-hidden="true" className="w-7 h-7 rounded-full bg-measured-soft text-measured-ink grid place-items-center text-[14px] font-bold">!</span>
            <span className="flex flex-col gap-[2px] min-w-0">
              <span className="text-[13.5px] font-semibold text-ink">{sample}</span>
              <span className="text-[12.5px] text-ink-2">{checks.map((c) => c.detail).join(" · ")}</span>
            </span>
            <span className="col-start-2 sm:col-start-auto flex gap-2 flex-wrap justify-end">
              {uses.slice(0, 1).map((fix) => (
                <button key="use" type="button" aria-label={fixName(fix)} onClick={() => onFix(fix)}
                        className={`${button} border-0 bg-action text-on-action shadow-raise font-semibold`}>Use {fix.file}</button>
              ))}
              {keeps.length > 0 && (
                <button type="button" aria-label={fixName(keeps[0])} onClick={() => keeps.forEach(onFix)}
                        className={`${button} border border-line-2 bg-surface text-ink`}>Keep it</button>
              )}
              <button type="button" aria-label={fixName(leave)} onClick={() => onFix(leave)}
                      className={`${button} border border-line-2 bg-surface text-ink`}>Leave out</button>
            </span>
          </div>
        );
      })}
    </Panel>
  );
}

/** **The references the pipeline reads**: one line each study-wide input Build's canvas has, set
 *  or not; before anything is built, the references chosen so far. */
export function ReferencesCard({ data }: { data: AnalysisData }) {
  const typeName = useTypeNames();
  const canvas = useBuildCanvas(data.draft_id);
  const wanted = (canvas.data?.canvas?.channels ?? []).filter((c) => c.grain === "study").map((c) => c.type_id);
  const kinds = [...new Set([...wanted, ...data.references.map((r) => r.type_id)])];
  return (
    <Panel title="References" actions={<Link to="references" className="text-[12.5px] font-semibold text-now-ink no-underline">Change</Link>}>
      {kinds.length === 0 && <p className="m-0 px-5 pb-4 text-[13px] text-ink-3">None yet.</p>}
      {kinds.map((kind) => {
        const ref = data.references.find((r) => r.type_id === kind);
        return (
          <div key={kind} data-testid="reference-slot"
               className="grid grid-cols-[18px_minmax(0,1fr)] gap-x-[10px] gap-y-[2px] px-5 py-[10px] border-t border-line-soft">
            <span aria-hidden="true" className={`mt-[2px] w-[14px] h-[14px] rounded-full grid place-items-center text-[9px] font-bold
                                                 ${ref ? "bg-done-soft text-done-ink" : "bg-measured-soft text-measured-ink"}`}>{ref ? "✓" : "!"}</span>
            <span className="text-[13px] font-semibold text-ink">{chipName(typeName(kind))}</span>
            <span />
            {ref ? <span className="font-data text-[12px] text-ink-2 truncate">{ref.name}</span>
              : <Link to="references" className="text-[12.5px] text-now-ink no-underline">Choose a file</Link>}
          </div>
        );
      })}
    </Panel>
  );
}

/** **Across the samples**: each measured fact, the same for all or its range and median. */
export function Across({ data }: { data: AnalysisData }) {
  const kept = data.samples.filter((s) => !s.left_out).length;
  if (data.summary.measured.length === 0) return null;
  return (
    <Panel title="Across the samples">
      <div className="flex flex-col gap-[10px] px-5 pb-4">
        {data.summary.measured.map((fact) => {
          const numbers = data.summary.compare_by.find((c) => c.measurement === fact.measurement);
          const values = numbers?.values.map((v) => v.value) ?? [];
          const said = fact.origin !== "varies"
            ? (fact.value === true ? `all ${kept}` : fact.value === false ? "none"
              : `${String(fact.value)}${numbers?.unit ? ` ${numbers.unit}` : ""}, all ${kept}`)
            : numbers && values.length
              ? `${withUnit(Math.min(...values), numbers.unit)} to ${withUnit(Math.max(...values), numbers.unit)}, median ${withUnit(numbers.median, numbers.unit)}`
              : "differs between samples";
          return (
            <span key={fact.measurement} className="flex justify-between gap-3 text-[13px]">
              <span className="text-ink-2">{fact.label}</span>
              <span className="font-semibold text-ink text-right">{said}</span>
            </span>
          );
        })}
      </div>
    </Panel>
  );
}
