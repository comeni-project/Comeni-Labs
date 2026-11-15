import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";

import { folds as foldsOf, type Fold } from "./folds";

/** What the page lays over one line: hidden by a filter, a mark of how its value was decided,
 *  whether it is the selected value, and what clicking it does. */
export type LineDecoration = {
  hidden?: boolean; mark?: ReactNode; selected?: boolean; onSelect?: () => void;
} | null;

/** **`pipeline.yml`, as text a person reads** (#499, direction A): line numbers, folds that open
 *  and close, each value's reason opened beneath its own lines, and a toolbar for any text
 *  selected. The text is the server's; nothing here re-serialises it. */
export function FileView({ text, decorate, below, onAbout, scrollTo }: {
  text: string;
  decorate?: (index: number, line: string) => LineDecoration;
  /** What to draw beneath a line — the reason of the value it ends (`index` is 0-based). */
  below?: (index: number) => ReactNode;
  /** Ask about selected lines: their real numbers (1-based), and their text. */
  onAbout?: (from: number, to: number, text: string, how: "explain" | "ask") => void;
  /** A 0-based line to bring into view, when it changes. */
  scrollTo?: number | null;
}) {
  const lines = useMemo(() => text.split("\n"), [text]);
  const all = useMemo(() => foldsOf(text), [text]);
  const [toggled, setToggled] = useState<Set<number>>(new Set());
  const folded = (fold: Fold) => fold.folded !== toggled.has(fold.start);
  const hiding = all.filter(folded);
  const root = useRef<HTMLPreElement>(null);
  const [picked, setPicked] = useState<{ from: number; to: number; text: string; top: number } | null>(null);

  useEffect(() => {
    if (scrollTo === null || scrollTo === undefined) return;
    const fold = hiding.find((f) => scrollTo > f.start && scrollTo <= f.end);
    if (fold) setToggled((was) => new Set(was).add(fold.start));
    root.current?.querySelector<HTMLElement>(`[data-n="${scrollTo + 1}"]`)?.scrollIntoView?.({ block: "start" });
    // eslint-disable-next-line react-hooks/exhaustive-deps -- only a new target scrolls
  }, [scrollTo]);

  /** The selected lines, read off the `data-n` the selection starts and ends in. */
  const select = () => {
    const chosen = window.getSelection();
    if (!chosen || chosen.isCollapsed || !root.current) { setPicked(null); return; }
    const at = (n: Node | null) => (n instanceof Element ? n : n?.parentElement)?.closest<HTMLElement>("[data-n]");
    const a = at(chosen.anchorNode), b = at(chosen.focusNode);
    if (!a || !b || !root.current.contains(a) || !root.current.contains(b)) { setPicked(null); return; }
    const [from, to] = [Number(a.dataset.n), Number(b.dataset.n)].sort((x, y) => x - y);
    const top = b.offsetTop + b.offsetHeight;
    setPicked({ from, to, text: lines.slice(from - 1, to).join("\n").slice(0, 2000), top });
  };

  const drawn: ReactNode[] = [];
  for (let index = 0; index < lines.length; index += 1) {
    const line = lines[index];
    const fold = all.find((f) => f.start === index);
    const deco = decorate?.(index, line) ?? null;
    if (deco?.hidden) continue;
    const closed = fold ? folded(fold) : false;
    drawn.push(
      <span key={index} data-testid="file-line" data-n={index + 1} onClick={deco?.onSelect}
            data-selected={deco?.selected || undefined}
            className="grid grid-cols-[44px_18px_minmax(0,1fr)] relative"
            style={{ ...(deco?.selected ? { background: "var(--now-soft)", boxShadow: "inset 3px 0 0 var(--now)" } : {}),
                     ...(deco?.onSelect ? { cursor: "pointer" } : {}),
                     ...(/:\s*null\b/.test(line) && !deco?.selected ? { background: "var(--needs-you-soft)" } : {}) }}>
        {/* The number and the fold arrow are drawn by CSS, so a line's text is only its text —
            for a reader, a test, and whatever is copied. */}
        <span aria-hidden className="text-right pr-[10px] text-ink-3 select-none before:content-[attr(data-n)]"
              data-n={index + 1} />
        {fold ? (
          <button type="button" aria-expanded={!closed}
                  aria-label={closed ? `${line.trim()} ${fold.summary}` : `fold ${line.trim()}`}
                  onClick={(e) => { e.stopPropagation(); setToggled((was) => {
                    const next = new Set(was);
                    if (next.has(fold.start)) next.delete(fold.start); else next.add(fold.start);
                    return next;
                  }); }}
                  className={`p-0 bg-transparent border-0 text-ink-3 cursor-pointer select-none hover:text-ink
                              ${closed ? "before:content-['▸']" : "before:content-['▾']"}`} />
        ) : <span />}
        <span className="whitespace-pre min-w-0">
          {line || " "}
          {closed && <span className="text-ink-3"> {fold!.summary}</span>}
          {deco?.mark && <span className="absolute right-[6px] top-[2px]">{deco.mark}</span>}
        </span>
      </span>,
    );
    const after = below?.(index);
    if (after) drawn.push(<span key={`below-${index}`} className="block pl-[62px] pr-4 py-1">{after}</span>);
    if (closed) index = fold!.end;
  }

  return (
    <div className="relative">
      <pre ref={root} data-testid="artifact-text" onMouseUp={select} onKeyUp={select}
           className="m-0 font-data text-[12px] leading-[1.75] text-ink-2">
        {drawn}
      </pre>
      {picked && onAbout && (
        <div role="toolbar" aria-label="about the selection"
             className="absolute left-[62px] z-10 flex gap-[2px] p-[4px] rounded-button border shadow-raise"
             style={{ top: picked.top + 4, background: "var(--surface)", borderColor: "var(--line-2)" }}>
          {([["explain", "Explain this"], ["ask", "Ask about it…"]] as const).map(([how, label]) => (
            <button key={how} type="button" onClick={() => { onAbout(picked.from, picked.to, picked.text, how); setPicked(null); }}
                    className="px-[10px] py-[5px] rounded-control border-0 bg-transparent text-[12.5px] text-ink cursor-pointer
                               hover:bg-[var(--hover)] focus-visible:shadow-[var(--ring)]">
              {label}
            </button>
          ))}
          <button type="button" onClick={() => { void navigator.clipboard?.writeText(picked.text); setPicked(null); }}
                  className="px-[10px] py-[5px] rounded-control border-0 bg-transparent text-[12.5px] text-ink-2 cursor-pointer
                             hover:bg-[var(--hover)] focus-visible:shadow-[var(--ring)]">
            Copy
          </button>
        </div>
      )}
    </div>
  );
}
