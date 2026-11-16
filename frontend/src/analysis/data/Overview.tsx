import { useState } from "react";
import { Link } from "react-router";

import { Panel } from "../../ui/Panel";
import { SourceTag } from "../../ui/SourceTag";
import type { AnalysisData, DataFix } from "./types";

const TILE_TO: Record<string, string> = { Samples: "samples", Files: "files" };

/** Data's Overview (#511): the same four tiles whatever the data is, what needs checking, the
 *  samples compared by a fact this data measured, and what was measured. */
export function Overview({ data, onFix, onRescan }: {
  data: AnalysisData; onFix: (fix: DataFix) => void; onRescan?: () => void;
}) {
  if (data.folders.length === 0) {
    return (
      <p className="m-0 text-[14px] text-ink-2">
        Tick the folders that hold your data, in <b>Folders</b> on the left. Comeni reads the start of each file
        where it is, and never copies it.
      </p>
    );
  }
  const { summary } = data;
  return (
    <div className="flex flex-col gap-4">
      {data.scan.state === "scanning" && (
        <p role="status" className="m-0 text-[13px] text-now-ink">
          Reading the files: {data.scan.done} of {data.scan.total}…
        </p>
      )}
      {data.scan.state === "failed" && (
        <p role="alert" className="m-0 flex flex-wrap items-center gap-3 text-[13px] text-needs-you-ink">
          <span className="flex-1 min-w-0">The scan stopped: {data.scan.error}</span>
          {onRescan && (
            <button type="button" onClick={onRescan}
                    className="h-[30px] px-[11px] rounded-control border border-line-2 bg-surface text-[12.5px] text-ink cursor-pointer">
              Read again
            </button>
          )}
        </p>
      )}
      <div className="grid gap-3 grid-cols-2 lg:grid-cols-4">
        {summary.tiles.map((tile) => {
          const body = (
            <>
              <span className="text-[12px] font-semibold text-ink-3">{tile.label}</span>
              <span className="text-[24px] font-semibold tracking-[-.02em] text-ink">{tile.value}</span>
              {tile.hint && <span className="text-[12.5px] text-ink-3">{tile.hint}</span>}
            </>
          );
          const look = "flex flex-col gap-1 px-4 py-[14px] bg-surface border border-line rounded-panel no-underline text-left";
          return TILE_TO[tile.label] ? (
            <Link key={tile.label} data-testid="data-tile" to={TILE_TO[tile.label]} className={`${look} hover:bg-surface-2`}>
              {body}
            </Link>
          ) : (
            <div key={tile.label} data-testid="data-tile" className={look}>{body}</div>
          );
        })}
      </div>
      <div className="flex flex-col lg:flex-row gap-[14px] items-start">
        <div className="flex-1 min-w-0 flex flex-col gap-[14px] w-full">
          {data.checks.length > 0 && <Checks data={data} onFix={onFix} />}
          {summary.compare_by.length > 0 && <Compare data={data} />}
        </div>
        <Measured data={data} />
      </div>
    </div>
  );
}

function fixLabel(fix: DataFix): string {
  return fix.kind === "use_file" ? `Use ${fix.file}` : fix.kind === "keep" ? "Keep it" : "Leave out";
}

function fixName(fix: DataFix): string {
  if (fix.kind === "use_file") return `Use ${fix.file} as ${fix.sample}'s mate`;
  if (fix.kind === "keep") return `Keep ${fix.sample}'s ${fix.measurement}`;
  return `Leave ${fix.sample} out`;
}

function Checks({ data, onFix }: { data: AnalysisData; onFix: (fix: DataFix) => void }) {
  return (
    <Panel title="Check these" hint="found from what was measured" className="w-full">
      {data.checks.map((check) => (
        <div key={`${check.kind}-${check.sample}`}
             className="grid grid-cols-[10px_minmax(0,1fr)_auto] gap-3 items-center px-4 py-[10px] border-t border-line-soft">
          <span aria-hidden="true" className="w-2 h-2 rounded-full bg-measured" />
          <span className="flex flex-col gap-[2px] min-w-0">
            <span className="text-[13px] text-ink"><b>{check.sample}</b></span>
            <span className="text-[12px] text-ink-3 truncate">{check.detail}</span>
          </span>
          <span className="flex gap-[6px] flex-wrap justify-end">
            {[...check.fixes,
              ...(check.kind === "odd_fact" && check.measurement
                ? [{ kind: "keep", sample: check.sample, measurement: check.measurement } as DataFix] : [])
            ].map((fix) => (
              <button key={fixLabel(fix)} type="button" aria-label={fixName(fix)}
                      onClick={() => onFix(fix.kind === "keep"
                        ? { kind: "keep", sample: fix.sample, measurement: fix.measurement } as DataFix : fix)}
                      className="h-[30px] px-[11px] rounded-control border border-line-2 bg-surface text-[12.5px] text-ink
                                 cursor-pointer hover:bg-surface-2">
                {fixLabel(fix)}
              </button>
            ))}
          </span>
        </div>
      ))}
    </Panel>
  );
}

