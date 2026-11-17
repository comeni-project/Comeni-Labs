import { useState, type ReactNode } from "react";

export type CheckOption = { id: string; label: ReactNode; count: number; on: boolean; text?: string };

/** **A filter's tick list** with counts — the panel's one control, on Registry · Tools and Run →
 *  Outputs alike. Past `searchFrom` options it gets its own search, and past `max` it scrolls in
 *  its own box, so four hundred samples or two hundred formats fit. Ticked options stay in view
 *  whatever the search. */
export function CheckList({ title, options, onFlip, searchFrom = 10, max = 220 }: {
  title: string; options: CheckOption[]; onFlip: (id: string) => void; searchFrom?: number; max?: number;
}) {
  const [find, setFind] = useState("");
  const q = find.trim().toLowerCase();
  const shown = options.filter((o) => o.on || !q || (o.text ?? String(o.label)).toLowerCase().includes(q));
  if (!options.length) return null;
  return (
    <fieldset className="m-0 p-0 border-0 flex flex-col gap-1 min-w-0">
      <legend className="p-0 mb-1 text-[11.5px] font-semibold text-ink-3">
        {title} <span className="font-normal">{options.length}</span>
      </legend>
      {options.length > searchFrom && (
        <input aria-label={`Find ${title.toLowerCase()}`} placeholder={`Find ${title.toLowerCase()}`} value={find}
               onChange={(e) => setFind(e.target.value)}
               className="h-[28px] w-full px-[10px] rounded-control border border-line-2 bg-surface text-[12px] text-ink" />
      )}
      <div className="flex flex-col gap-[2px] overflow-y-auto" style={{ maxHeight: max }}>
        {shown.map((o) => (
          <label key={o.id} className="flex items-center gap-2 min-h-[26px] px-1 rounded-control text-[12.5px] text-ink-2 cursor-pointer hover:bg-surface-2">
            <input type="checkbox" checked={o.on} onChange={() => onFlip(o.id)} className="w-[14px] h-[14px] shrink-0 accent-[var(--now)]" />
            <span className={`truncate ${o.on ? "text-ink font-semibold" : ""}`}>{o.label}</span>
            <span className="ml-auto font-data text-[11px] text-ink-3">{o.count.toLocaleString("en")}</span>
          </label>
        ))}
        {shown.length === 0 && <span className="px-1 text-[12px] text-ink-3">None match.</span>}
      </div>
    </fieldset>
  );
}
