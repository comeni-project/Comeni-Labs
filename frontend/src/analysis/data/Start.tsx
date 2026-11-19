import { useQuery } from "@tanstack/react-query";
import { useId, useState } from "react";
import { Link } from "react-router";

import { get } from "../../api/client";
import type { components } from "../../api/schema";
import { useTypeNames } from "../../build/living/useTypeNames";
import { Panel } from "../../ui/Panel";
import { FileLocation } from "./FileLocation";

type Listing = components["schemas"]["FolderListing"];
type Folder = components["schemas"]["Folder"];
type Reader = components["schemas"]["Reader"];

const tree = (path: string | null, offset = 0) => (path === null ? "/data/tree" : `/data/tree?path=${encodeURIComponent(path)}${offset ? `&file_offset=${offset}` : ""}`);
const words = (id: string) => id.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase());
const ROW = "grid grid-cols-[44px_minmax(0,1fr)] sm:grid-cols-[44px_minmax(0,1fr)_64px_minmax(0,1.3fr)] gap-x-3 gap-y-1 items-center px-5";

/** **Data before anything is read** (board 2026-11-16): the folders under the data roots on the
 *  page, each saying what its files look like, ticked and then read together; beside them, what
 *  Comeni reads. Opening a folder lists its subfolders; a folder's own files are what a tick reads. */
