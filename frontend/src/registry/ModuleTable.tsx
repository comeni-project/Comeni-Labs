import { FormatPills } from "./FormatPills";
import { colourOf, labelOf, StateIcon } from "./states";
import type { ModuleRow } from "./useCatalogue";

/** Board 1's columns, shared by the head and every row. An inline style, because a track list
 *  assembled in a string is invisible to Tailwind's scanner (see `runs/Board.tsx`). */
const COLUMNS = {
  gridTemplateColumns: "minmax(0,1.5fr) minmax(0,1.25fr) 76px 18px",
  gap: "14px",
} as const;

export function ModuleTable({ rows, selected, onSelect, footer }: {
  rows: ModuleRow[];
  selected: string;
  onSelect: (path: string) => void;
  footer: React.ReactNode;
}) {
  return (
    <div role="table" aria-label="nf-core modules"
         className="bg-surface border border-line rounded-panel overflow-hidden">
      {/* `contain: inline-size`: a scroll box still lends its content's minimum width to the
          page, which pushed every page at phone width to 610px; this keeps it inside. */}
      <div className="overflow-x-auto [contain:inline-size]">
        <div className="min-w-[560px]">
          <div role="row" style={COLUMNS}
               className="grid px-[14px] py-[9px] border-b border-line text-[12px] font-medium text-ink-3 bg-paper-2">
            <span role="columnheader">Module</span>
            <span role="columnheader">Reads → makes</span>
            <span role="columnheader">Version</span>
            <span role="columnheader"><span className="sr-only">Registry</span></span>
          </div>
          {rows.map((row) => (
            <div key={`${row.source}/${row.path}`} role="row" tabIndex={0} style={COLUMNS}
                 aria-selected={row.path === selected}
                 onClick={() => onSelect(row.path)}
                 onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onSelect(row.path); } }}
                 className={`grid items-center px-[14px] py-[9px] border-b border-line-soft cursor-pointer transition-colors ${
                   row.path === selected ? "bg-now-soft" : "hover:bg-hover"}`}>
              <span role="cell" className="min-w-0">
                <span className="block truncate font-data text-[13.5px] font-medium text-ink">
                  {row.path.includes("/") && <span className="font-normal text-ink-3">{row.path.slice(0, row.path.lastIndexOf("/") + 1)}</span>}
                  {row.path.slice(row.path.lastIndexOf("/") + 1)}
                </span>
                <span className="block text-[12.5px] text-ink-3 truncate">{row.description ?? ""}</span>
              </span>
              <span role="cell" className="flex items-center gap-1 min-w-0 overflow-hidden">
                <FormatPills declared={row.formats_in} mentioned={row.mentions_in} />
                <span className="shrink-0 mx-[2px] text-[12px] text-ink-3" aria-label="makes">→</span>
                <FormatPills declared={row.formats_out} mentioned={row.mentions_out} tone="makes" />
              </span>
              <span role="cell" className="truncate font-data text-[12px] text-ink-3 tabular-nums">
                {row.tool_version ?? "unknown"}
              </span>
              <span role="cell" title={labelOf(row.state)} className={colourOf(row.state)}>
                <StateIcon state={row.state} /><span className="sr-only">{labelOf(row.state)}</span>
              </span>
            </div>
          ))}
        </div>
      </div>
      <div className="flex flex-wrap justify-between gap-2 px-[18px] py-3 text-[12.5px] text-ink-3 border-t border-line">
        {footer}
      </div>
    </div>
  );
}
