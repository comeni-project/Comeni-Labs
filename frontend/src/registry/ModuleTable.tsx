import { FormatPills } from "./FormatPills";
import { labelOf, StateDot } from "./states";
import type { ModuleRow } from "./useCatalogue";

/** **The tool list** (board "7 · Registry"): a card that scrolls on its own, one slim row a tool —
 *  its state dot, path and version, what it does, and what it takes and makes. The selected row
 *  has a bar on its left; its card beside the list carries the detail. */
export function ModuleTable({ rows, selected, onSelect, header, more, footer }: {
  rows: ModuleRow[];
  selected: string;
  onSelect: (path: string) => void;
  header?: React.ReactNode;
  more?: React.ReactNode;
  footer: React.ReactNode;
}) {
  return (
    <div role="table" aria-label="nf-core modules"
         className="bg-surface border border-line rounded-panel overflow-hidden flex flex-col min-w-0">
      {header && <div className="flex flex-wrap items-center gap-2 px-4 py-3 border-b border-line">{header}</div>}
      <div role="rowgroup" className="flex flex-col overflow-y-auto max-h-[640px]">
        {rows.map((row) => {
          const on = row.path === selected;
          const cut = row.path.lastIndexOf("/") + 1;
          return (
            <div key={`${row.source}/${row.path}`} role="row" tabIndex={0} aria-selected={on}
                 onClick={() => onSelect(row.path)}
                 onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onSelect(row.path); } }}
                 className={`flex flex-col gap-1 pl-[13px] pr-4 py-[10px] border-b border-line-soft border-l-[3px] cursor-pointer transition-colors
                             ${on ? "bg-now-soft border-l-now" : "border-l-transparent hover:bg-hover"}`}>
              <span role="cell" className="flex items-center gap-2 min-w-0">
                <span title={labelOf(row.state)}><StateDot state={row.state} /><span className="sr-only">{labelOf(row.state)}</span></span>
                <span className="truncate font-data text-[13px] font-semibold text-ink">
                  {cut > 0 && <span className="font-normal">{row.path.slice(0, cut)}</span>}{row.path.slice(cut)}
                </span>
                <span className="ml-auto shrink-0 font-data text-[11.5px] text-ink-3 tabular-nums">{row.tool_version ?? "unknown"}</span>
              </span>
              {row.description && <span role="cell" className="pl-[15px] text-[12px] text-ink-2 truncate">{row.description}</span>}
              <span role="cell" className="pl-[15px] flex items-center gap-1 min-w-0 overflow-hidden">
                <FormatPills declared={row.formats_in} mentioned={row.mentions_in} />
                <span className="shrink-0 mx-[2px] text-[12px] text-ink-3" aria-label="makes">→</span>
                <FormatPills declared={row.formats_out} mentioned={row.mentions_out} tone="makes" />
              </span>
            </div>
          );
        })}
        {rows.length === 0 && <p className="m-0 px-4 py-6 text-[13px] text-ink-3">No tools match. Clear a filter.</p>}
        {more}
      </div>
      <div className="flex flex-wrap justify-between gap-2 px-4 py-[10px] border-t border-line text-[12px] text-ink-3">
        {footer}
      </div>
    </div>
  );
}
