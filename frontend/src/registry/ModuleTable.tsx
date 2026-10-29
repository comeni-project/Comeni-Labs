import { colourOf, labelOf, StateIcon } from "./states";
import type { ModuleRow } from "./useCatalogue";

/** Board 1's columns, shared by the head and every row. An inline style, because a track list
 *  assembled in a string is invisible to Tailwind's scanner (see `runs/Board.tsx`). */
const COLUMNS = {
  gridTemplateColumns: "minmax(0,2.4fr) minmax(0,1.4fr) 88px 168px",
  gap: "16px",
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
      <div className="overflow-x-auto">
        <div className="min-w-[560px]">
          <div role="row" style={COLUMNS}
               className="grid px-[18px] py-[10px] border-b border-line text-[12px] font-medium text-ink-3 bg-paper-2">
            <span role="columnheader">Module</span>
            <span role="columnheader">Reads → makes</span>
            <span role="columnheader" className="text-right">Version</span>
            <span role="columnheader">Registry</span>
          </div>
          {rows.map((row) => (
            <div key={`${row.source}/${row.path}`} role="row" tabIndex={0} style={COLUMNS}
                 aria-selected={row.path === selected}
                 onClick={() => onSelect(row.path)}
                 onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onSelect(row.path); } }}
                 className={`grid items-center px-[18px] py-[11px] border-b border-line-soft cursor-pointer ${
                   row.path === selected ? "bg-now-soft" : "hover:bg-hover"}`}>
              <span role="cell" className="min-w-0">
                <span className="block font-data text-[13.5px] font-medium text-ink">{row.name}</span>
                <span className="block text-[12.5px] text-ink-3 truncate">{row.description ?? ""}</span>
              </span>
              <span role="cell" className="font-data text-[12.5px] text-ink-2">
                {io(row)}
              </span>
              <span role="cell" className="text-right font-data text-[12.5px] tabular-nums">
                {row.tool_version ?? <span className="text-ink-3">unknown</span>}
              </span>
              <span role="cell" className={`flex items-center gap-[7px] text-[13px] ${colourOf(row.state)}`}>
                <StateIcon state={row.state} />{labelOf(row.state)}
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

export function io(row: ModuleRow): string {
  const reads = row.formats_in.join(", ") || "—";
  const makes = row.formats_out.join(", ") || "—";
  return `${reads} → ${makes}`;
}