export function Start({ ticked, onTick, onCancel, usedFiles = [] }: {
  ticked: string[]; onTick: (folders: string[]) => void; onCancel?: () => void;
  usedFiles?: string[];
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
               className="h-[32px] w-[220px] max-w-full px-[10px] border border-line-2 rounded-control bg-surface text-[13px] text-ink" />
      }>
        <div className={`${ROW} hidden sm:grid py-2 border-t border-line-soft text-[12px] font-semibold text-ink-3`}>
          <span /><span>Folder / file</span><span>Files / size</span><span>Looks like</span>
        </div>
        {roots.error && <p className="m-0 px-5 py-3 text-[13px] text-needs-you-ink">No data folder is set up on this installation.</p>}
        {(roots.data?.folders ?? []).map((folder) => (
          <Row key={folder.path} folder={folder} depth={0} open={only} chosen={chosen} find={find.trim().toLowerCase()} onFlip={flip} usedFiles={usedFiles} />
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

function Row({ folder, depth, open: startOpen, chosen, find, onFlip, usedFiles }: {
  folder: Folder; depth: number; open: boolean; chosen: string[]; find: string; onFlip: (f: Folder) => void;
  usedFiles: string[];
}) {
  const typeName = useTypeNames();
  const selectionId = useId();
  // Open down to every ticked folder, so what is ticked is in sight.
  const [open, setOpen] = useState(startOpen || chosen.some((p) => p.startsWith(`${folder.path}/`)));
  const [fileOffset, setFileOffset] = useState(0);
  const inside = useQuery({ queryKey: ["data-tree", folder.path, fileOffset], queryFn: () => get<Listing>(tree(folder.path, fileOffset)), enabled: open });
  const on = chosen.includes(folder.path);
  const shown = !find || folder.name.toLowerCase().includes(find);
  const looks = folder.looks_like ?? [];
  return (
    <>
      {shown && (
        <div className={`${ROW} min-h-[52px] py-[4px] border-t border-line-soft ${on ? "bg-now-soft" : ""}`}>
          {folder.files > 0
            ? <label className="relative grid place-items-center w-[44px] h-[44px] rounded-control cursor-pointer hover:bg-hover">
                <input id={selectionId} type="checkbox" checked={on} aria-label={`Use ${folder.name}`} onChange={() => onFlip(folder)}
                       className="appearance-none m-0 w-[22px] h-[22px] rounded-xs border-2 border-ink-3 bg-surface
                                  checked:bg-now checked:border-now cursor-pointer focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-now" />
                {on && <svg aria-hidden="true" width="16" height="16" viewBox="0 0 24 24" fill="none"
                            stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"
                            className="absolute pointer-events-none text-surface"><path d="m5 12 4 4 10-10" /></svg>}
              </label>
            : <span />}
          <span className="flex items-center gap-2 min-w-0" style={{ paddingLeft: depth * 20 }}>
            {folder.folders > 0 || folder.files > 0 ? (
              <button type="button" aria-label={`${open ? "Close" : "Open"} ${folder.name}`} aria-expanded={open} onClick={() => setOpen(!open)}
                      className="w-[32px] h-11 shrink-0 grid place-items-center border-0 rounded-control bg-transparent text-ink-3 hover:bg-hover cursor-pointer">
                <svg aria-hidden="true" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3"
                     style={{ transform: open ? "rotate(90deg)" : undefined }}><path d="M9 6l6 6-6 6" /></svg>
              </button>
            ) : <span className="w-5" />}
            {folder.files > 0 ? (
              <label htmlFor={selectionId} className={`flex-1 min-w-0 truncate py-[12px] text-[13.5px] font-semibold cursor-pointer ${on ? "text-now-ink" : "text-ink"}`}>
                {folder.name}
              </label>
            ) : <span className="truncate text-[13.5px] font-semibold text-ink">{folder.name}</span>}
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
        <Row key={child.path} folder={child} depth={depth + 1} open={false} chosen={chosen} find={find} onFlip={onFlip} usedFiles={usedFiles} />
      ))}
      {open && inside.isPending && <p role="status" className="m-0 px-5 py-2 text-secondary text-ink-3">Loading files…</p>}
      {open && inside.isError && <p role="alert" className="m-0 px-5 py-2 text-secondary text-needs-you-ink">Could not list this folder. <button type="button" onClick={() => void inside.refetch()} className="connection-text-button">Retry</button></p>}
      {open && (inside.data?.entries ?? []).filter((file) => !find || shown || file.name.toLowerCase().includes(find)).map((file) => {
        const used = usedFiles.includes(`${folder.path}/${file.name}`);
        return <div key={file.name} data-testid="folder-file" className={`${ROW} min-h-10 py-2 border-t border-line-soft bg-surface-2`}>
          <span />
          <span className="min-w-0 flex items-center gap-2" style={{ paddingLeft: (depth + 1) * 20 + 32 }}>
            <svg aria-hidden width="14" height="16" viewBox="0 0 16 18" fill="none" stroke="currentColor" className="shrink-0 text-ink-3"><path d="M3 1h6l4 4v12H3zM9 1v5h4" /></svg>
            <FileLocation path={`${folder.path}/${file.name}`} />
          </span>
          <span className="hidden sm:block font-data text-[11px] text-ink-3">{file.size < 1024 ? `${file.size} B` : file.size < 1048576 ? `${(file.size / 1024).toFixed(1)} KB` : `${(file.size / 1048576).toFixed(1)} MB`}</span>
          <span className="col-start-2 sm:col-start-auto flex flex-wrap gap-2 text-[12px] text-ink-2">
            {used && <span className="rounded-control px-2 bg-done-soft text-done-ink">Used by this pipeline</span>}
            <span>{file.type_id ? typeName(file.type_id) : "Unrecognised format"}</span>
          </span>
        </div>;
      })}
      {open && (inside.data?.files ?? 0) > 200 && <div className="flex items-center justify-end gap-3 px-5 py-2 text-secondary text-ink-2">
        <span>Files {fileOffset + 1}–{Math.min(fileOffset + 200, inside.data!.files)} of {inside.data!.files}</span>
        <button type="button" disabled={!fileOffset} onClick={() => setFileOffset((n) => Math.max(0, n - 200))} className="connection-button">Previous</button>
        <button type="button" disabled={fileOffset + 200 >= inside.data!.files} onClick={() => setFileOffset((n) => n + 200)} className="connection-button">Next</button>
      </div>}
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
        {(readers.data ?? []).filter((r) => r.by === "code").map((r) => (
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