function Compare({ data }: { data: AnalysisData }) {
  const options = data.summary.compare_by;
  const [chosen, setChosen] = useState(options[0].measurement);
  const fact = options.find((o) => o.measurement === chosen) ?? options[0];
  const top = Math.max(...fact.values.map((v) => v.value), 1);
  const flagged = new Set(data.checks.map((c) => c.sample));
  const many = fact.values.length > 60;
  const unit = fact.unit ? ` ${fact.unit}` : "";
  return (
    <Panel title="Compare samples by" className="w-full">
      <div className="px-4 pb-[14px] flex flex-col gap-[10px]">
        <div className="flex items-center gap-2 flex-wrap">
          <select aria-label="Measured fact" value={fact.measurement} onChange={(e) => setChosen(e.target.value)}
                  className="h-7 border border-line-2 rounded-control px-2 text-[12.5px] bg-surface text-ink">
            {options.map((o) => <option key={o.measurement} value={o.measurement}>{o.label}</option>)}
          </select>
          <span className="text-[12px] text-ink-3">measured from this data · median {fact.median}{unit}</span>
        </div>
        {/* Hundreds of samples narrow the bars rather than widen the page. */}
        <div data-testid="compare-bars"
             className={`flex items-end h-[120px] pt-[6px] border-b border-line overflow-hidden ${many ? "gap-0" : "gap-1"}`}>
          {fact.values.map((v) => (
            <span key={v.sample} data-testid="compare-bar" title={`${v.sample}: ${v.value}${unit}`}
                  className={`flex-1 min-w-0 ${many ? "" : "rounded-t-xs"} ${flagged.has(v.sample) ? "bg-measured" : "bg-now-mid"}`}
                  style={{ height: `${Math.max(4, (v.value / top) * 100)}%` }} />
          ))}
        </div>
        <div className="flex justify-between font-data text-[11px] text-ink-3">
          <span>{fact.values[0]?.sample}</span>
          <span>{fact.values[fact.values.length - 1]?.sample}</span>
        </div>
      </div>
    </Panel>
  );
}

function said(value: unknown): string {
  if (value === true) return "yes";
  if (value === false) return "no";
  return String(value);
}

function Measured({ data }: { data: AnalysisData }) {
  const rule = data.rule.pattern === null ? "by name" : data.rule.pattern;
  return (
    <Panel title="What was measured" className="w-full lg:w-[340px] shrink-0">
      <div className="flex flex-col px-4 pb-[14px]">
        <span className="flex items-center justify-between gap-3 py-2 border-b border-line-soft text-[13px]">
          <span className="text-ink-2">Samples from file names</span>
          <span className="flex items-center gap-2 text-ink">{rule}
            <SourceTag source={data.rule.origin === "ai" ? "ai" : data.rule.origin === "you" ? "you" : "rule"} />
          </span>
        </span>
        {data.summary.measured.map((fact) => (
          <span key={fact.measurement}
                className="flex items-center justify-between gap-3 py-2 border-b border-line-soft text-[13px]">
            <span className="text-ink-2">{fact.label}</span>
            <span className="flex items-center gap-2 text-ink text-right">
              {fact.origin === "varies" ? "differs between samples" : said(fact.value)}
              <SourceTag source="measured" />
            </span>
          </span>
        ))}
        <Link to="samples" className="self-start mt-3 h-[30px] px-[11px] inline-flex items-center rounded-control border
                                      border-line-2 bg-surface text-[12.5px] text-ink no-underline hover:bg-surface-2">
          Open samples
        </Link>
      </div>
    </Panel>
  );
}
