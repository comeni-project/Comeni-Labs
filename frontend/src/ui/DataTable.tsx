import { useVirtualizer } from "@tanstack/react-virtual";
import { type CSSProperties, type ReactNode, useRef } from "react";

export type Column<T> = {
  id: string;
  header: ReactNode;
  cell: (row: T) => ReactNode;
  /** A CSS grid track; the default shares what is left. */
  width?: string;
};

const ROW = 38;
const HEADER = 36;

const GAP = 14;
const PAD = 40;

/** A track's least width in px: `170px`, or the minimum of `minmax(140px,1.2fr)`. */
function leastOf(track: string): number {
  const px = /(\d+(?:\.\d+)?)px/.exec(track);
  return px ? Number(px[1]) : 0;
}

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
    // The header sits in the same scrolling box, above the rows.
    scrollMargin: HEADER,
    initialRect: { width: 1200, height },
  });
  const tracks = columns.map((c) => c.width ?? "minmax(120px,1fr)").join(" ");
  // **One width for the header and every row** (walk 2026-11-17): each row sized to its own
  // content (`w-max`), so on a narrow page the flexible columns spread differently row by row.
  // The page's width, or the columns' least, whichever is wider; a cell truncates past it.
  const least = columns.reduce((sum, c) => sum + leastOf(c.width ?? "minmax(120px,1fr)"), 0)
    + GAP * Math.max(0, columns.length - 1) + PAD;
  const cells = "grid items-center gap-[14px] px-5 w-[max(100%,var(--least))]";

  return (
    <div role="table" aria-label={label} aria-rowcount={rows.length + 1} className="min-w-0 text-[13px]"
         style={{ "--least": `${least}px` } as CSSProperties}>
      {/* **One box scrolls both ways**, so a wide table's header moves with its rows. */}
      <div ref={scroller} data-testid="table-scroll" className="overflow-auto" style={{ height: height + HEADER }}>
        <div role="rowgroup" className="sticky top-0 z-[1] bg-surface">
          <div role="row" aria-rowindex={1} style={{ gridTemplateColumns: tracks, height: HEADER }}
               className={`${cells} border-b border-line text-[12px] text-ink-3 font-medium`}>
            {columns.map((c) => <div key={c.id} role="columnheader" className="truncate">{c.header}</div>)}
          </div>
        </div>
        <div role="rowgroup" className="relative w-[max(100%,var(--least))]" style={{ height: virtual.getTotalSize() }}>
          {virtual.getVirtualItems().map((item) => {
            const row = rows[item.index];
            const marked = highlight?.(row) ?? false;
            return (
              <div key={rowKey(row)} role="row" aria-rowindex={item.index + 2} data-highlight={marked}
                   onClick={onRow ? () => onRow(row) : undefined}
                   tabIndex={onRow ? 0 : undefined}
                   onKeyDown={onRow ? (event) => { if (event.key === "Enter") onRow(row); } : undefined}
                   style={{ gridTemplateColumns: tracks, height: ROW,
                            transform: `translateY(${item.start - HEADER}px)` }}
                   className={`${cells} absolute left-0 top-0 border-t border-line-soft
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
