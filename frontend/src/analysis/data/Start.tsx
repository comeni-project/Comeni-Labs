import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router";

import { get } from "../../api/client";
import type { components } from "../../api/schema";
import { useTypeNames } from "../../build/living/useTypeNames";
import { Panel } from "../../ui/Panel";

type Listing = components["schemas"]["FolderListing"];
type Folder = components["schemas"]["Folder"];
type Reader = components["schemas"]["Reader"];

const tree = (path: string | null) => (path === null ? "/data/tree" : `/data/tree?path=${encodeURIComponent(path)}`);
const words = (id: string) => id.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase());
const ROW = "grid grid-cols-[28px_minmax(0,1fr)] sm:grid-cols-[28px_minmax(0,1fr)_64px_minmax(0,1.3fr)] gap-x-3 gap-y-1 items-center px-5";

/** **Data before anything is read** (board 2026-11-16): the folders under the data roots on the
 *  page, each saying what its files look like, ticked and then read together; beside them, what
 *  Comeni reads. Opening a folder lists its subfolders; a folder's own files are what a tick reads. */
export function Start({ ticked, onTick, onCancel }: {
  ticked: string[]; onTick: (folders: string[]) => void; onCancel?: () => void;
}) {
  const roots = useQuery({ queryKey: ["data-tree", null], queryFn: () => get<Listing>(tree(null)) });
  const [chosen, setChosen] = useState<string[]>(ticked);
  const [find, setFind] = useState("");
  const [files, setFiles] = useState<Record<string, number>>({});
  const flip = (folder: Folder) => {
    setFiles((f) => ({ ...f, [folder.path]: folder.files }));
    setChosen((c) => (c.includes(folder.path) ? c.filter((p) => p !== folder.path) : [...c, folder.path].sort()));
  };
  const total = chosen.reduce((n, p) => n + (files[p] ?? 0), 0);
  const only = (roots.data?.folders ?? []).length === 1;

  return (
    <div className="grid gap-[14px] items-start lg:grid-cols-[minmax(0,1fr)_340px]">
      <Panel title="Folders" actions={
        <input aria-label="Find a folder" placeholder="Find a folder" value={find} onChange={(e) => setFind(e.target.value)}
               className="h-8 w-[220px] max-w-full px-[10px] border border-line-2 rounded-control bg-surface text-[13px] text-ink" />
      }>
        <div className={`${ROW} hidden sm:grid py-2 border-t border-line-soft text-[12px] font-semibold text-ink-3`}>
          <span /><span>Folder</span><span>Files</span><span>Looks like</span>
        </div>
        {roots.error && <p className="m-0 px-5 py-3 text-[13px] text-needs-you-ink">No data folder is set up on this installation.</p>}
        {(roots.data?.folders ?? []).map((folder) => (
          <Row key={folder.path} folder={folder} depth={0} open={only} chosen={chosen} find={find.trim().toLowerCase()} onFlip={flip} />
        ))}
        <footer className="flex flex-wrap items-center gap-3 px-5 py-[14px] border-t border-line-soft">
          <span className="text-[13px] text-ink-2">
            {chosen.length ? <><b className="text-ink">{chosen.length} {chosen.length === 1 ? "folder" : "folders"}</b>{total ? ` · ${total} files` : ""}</>
              : "Tick the folders that hold this analysis's data."}
          </span>
          {onCancel && (
            <button type="button" onClick={onCancel}
                    className="ml-auto h-10 px-[14px] rounded-control border border-line-2 bg-surface text-[13px] text-ink cursor-pointer">Cancel</button>
          )}
          <button type="button" disabled={!chosen.length} onClick={() => onTick(chosen)}
                  className={`${onCancel ? "" : "ml-auto "}h-10 px-[18px] rounded-control border-0 bg-action text-on-action shadow-raise text-[14px] font-semibold cursor-pointer disabled:opacity-50`}>
            Read these folders
          </button>
        </footer>
      </Panel>
      <div className="flex flex-col gap-[14px] min-w-0">
        <Readers />
        <Panel title="Elsewhere">
          <div className="flex flex-col gap-2 px-5 pb-4 text-[13px] text-ink-3">
            <span className="flex justify-between">Cloud storage<span className="text-[12px]">later</span></span>
            <span className="flex justify-between">Public data by accession<span className="text-[12px]">later</span></span>
          </div>
        </Panel>
      </div>
    </div>
  );
}

