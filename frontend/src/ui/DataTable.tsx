import { useVirtualizer } from "@tanstack/react-virtual";
import { useRef, type ReactNode } from "react";

export type Column<T> = {
  id: string;
  header: ReactNode;
  cell: (row: T) => ReactNode;
  /** A CSS grid track; the default shares what is left. */
  width?: string;
};

const ROW = 38;

/** A table for hundreds of rows (samples, files, tasks): only the rows in view are mounted, so
 *  500 samples cost what 20 do. Its own box scrolls, never the page. */
export function DataTable<T>({ rows, columns, rowKey, label, height, highlight, onRow }: {
  rows: T[];
  columns: Column<T>[];
  rowKey: (row: T) => string;
  label: string;
  /** The scrolling box's height in px. */
  height: number;
  highlight?: (row: T) => boolean;
  onRow?: (row: T) => void;
}) {
  const scroller = useRef<HTMLDivElement>(null);
  const virtual = useVirtualizer({
    count: rows.length,
    getScrollElement: () => scroller.current,
    estimateSize: () => ROW,
    overscan: 8,
    initialRect: { width: 1200, height },
  });
  const tracks = columns.map((c) => c.width ?? "minmax(0,1fr)").join(" ");
  const cells = "grid items-center gap-[14px] px-5";

  return (
    <div role="table" aria-label={label} aria-rowcount={rows.length + 1} className="min-w-0 text-[13px]">
      <div role="rowgroup">
        <div role="row" aria-rowindex={1} style={{ gridTemplateColumns: tracks }}
             className={`${cells} h-9 border-b border-line text-[12px] text-ink-3 font-medium`}>
          {columns.map((c) => <div key={c.id} role="columnheader" className="truncate">{c.header}</div>)}
        </div>
      </div>
      <div ref={scroller} role="rowgroup" className="overflow-auto" style={{ height }}>
        <div className="relative w-full" style={{ height: virtual.getTotalSize() }}>
          {virtual.getVirtualItems().map((item) => {
            const row = rows[item.index];
            const marked = highlight?.(row) ?? false;
            return (
              <div key={rowKey(row)} role="row" aria-rowindex={item.index + 2} data-highlight={marked}
                   onClick={onRow ? () => onRow(row) : undefined}
                   tabIndex={onRow ? 0 : undefined}
                   onKeyDown={onRow ? (event) => { if (event.key === "Enter") onRow(row); } : undefined}
                   style={{ gridTemplateColumns: tracks, height: ROW, transform: `translateY(${item.start}px)` }}
                   className={`${cells} absolute left-0 right-0 top-0 border-t border-line-soft
                               ${marked ? "bg-needs-you-soft" : ""} ${onRow ? "cursor-pointer hover:bg-hover focus-visible:shadow-[var(--ring)] outline-none" : ""}`}>
                {columns.map((c) => <div key={c.id} role="cell" className="truncate min-w-0">{c.cell(row)}</div>)}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
