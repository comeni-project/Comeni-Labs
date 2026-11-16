import { Link, useParams, useSearchParams } from "react-router";

import { useAnalysis } from "../../app/AnalysisFrame";
import { RailControls } from "../../app/rail/RailContext";
import { useTypeNames } from "../../build/living/useTypeNames";
import { Failed, Loading } from "../../ui/States";
import { Assistant } from "../Assistant";
import { Applied } from "./Applied";
import { Files } from "./Files";
import { Across, Checks, ReferencesCard, ScanState } from "./Overview";
import { References } from "./References";
import { Samples } from "./Samples";
import { Start } from "./Start";
import type { AnalysisData } from "./types";
import { useAnalysisData } from "./useAnalysisData";

const TITLES: Record<string, string> = { references: "References", files: "All files" };
// A folder's last two parts: the rest is the data root, the same for every analysis.
const short = (path: string) => path.split("/").slice(-2).join("/");

/** **Data** (#511, board 2026-11-16): nothing ticked, the folders on the page to pick; read, the
 *  samples are the page, with what to check, the references and the facts beside them. The rail
 *  lists the folders read, and "Change folders" opens the picker again. */
export function DataPage() {
  const { sub: asked } = useParams();
  const sub = asked && asked in TITLES ? asked : undefined;
  const [search, setSearch] = useSearchParams();
  const { draftId } = useAnalysis();
  const data = useAnalysisData(draftId);
  const folders = data.data?.folders ?? [];
  const picking = search.has("folders") || (data.data !== undefined && folders.length === 0);
  const read = data.data?.scan.finished_at;

  return (
    <div className="overflow-y-auto h-full">
      <Assistant draftId={draftId} />
      {folders.length > 0 && (
        <RailControls label="Folders">
          <div className="flex flex-col">
            {folders.map((f) => <span key={f} className="px-[10px] py-[3px] font-data text-[12px] text-ink-2 truncate">{short(f)}</span>)}
            <Link to="?folders" className="px-[10px] py-[5px] text-[12.5px] font-semibold text-now-ink no-underline">Change folders</Link>
          </div>
        </RailControls>
      )}
      <div className="page">
        <header className="flex flex-wrap items-end gap-[14px]">
          <div className="flex flex-col gap-1 min-w-0">
            <h1 className="m-0 text-[22px] font-semibold tracking-[-.015em] text-ink">{sub ? TITLES[sub] : "Data"}</h1>
            {picking ? (
              <span className="text-[13.5px] text-ink-2">Pick the folders that hold this analysis's data. Files are read where they are, never copied.</span>
            ) : data.data && <Summary data={data.data} />}
          </div>
          {!picking && folders.length > 0 && data.data?.scan.state !== "scanning" && (
            <span className="ml-auto flex items-center gap-2 text-[12.5px] text-ink-3">
              {read && `Read at ${new Date(read).toLocaleTimeString([], { timeStyle: "short" })}`}
              <button type="button" onClick={data.rescan} disabled={data.busy}
                      className="h-[30px] px-[11px] rounded-control border border-line-2 bg-surface text-[12.5px] text-ink cursor-pointer">
                Read again
              </button>
            </span>
          )}
        </header>
        {data.error && (
          <p role="alert" className="m-0 flex items-start gap-3 px-4 py-3 rounded-panel bg-needs-you-soft text-[13px] text-needs-you-ink">
            <span className="flex-1">{data.error instanceof Error ? data.error.message : String(data.error)}</span>
            <button type="button" onClick={data.dismiss} aria-label="Dismiss"
                    className="border-0 bg-transparent text-needs-you-ink cursor-pointer">×</button>
          </p>
        )}
        {data.loading ? <Loading what="your data" />
          : data.loadError && !data.data ? <Failed error={data.loadError} />
          : data.data && (
            picking ? (
              <Start ticked={folders} onTick={(chosen) => { data.tick(chosen); setSearch({}, { replace: true }); }}
                     onCancel={folders.length ? () => setSearch({}, { replace: true }) : undefined} />
            )
            : sub === "references" ? <References data={data.data} onAdd={data.addReference} onRemove={data.removeReference} />
            : sub === "files" ? <Files draftId={draftId} />
            : (
              <>
                <ScanState data={data.data} onRescan={data.rescan} />
                <Checks data={data.data} onFix={data.fix} />
                <div className="grid gap-[14px] items-start lg:grid-cols-[minmax(0,1fr)_340px]">
                  <Samples data={data.data} setRule={data.setRule} confirmRule={data.confirmRule}
                           undoFix={data.undoFix} setCell={data.setCell} addColumn={data.addColumn} />
                  <div className="flex flex-col gap-[14px] min-w-0">
                    <ReferencesCard data={data.data} />
                    <Across data={data.data} />
                    <Applied data={data.data} onKeep={data.keepFix} onUndo={data.undoFix} />
                  </div>
                </div>
              </>
            ))}
      </div>
    </div>
  );
}

/** One line of what the analysis has: *5 samples of assemblies · 2 references · 17.9 MB*. */
function Summary({ data }: { data: AnalysisData }) {
  const typeName = useTypeNames();
  const kept = data.samples.filter((s) => !s.left_out);
  const kinds = [...new Set(kept.map((s) => s.type_id).filter((t): t is string => !!t))];
  const size = data.summary.tiles.find((t) => t.label === "Size on disk")?.value;
  const refs = data.references.length;
  return (
    <span className="text-[13.5px] text-ink-2">
      <b className="text-ink">{kept.length} {kept.length === 1 ? "sample" : "samples"}</b>
      {kinds.length > 0 && ` of ${kinds.map(typeName).join(" and ")}`}
      {` · ${refs ? `${refs} ${refs === 1 ? "reference" : "references"}` : "no references yet"}`}
      {size && ` · ${size}`}
    </span>
  );
}
