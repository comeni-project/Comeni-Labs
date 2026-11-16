import { useParams } from "react-router";

import { useAnalysis } from "../../app/AnalysisFrame";
import { RailControls } from "../../app/rail/RailContext";
import { Failed, Loading } from "../../ui/States";
import { FolderTree } from "./FolderTree";
import { Files } from "./Files";
import { Overview } from "./Overview";
import { References } from "./References";
import { Samples } from "./Samples";
import { useAnalysisData } from "./useAnalysisData";

const TITLES: Record<string, string> = { samples: "Samples", references: "References", files: "Files" };

/** Data (#511): what the analysis has, read where it is. The rail holds the folders to tick; the
 *  page is the Overview or one of its pages. */
export function DataPage() {
  const { sub } = useParams();
  const { draftId } = useAnalysis();
  const data = useAnalysisData(draftId);
  const folders = data.data?.folders ?? [];
  // The folder's last two parts: the rest is the data root, the same for every analysis.
  const short = (path: string) => `…/${path.split("/").slice(-2).join("/")}`;
  const where = folders.length === 1 ? short(folders[0]) : folders.length > 1 ? `${folders.length} folders` : null;

  return (
    <div className="overflow-y-auto h-full">
      <RailControls label="Folders">
        <FolderTree ticked={folders} onTick={data.tick} />
      </RailControls>
      <div className="max-w-[1140px] mx-auto px-4 sm:px-9 pt-7 pb-10 flex flex-col gap-4">
        <header className="flex flex-wrap items-end gap-[14px]">
          <div className="flex flex-col gap-1 min-w-0">
            <h1 className="m-0 text-[24px] font-semibold tracking-[-.015em] text-ink">{sub ? TITLES[sub] : "Data"}</h1>
            {where && (
              <span className="text-[13.5px] text-ink-2">
                <span className="font-data text-[12.5px] break-all">{where}</span>
                {" · "}{data.data?.files ?? 0} files · read where they are, never copied
              </span>
            )}
          </div>
        </header>
        {data.loading ? <Loading what="your data" />
          : data.error && !data.data ? <Failed error={data.error} />
          : data.data && (
            sub === "samples" ? <Samples data={data.data} setRule={data.setRule} confirmRule={data.confirmRule}
                                         undoFix={data.undoFix} setColumn={data.setColumn} />
            : sub === "references" ? <References data={data.data} onAdd={data.addReference}
                                                 onRemove={data.removeReference} />
            : sub === "files" ? <Files draftId={draftId} />
            : <Overview data={data.data} onFix={data.fix} />)}
      </div>
    </div>
  );
}
