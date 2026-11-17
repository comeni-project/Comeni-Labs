import { useNavigate, useParams } from "react-router";

import { useAnalysis } from "../../app/AnalysisFrame";
import { useTypeNames } from "../../build/living/useTypeNames";
import { Failed, Loading } from "../../ui/States";
import { Assistant } from "../Assistant";
import { useBuildCanvas } from "../run/useRuns";
import { Applied } from "./Applied";
import { Files } from "./Files";
import { FileLocationRoots } from "./FileLocation";
import { Across, Checks, ReferencesCard, ScanState } from "./Overview";
import { References } from "./References";
import { Samples } from "./Samples";
import { Start } from "./Start";
import type { AnalysisData } from "./types";
import { useAnalysisData } from "./useAnalysisData";

const TITLES: Record<string, string> = { folders: "Folders", references: "References", files: "All files" };

/** **Data** (#511, board 2026-11-16): nothing ticked, the folders on the page to pick; read, the
 *  samples are the page, with what to check, the references and the facts beside them. **Folders**
 *  is Data's own page in the rail (walk 2026-11-17), the picker with what is read ticked. */
export function DataPage() {
  const { sub: asked } = useParams();
  const sub = asked && asked in TITLES ? asked : undefined;
  const { draftId } = useAnalysis();
  const data = useAnalysisData(draftId);
  const pipeline = useBuildCanvas(draftId);
  const channels = pipeline.data?.canvas?.channels ?? [];
  const sampleTypes = new Set(channels.filter((c) => c.grain === "sample").map((c) => c.type_id));
  const referenceTypes = new Set(channels.filter((c) => c.grain === "study").map((c) => c.type_id));
  const used = (data.data?.samples ?? []).filter((s) => !s.left_out && sampleTypes.has(s.type_id ?? ""));
  const usedReferences = (data.data?.references ?? []).filter((r) => referenceTypes.has(r.type_id));
  const usedFiles = [...used.flatMap((s) => s.files), ...usedReferences.map((r) => r.path)];
  const folders = data.data?.folders ?? [];
  const picking = sub === "folders" || (data.data !== undefined && folders.length === 0);
  const navigate = useNavigate();
  const toData = () => navigate(`/a/${encodeURIComponent(draftId)}/data`, { replace: true });
  const read = data.data?.scan.finished_at;

  return (
    <FileLocationRoots.Provider value={folders}>
    <div className="overflow-y-auto h-full">
      <Assistant draftId={draftId} />
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
              <button type="button" onClick={() => navigate(`/a/${encodeURIComponent(draftId)}/data/folders`)}
                      className="h-[34px] px-3 rounded-control border border-now-line bg-now-soft text-[13px] font-semibold text-now-ink cursor-pointer">
                + Add dataset
              </button>
              {read && `Read at ${new Date(read).toLocaleTimeString([], { timeStyle: "short" })}`}
              <button type="button" onClick={data.rescan} disabled={data.busy}
                      className="h-[30px] px-[11px] rounded-control border border-line-2 bg-surface text-[12.5px] text-ink cursor-pointer">
                Read again
              </button>
            </span>
          )}
        </header>
        {data.data && channels.length > 0 && <section aria-label="Used by this pipeline" className="flex flex-wrap items-center gap-x-5 gap-y-2 px-4 py-3 rounded-panel border border-done-line bg-done-soft text-[13px]">
          <span className="font-semibold text-done-ink">Used by this pipeline</span>
          <span className="text-ink">{used.length} samples · {used.reduce((n, s) => n + s.files.length, 0)} sample files · {usedReferences.length} references</span>
          <span className="text-ink-2">{data.data.samples.filter((s) => !s.left_out && !sampleTypes.has(s.type_id ?? "")).length} other samples available · {data.data.samples.filter((s) => s.left_out).length} left out</span>
        </section>}
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
              <Start ticked={folders} usedFiles={usedFiles} onTick={(chosen) => { data.tick(chosen); toData(); }}
                     onCancel={folders.length ? toData : undefined} />
            )
            : sub === "references" ? <References data={data.data} onAdd={data.addReference} onRemove={data.removeReference} />
            : sub === "files" ? <Files draftId={draftId} />
            : (
              <>
                <ScanState data={data.data} onRescan={data.rescan} />
                <Checks data={data.data} onFix={data.fix} busy={data.busy || data.data.scan.state === "scanning"} pendingFix={data.pendingFix} />
                <div className="grid gap-[14px] items-start lg:grid-cols-[minmax(0,1fr)_340px]">
                  <Samples data={data.data} setRule={data.setRule} confirmRule={data.confirmRule}
                           undoFix={data.undoFix} setCell={data.setCell} addColumn={data.addColumn}
                           busy={data.busy || data.data.scan.state === "scanning"} />
                  <div className="flex flex-col gap-[14px] min-w-0">
                    <ReferencesCard data={data.data} />
                    <Across data={data.data} />
                    <Applied data={data.data} onKeep={data.keepFix} onUndo={data.undoFix}
                             busy={data.busy || data.data.scan.state === "scanning"} pendingFix={data.pendingFix} />
                  </div>
                </div>
              </>
            ))}
      </div>
    </div>
    </FileLocationRoots.Provider>
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
