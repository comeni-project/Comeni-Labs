import { useState } from "react";

export type PickerEntry = {
  id: string;
  name: string;
  group: string;
  says: string;
  before: string[];
  after: string[];
};

function Listed({ label, ids, empty }: { label: string; ids: string[]; empty?: string }) {
  return (
    <div className="flex flex-col gap-[3px]">
      <p className="m-0 text-[12px] text-ink-3">{label}</p>
      {ids.length === 0
        ? <p className="m-0 text-[12.5px] text-ink-3">{empty ?? "Nothing yet"}</p>
        : <ul className="list-none m-0 p-0 flex flex-wrap gap-1">
            {ids.map((id) => <li key={id} className="px-[6px] rounded-control bg-hover font-data text-[11.5px] text-ink-2">{id}</li>)}
          </ul>}
    </div>
  );
}

/** Choosing from what the registry already has: search over everything, groups to narrow it, and
 *  what the option in view connects to. `closest` pins entries the caller has a reason for; the
 *  order of the rest is the server's. A sheet at phone width. */
export function RegistryPicker({
  title, entries, before, after, emptyBefore, emptyAfter, closest = [], onPick, onClose, onNew, newLabel,
}: {
  title: string;
  entries: PickerEntry[];
  before: string;
  after: string;
  emptyBefore?: string;
  emptyAfter?: string;
  closest?: string[];
  onPick: (id: string) => void;
  onClose: () => void;
  onNew?: (name: string) => void;
  newLabel?: string;
}) {
  const [query, setQuery] = useState("");
  const [group, setGroup] = useState<string | null>(null);
  const [inView, setInView] = useState<string | null>(null);

  const words = query.toLowerCase().split(/\s+/).filter(Boolean);
  const matching = entries.filter((e) => {
    const text = `${e.id} ${e.name} ${e.says} ${e.group}`.toLowerCase();
    return words.every((w) => text.includes(w));
  });
  const groups = [...new Set(entries.map((e) => e.group))].sort()
    .map((g) => ({ g, n: matching.filter((e) => e.group === g).length })).filter((x) => x.n > 0);
  const shown = matching.filter((e) => group === null || e.group === group);
  const pinned = shown.filter((e) => closest.includes(e.id));
  const rest = shown.filter((e) => !closest.includes(e.id));
  const list = [...pinned, ...rest];
  const current = list.find((e) => e.id === inView) ?? list[0] ?? null;
  const typed = query.trim();

  const option = (e: PickerEntry) => (
    <button key={e.id} type="button" role="option" aria-selected={e.id === current?.id}
            className="picker-option" onClick={() => setInView(e.id)} onMouseEnter={() => setInView(e.id)}>
      <span className="block text-[13.5px]">{e.name}</span>
      <span className="block truncate font-data text-[12px] text-ink-3">{e.id}</span>
    </button>
  );

  return (
    <div role="dialog" aria-label={title} className="picker"
         onKeyDown={(event) => { if (event.key === "Escape") onClose(); }}>
      <div className="flex items-center gap-2 px-[14px] py-[10px] border-b border-line-2">
        <input type="search" autoFocus aria-label={title} value={query} placeholder="Search by name or meaning"
               onChange={(event) => { setQuery(event.target.value); setGroup(null); setInView(null); }}
               className="flex-1 min-w-0 bg-transparent border-0 outline-none text-ink text-[14.5px]" />
        <span className="font-data text-[12px] text-ink-3">{entries.length} in the registry</span>
        <button type="button" className="control" onClick={onClose}>Close</button>
      </div>
      {groups.length > 1 && (
        <div className="flex flex-wrap gap-1 px-3 py-2 border-b border-line" role="group" aria-label="Narrow down">
          {groups.map(({ g, n }) => (
            <button key={g} type="button" className="picker-group" aria-pressed={group === g}
                    onClick={() => { setGroup(group === g ? null : g); setInView(null); }}>
              {g.replace(/_/g, " ")} <span className="font-data text-ink-3">{n}</span>
            </button>
          ))}
        </div>
      )}
      <div className="picker-body">
        <div role="listbox" aria-label={title} className="p-[6px] overflow-auto">
          {pinned.length > 0 && <p className="mx-[10px] mt-[6px] mb-[2px] text-[11.5px] text-ink-3">Closest</p>}
          {pinned.map(option)}
          {pinned.length > 0 && rest.length > 0 && (
            <p className="mx-[10px] mt-[6px] mb-[2px] text-[11.5px] text-ink-3">Everything else</p>
          )}
          {rest.map(option)}
          {list.length === 0 && (
            <p className="m-0 px-[10px] py-[14px] text-[13px] text-ink-2">Nothing in the registry matches.</p>
          )}
        </div>
        {current && (
          <section aria-label={current.id} className="p-[14px] flex flex-col gap-[11px] overflow-auto bg-surface">
            <div>
              <p className="m-0 font-data text-[13.5px] break-all">{current.id}</p>
              <p className="mt-1 mb-0 text-[13px] text-ink-2">{current.says}</p>
            </div>
            <Listed label={before} ids={current.before} empty={emptyBefore} />
            <Listed label={after} ids={current.after} empty={emptyAfter} />
          </section>
        )}
      </div>
      <div className="flex items-center gap-[10px] px-[14px] py-[10px] border-t border-line-2">
        {onNew && (
          <button type="button" className="control border-dashed" disabled={!typed} onClick={() => onNew(typed)}>
            + {newLabel}{typed ? ` “${typed}”` : ""}
          </button>
        )}
        {current && (
          <button type="button" className="control-primary ml-auto" onClick={() => onPick(current.id)}>
            Use {current.id}
          </button>
        )}
      </div>
    </div>
  );
}
