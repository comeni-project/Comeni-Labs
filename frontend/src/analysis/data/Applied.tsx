import { Panel } from "../../ui/Panel";
import { SourceTag } from "../../ui/SourceTag";
import type { AnalysisData, DataFix } from "./types";

/** What was done to how the files are read (#511): every fix, whose it is and why. The AI's stay
 *  AI until the person keeps them; any can be undone. A model's change stays reviewable. */
export function Applied({ data, onKeep, onUndo, busy = false, pendingFix }: {
  data: AnalysisData; onKeep: (index: number) => void; onUndo: (index: number) => void;
  busy?: boolean; pendingFix?: string | null;
}) {
  if (data.fixes.length === 0) return null;
  return (
    <Panel title="Changes" hint="yours and the AI's, kept on every scan">
      {data.fixes.map((fix, index) => {
        const said = describe(fix);
        return (
          <div key={`${index}-${said}`}
               className="flex items-center gap-3 flex-wrap px-5 py-[10px] border-t border-line-soft text-[13px]">
            <SourceTag source={fix.by === "ai" ? "ai" : "you"} />
            <span className="text-ink">{said}</span>
            {fix.reason && <span className="text-[12px] text-ink-3">{fix.reason}</span>}
            <span className="ml-auto flex gap-[6px]">
              {fix.by === "ai" && (
                <button type="button" disabled={busy} aria-label={`Keep: ${said}`} onClick={() => onKeep(index)}
                        className="h-7 px-[10px] rounded-control border border-line-2 bg-surface text-[12px] text-ink cursor-pointer">
                  Keep
                </button>
              )}
              <button type="button" disabled={busy} aria-label={`Undo: ${said}`} onClick={() => onUndo(index)}
                      className="h-7 px-[10px] rounded-control border border-line-2 bg-surface text-[12px] text-ink-2 cursor-pointer">
                {pendingFix === `/fixes/${index}` ? "Undoing…" : "Undo"}
              </button>
            </span>
          </div>
        );
      })}
    </Panel>
  );
}

function describe(fix: DataFix): string {
  if (fix.kind === "use_file") return `${fix.file} used as ${fix.sample}'s mate`;
  if (fix.kind === "keep") return `${fix.sample}'s ${fix.measurement} kept as it is`;
  return `${fix.sample} left out`;
}