function Row({ folder, depth, open: startOpen, chosen, find, onFlip }: {
  folder: Folder; depth: number; open: boolean; chosen: string[]; find: string; onFlip: (f: Folder) => void;
}) {
  const typeName = useTypeNames();
  // Open down to every ticked folder, so what is ticked is in sight.
  const [open, setOpen] = useState(startOpen || chosen.some((p) => p.startsWith(`${folder.path}/`)));
  const inside = useQuery({ queryKey: ["data-tree", folder.path], queryFn: () => get<Listing>(tree(folder.path)), enabled: open });
  const on = chosen.includes(folder.path);
  const shown = !find || folder.name.toLowerCase().includes(find);
  const looks = folder.looks_like ?? [];
  return (
    <>
      {shown && (
        <div className={`${ROW} py-[10px] border-t border-line-soft ${on ? "bg-now-soft" : ""}`}>
          {folder.files > 0
            ? <input type="checkbox" checked={on} aria-label={`Use ${folder.name}`} onChange={() => onFlip(folder)}
                     className="w-4 h-4 accent-[var(--now)] cursor-pointer" />
            : <span />}
          <span className="flex items-center gap-2 min-w-0" style={{ paddingLeft: depth * 20 }}>
            {folder.folders > 0 ? (
              <button type="button" aria-label={`${open ? "Close" : "Open"} ${folder.name}`} onClick={() => setOpen(!open)}
                      className="w-5 h-5 grid place-items-center border-0 bg-transparent text-ink-3 cursor-pointer">
                <svg aria-hidden="true" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3"
                     style={{ transform: open ? "rotate(90deg)" : undefined }}><path d="M9 6l6 6-6 6" /></svg>
              </button>
            ) : <span className="w-5" />}
            <span className={`truncate text-[13.5px] font-semibold ${on ? "text-now-ink" : "text-ink"}`}>{folder.name}</span>
          </span>
          <span className="hidden sm:block text-[13px] text-ink-2">{folder.files}</span>
          <span className="col-start-2 sm:col-start-auto flex flex-wrap gap-[6px]">
            {looks.length ? looks.map((l) => (
              <span key={l.type_id} className="px-2 py-[2px] rounded-xs border border-line bg-surface-2 text-[12px] text-ink-2">
                {l.count === 1 ? typeName(l.type_id) : `${l.count} · ${typeName(l.type_id)}`}
              </span>
            )) : <span className="text-[12px] text-ink-3">{folder.files ? "nothing Comeni reads yet" : folder.folders ? `${folder.folders} folders` : "empty"}</span>}
          </span>
        </div>
      )}
      {open && (inside.data?.folders ?? []).map((child) => (
        <Row key={child.path} folder={child} depth={depth + 1} open={false} chosen={chosen} find={find} onFlip={onFlip} />
      ))}
    </>
  );
}

function Readers() {
  const typeName = useTypeNames();
  const readers = useQuery({ queryKey: ["data-readers"], queryFn: () => get<Reader[]>("/data/readers") });
  const references = useQuery({ queryKey: ["reference-types"], queryFn: () => get<string[]>("/data/reference-types") });
  return (
    <Panel title="What Comeni reads">
      <div className="flex flex-col px-5 pb-4">
        {readers.error && <p className="m-0 text-[12.5px] text-needs-you-ink">The readers could not be listed.</p>}
        {(readers.data ?? []).map((r) => (
          <div key={r.id} className="flex flex-col gap-[2px] py-[10px] border-b border-line-soft">
            <span className="text-[13.5px] font-semibold text-ink">{typeName(r.type_id)}</span>
            <span className="font-data text-[11.5px] text-ink-3">{r.extensions.join(" ")}{r.compressed.length ? `, and ${r.compressed.join(" ")}` : ""}</span>
            {r.measures.length > 0 && <span className="text-[12.5px] text-ink-2">{words(r.measures.map((m) => m.replace(/_/g, " ")).join(", "))}</span>}
          </div>
        ))}
        {(references.data ?? []).length > 0 && (
          <div className="flex flex-col gap-[2px] py-[10px] border-b border-line-soft">
            <span className="text-[13.5px] font-semibold text-ink">References</span>
            <span className="text-[12.5px] text-ink-2">{(references.data ?? []).map(typeName).join(", ")}</span>
          </div>
        )}
        <Link to="/forge" className="mt-3 text-[12.5px] font-semibold text-now-ink no-underline">Another format? Add a reader in the Forge</Link>
      </div>
    </Panel>
  );
}
