import type { ReactNode } from "react";

/** One number with its name (the Data overview's tiles). */
export function Tile({ label, value, hint }: { label: string; value: ReactNode; hint?: ReactNode }) {
  return (
    <div className="bg-surface border border-line rounded-panel px-4 py-[14px] flex flex-col gap-1 min-w-0">
      <span className="text-[12.5px] text-ink-3">{label}</span>
      <span className="text-[22px] font-semibold tracking-[-.01em] text-ink tabular-nums">{value}</span>
      {hint && <span className="text-[12px] text-ink-3 truncate">{hint}</span>}
    </div>
  );
}
