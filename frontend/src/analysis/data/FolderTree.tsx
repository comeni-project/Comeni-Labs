import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { get } from "../../api/client";
import type { components } from "../../api/schema";

type Listing = components["schemas"]["FolderListing"];
type Folder = components["schemas"]["Folder"];

const tree = (path: string | null) =>
  path === null ? "/data/tree" : `/data/tree?path=${encodeURIComponent(path)}`;

/** The folders this installation reads, to tick (#511). A folder's own files are read; its
 *  subfolders are ticked on their own. Opened lazily, one level at a time. */
export function FolderTree({ ticked, onTick }: { ticked: string[]; onTick: (folders: string[]) => void }) {
  const roots = useQuery({ queryKey: ["data-tree", null], queryFn: () => get<Listing>(tree(null)) });
  // Up and Down move between the folders in sight; Right opens one, Left closes it.
  const move = (event: React.KeyboardEvent<HTMLDivElement>) => {
    const ticks = Array.from(event.currentTarget.querySelectorAll("[data-tick]")) as HTMLButtonElement[];
    const at = ticks.indexOf(document.activeElement as HTMLButtonElement);
    if (at < 0) return;
    const step = event.key === "ArrowDown" ? 1 : event.key === "ArrowUp" ? -1 : 0;
    if (step) {
      event.preventDefault();
      ticks[Math.max(0, Math.min(ticks.length - 1, at + step))]?.focus();
    } else if (event.key === "ArrowRight" || event.key === "ArrowLeft") {
      const caret = ticks[at].parentElement?.querySelector("[data-caret]") as HTMLButtonElement | null;
      const open = caret?.getAttribute("aria-label")?.startsWith("Close");
      if (caret && (event.key === "ArrowRight") !== open) { event.preventDefault(); caret.click(); }
    }
  };
  const flip = (path: string) =>
    onTick(ticked.includes(path) ? ticked.filter((p) => p !== path) : [...ticked, path].sort());
  return (
    <div className="flex flex-col">
      <div role="tree" aria-label="folders" className="flex flex-col" onKeyDown={move}>
        {roots.error && <p className="m-0 px-[10px] text-[12.5px] text-needs-you-ink">No data folder is set up.</p>}
        {(roots.data?.folders ?? []).map((folder) => (
          <Node key={folder.path} folder={folder} depth={0} ticked={ticked} onFlip={flip} />
        ))}
      </div>
      <div aria-disabled="true" title="Not available yet"
           className="flex items-center gap-[9px] px-[10px] py-[7px] text-[13px] text-ink-3 cursor-default">
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
          <path d="M7 18h10a4 4 0 0 0 .5-7.97A6 6 0 0 0 6 9.5 4.25 4.25 0 0 0 7 18z" />
        </svg>
        <span>Cloud storage</span>
        <span className="ml-auto text-[11px]">later</span>
      </div>
    </div>
  );
}

function Node({ folder, depth, ticked, onFlip }: {
  folder: Folder; depth: number; ticked: string[]; onFlip: (path: string) => void;
}) {
  // Open down to every ticked folder, so what is ticked is in sight, including once the
  // analysis has loaded after the tree did.
  const holds = ticked.some((p) => p.startsWith(`${folder.path}/`));
  const [open, setOpen] = useState(holds);
  useEffect(() => { if (holds) setOpen(true); }, [holds]);
  const children = useQuery({
    queryKey: ["data-tree", folder.path],
    queryFn: () => get<Listing>(tree(folder.path)),
    enabled: open,
  });
  const on = ticked.includes(folder.path);
  return (
    <div role="treeitem" aria-expanded={folder.folders > 0 ? open : undefined}>
      <div className={`flex items-center gap-[2px] rounded-control pr-[6px] ${on ? "bg-now-soft" : "hover:bg-surface-2"}`}
           style={{ paddingLeft: depth * 14 }}>
        {folder.folders > 0 ? (
          <button type="button" data-caret onClick={() => setOpen(!open)} tabIndex={-1}
                  aria-label={`${open ? "Close" : "Open"} ${folder.name}`}
                  className="w-5 h-7 shrink-0 border-0 bg-transparent text-ink-3 cursor-pointer text-[10px] p-0">
            {open ? "▾" : "▸"}
          </button>
        ) : <span className="w-5 shrink-0" aria-hidden="true" />}
        <button type="button" data-tick onClick={() => onFlip(folder.path)} aria-pressed={on}
                aria-label={`${folder.name}, ${folder.files} ${folder.files === 1 ? "file" : "files"}`}
                className="flex items-center gap-2 flex-1 min-w-0 h-[30px] border-0 bg-transparent cursor-pointer
                           text-[13px] text-ink-2 text-left px-[2px]">
          <span aria-hidden="true"
                className={`w-[15px] h-[15px] shrink-0 rounded-xs border-[1.5px] flex items-center justify-center
                            ${on ? "bg-now border-now" : "border-mark"}`}>
            {on && (
              <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="var(--surface)" strokeWidth="3.5">
                <path d="M5 12l5 5 9-10" />
              </svg>
            )}
          </span>
          <span className="truncate">{folder.name}</span>
          {folder.files > 0 && <span className="ml-auto pl-[6px] text-[11.5px] text-ink-3">{folder.files}</span>}
        </button>
      </div>
      {open && (
        <div role="group">
          {(children.data?.folders ?? []).map((child) => (
            <Node key={child.path} folder={child} depth={depth + 1} ticked={ticked} onFlip={onFlip} />
          ))}
        </div>
      )}
    </div>
  );
}
