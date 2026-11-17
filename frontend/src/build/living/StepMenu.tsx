import { useEffect, useRef } from "react";

export type MenuItem = { id: string; label: string; danger?: boolean };

/** **A step's menu** (#499): what a person can do to this step, one list, from a right-click,
 *  a long press, `⋯`, or Shift+F10 and the menu key. Arrows move, Enter chooses, Esc closes; the
 *  caller puts focus back on the step. No *Why is it here?*: that is asked in the chat. */
export function StepMenu({ label, items, onChoose, onClose }: {
  label: string;
  items: MenuItem[];
  onChoose: (id: string) => void;
  onClose: () => void;
}) {
  const list = useRef<HTMLDivElement>(null);
  const buttons = () => Array.from(list.current?.querySelectorAll<HTMLButtonElement>("[role='menuitem']") ?? []);
  useEffect(() => { buttons()[0]?.focus(); }, []);
  const move = (by: number) => {
    const all = buttons();
    const at = all.indexOf(document.activeElement as HTMLButtonElement);
    all[(at + by + all.length) % all.length]?.focus();
  };
  return (
    <div ref={list} role="menu" aria-label={label} tabIndex={-1}
         onKeyDown={(e) => {
           if (e.key === "ArrowDown") { e.preventDefault(); move(1); }
           else if (e.key === "ArrowUp") { e.preventDefault(); move(-1); }
           else if (e.key === "Home") { e.preventDefault(); buttons()[0]?.focus(); }
           else if (e.key === "End") { e.preventDefault(); buttons().at(-1)?.focus(); }
           else if (e.key === "Escape" || e.key === "Tab") { e.preventDefault(); onClose(); }
         }}
         className="w-fit min-w-[200px] py-[4px] rounded-button border shadow-raise flex flex-col"
         style={{ background: "var(--surface)", borderColor: "var(--line-2)" }}>
      {items.map((item) => (
        <button key={item.id} type="button" role="menuitem" tabIndex={-1} onClick={() => onChoose(item.id)}
                className={`text-left px-[12px] py-[7px] min-h-[36px] md:min-h-0 bg-transparent border-0 text-[13px]
                            cursor-pointer hover:bg-[var(--hover)] focus-visible:bg-[var(--hover)] focus-visible:outline-none
                            ${item.danger ? "text-needs-you-ink" : "text-ink"}`}>
          {item.label}
        </button>
      ))}
    </div>
  );
}
