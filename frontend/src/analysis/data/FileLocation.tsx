import { createContext, useContext, useEffect, useId, useRef, useState, type CSSProperties } from "react";
import { createPortal } from "react-dom";

export const FileLocationRoots = createContext<string[]>([]);

/** Location inside an added folder, keeping same-named folders distinguishable. */
function relativeLocation(path: string, roots: string[]): string {
  const parts = path.split("/").filter(Boolean);
  const folder = [...roots].sort((a, b) => b.length - a.length)
    .find((root) => path.startsWith(`${root.replace(/\/$/, "")}/`));
  if (!folder) return parts.slice(-2).join("/");
  const rootParts = folder.split("/").filter(Boolean);
  let depth = 1;
  while (depth < rootParts.length && roots.some((other) => other !== folder
    && other.split("/").filter(Boolean).slice(-depth).join("/") === rootParts.slice(-depth).join("/"))) depth++;
  return [...rootParts.slice(-depth), path.slice(folder.replace(/\/$/, "").length + 1)].join("/");
}

/** File ancestry from Data's added folders; opening it never rereads a file. */
export function FileLocation({ path }: { path: string }) {
  const roots = useContext(FileLocationRoots);
  const location = relativeLocation(path, roots);
  const id = useId();
  const trigger = useRef<HTMLButtonElement>(null);
  const card = useRef<HTMLDivElement>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const returningFocus = useRef(false);
  const [position, setPosition] = useState<CSSProperties | null>(null);
  const [copied, setCopied] = useState(false);
  const parts = location.split("/").filter(Boolean);
  const name = parts.at(-1) ?? path;
  const cancel = () => { if (timer.current) clearTimeout(timer.current); };
  const show = () => {
    cancel();
    const rect = trigger.current?.getBoundingClientRect();
    if (!rect) return;
    const width = Math.min(460, window.innerWidth - 24);
    const below = window.innerHeight - rect.bottom;
    const above = rect.top;
    setCopied(false);
    setPosition({
      width, left: Math.max(12, Math.min(rect.left, window.innerWidth - width - 12)),
      ...(below >= Math.min(360, above) ? { top: rect.bottom + 8 } : { bottom: window.innerHeight - rect.top + 8 }),
      maxHeight: Math.min(440, Math.max(below, above) - 20),
    });
  };
  const leave = () => {
    cancel();
    timer.current = setTimeout(() => {
      if (!card.current?.contains(document.activeElement) && document.activeElement !== trigger.current) setPosition(null);
    }, 180);
  };
  useEffect(() => () => { if (timer.current) clearTimeout(timer.current); }, []);
  useEffect(() => {
    if (!position) return;
    const close = () => setPosition(null);
    const outside = (event: PointerEvent) => {
      if (!card.current?.contains(event.target as Node) && !trigger.current?.contains(event.target as Node)) close();
    };
    const scroll = (event: Event) => { if (!card.current?.contains(event.target as Node)) close(); };
    const escape = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      cancel(); close();
      if (card.current?.contains(document.activeElement)) {
        returningFocus.current = true;
        trigger.current?.focus();
      }
    };
    document.addEventListener("pointerdown", outside);
    document.addEventListener("keydown", escape);
    window.addEventListener("scroll", scroll, true);
    window.addEventListener("resize", close);
    return () => {
      document.removeEventListener("pointerdown", outside);
      document.removeEventListener("keydown", escape);
      window.removeEventListener("scroll", scroll, true);
      window.removeEventListener("resize", close);
    };
  }, [position]);

  return <>
    <button ref={trigger} type="button" aria-label={`File location: ${name}`} aria-haspopup="dialog"
      aria-expanded={!!position} aria-controls={position ? id : undefined}
      onPointerEnter={() => { cancel(); timer.current = setTimeout(show, 180); }} onPointerLeave={leave}
      onFocus={() => { if (returningFocus.current) returningFocus.current = false; else show(); }} onBlur={leave}
      onClick={show}
      onKeyDown={(event) => {
        if (event.key === "ArrowDown") {
          event.preventDefault(); show();
          requestAnimationFrame(() => card.current?.querySelector("button")?.focus());
        }
      }}
      className="block max-w-full truncate border-0 p-0 bg-transparent font-data text-[12px] text-ink-2 text-left cursor-pointer hover:text-now-ink hover:underline decoration-dotted underline-offset-4 focus-visible:outline-2 focus-visible:outline-now rounded-xs">
      {name}
    </button>
    {position && createPortal(
      <div ref={card} id={id} role="dialog" aria-label={`File location for ${name}`}
        onPointerEnter={cancel} onPointerLeave={leave} onFocus={cancel} onBlur={leave}
        className="fixed z-[80] box-border flex flex-col rounded-panel border border-line-2 bg-surface shadow-e3 overflow-hidden text-ink"
        style={position}>
        <div className="flex items-center justify-between gap-3 px-4 py-3 border-b border-line-soft shrink-0">
          <strong className="text-[13px]">File location</strong>
          <button type="button" onClick={() => {
            void navigator.clipboard.writeText(location).then(() => setCopied(true), () => setCopied(false));
          }} className="connection-text-button">{copied ? "Copied" : "Copy path"}</button>
        </div>
        <div className="overflow-auto p-4">
          <p className="m-0 mb-1 text-[11px] text-ink-3">Relative to your added folders</p>
          <p className="m-0 mb-3 font-data text-[11.5px] text-ink-2 break-all select-text">{location}</p>
          <div aria-label="Its folders" className="font-data text-[12px] leading-6 min-w-max">
            {parts.map((part, index) => <div key={index} style={{ paddingLeft: index * 12 }}
              className={index === parts.length - 1 ? "font-semibold text-now-ink bg-now-soft rounded-control pr-2" : "text-ink-2"}>
              <span aria-hidden className="text-ink-3">{index === parts.length - 1 ? "└─ ▤ " : "└─ ▸ "}</span>{part}
            </div>)}
          </div>
        </div>
      </div>, document.body)}
  </>;
}
