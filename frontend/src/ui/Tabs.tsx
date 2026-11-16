import { useRef, type KeyboardEvent } from "react";

/** A row of tabs (Build's Step | Assistant): the selected one underlined in the now colour.
 *  Arrow keys move between them, as a tab list's do. */
export function Tabs<const T extends string>({ tabs, value, onChange, label }: {
  tabs: { id: T; label: string }[];
  value: T;
  onChange: (id: T) => void;
  label: string;
}) {
  const refs = useRef<(HTMLButtonElement | null)[]>([]);
  const move = (event: KeyboardEvent, index: number) => {
    const step = event.key === "ArrowRight" ? 1 : event.key === "ArrowLeft" ? -1 : 0;
    const jump = event.key === "Home" ? 0 : event.key === "End" ? tabs.length - 1 : null;
    if (!step && jump === null) return;
    event.preventDefault();
    const next = jump ?? (index + step + tabs.length) % tabs.length;
    onChange(tabs[next].id);
    refs.current[next]?.focus();
  };
  return (
    <div role="tablist" aria-label={label} className="flex border-b border-line">
      {tabs.map((tab, index) => {
        const on = tab.id === value;
        return (
          <button key={tab.id} ref={(el) => { refs.current[index] = el; }} type="button" role="tab"
                  aria-selected={on} tabIndex={on ? 0 : -1}
                  onClick={() => onChange(tab.id)} onKeyDown={(event) => move(event, index)}
                  className={`flex-1 h-10 border-0 border-b-2 bg-transparent text-[13.5px] font-semibold cursor-pointer
                              focus-visible:shadow-[var(--ring)]
                              ${on ? "text-now-ink border-now" : "text-ink-3 border-transparent hover:text-ink"}`}>
            {tab.label}
          </button>
        );
      })}
    </div>
  );
}
