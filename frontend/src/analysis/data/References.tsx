import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { get } from "../../api/client";
import type { components } from "../../api/schema";
import { chipName } from "../../build/living/CollectionChannel";
import { useTypeNames } from "../../build/living/useTypeNames";
import { Panel } from "../../ui/Panel";
import { useBuildCanvas } from "../run/useRuns";
import { allFiles } from "./files";
import type { AnalysisData } from "./types";
import { bytes } from "./values";

type Reader = components["schemas"]["Reader"];
type File = components["schemas"]["FilesPage"]["files"][number];

const folderOf = (path: string) => path.split("/").slice(-3, -1).join("/");
const BUTTON = "h-9 px-[14px] rounded-control text-[13px] cursor-pointer";

/** **References** (#511, board 2026-11-16): one slot a study-wide input the pipeline reads, as
 *  Build's canvas has them. A slot set says its file; an open one offers the files in the ticked
 *  folders that can be one — those in a folder named for references and with the kind's
 *  extension first — and any other file by name. A reference the pipeline does not ask for yet is
 *  added by kind. Standard references, downloaded once per machine, come later (#514). */
export function References({ data, onAdd, onRemove }: {
  data: AnalysisData; onAdd: (path: string, typeId: string) => void; onRemove: (index: number) => void;
}) {
  const typeName = useTypeNames();
  const canvas = useBuildCanvas(data.draft_id);
  const files = useQuery({ queryKey: ["analysis-files", data.draft_id, data.revision], queryFn: () => allFiles(data.draft_id) });
  const readers = useQuery({ queryKey: ["data-readers"], queryFn: () => get<Reader[]>("/data/readers") });
  const wanted = [...new Set((canvas.data?.canvas?.channels ?? []).filter((c) => c.grain === "study").map((c) => c.type_id))];
  const extra = data.references.filter((r) => !wanted.includes(r.type_id)).map((r) => r.type_id);
  const slots = [...wanted, ...new Set(extra)];
  const chosen = new Set(data.references.map((r) => r.path));
  // Files a reference can be: not a sample's, not already one.
  const choices = (files.data?.files ?? []).filter((f) => !f.sample && f.recognised !== "fastq.reads" && !chosen.has(f.path));
  const set = data.references.length;

  return (
    <div className="grid gap-[14px] items-start lg:grid-cols-[minmax(0,1fr)_340px]">
      <div className="flex flex-col gap-[14px] min-w-0">
        <p className="m-0 text-[13.5px] text-ink-2">
          {wanted.length
            ? `The pipeline reads ${wanted.map((t) => chipName(typeName(t)).toLowerCase()).join(" and ")} once for every sample. ${Math.min(set, wanted.length)} of ${wanted.length} chosen.`
            : "Build has not asked for a reference yet. Add one by kind below, or build first."}
        </p>
        {files.error && <p role="alert" className="m-0 text-[13px] text-needs-you-ink">The files could not be listed.</p>}
        {slots.map((kind) => (
          <Slot key={kind} kind={kind} data={data} choices={choices} readers={readers.data ?? []}
                files={files.data?.files ?? []} onAdd={onAdd} onRemove={onRemove} />
        ))}
        <ByKind choices={choices} onAdd={onAdd} />
      </div>
      <div className="flex flex-col gap-[14px] min-w-0">
        <Panel title="Standard references" hint="later">
          <p className="m-0 px-5 pb-4 text-[12.5px] text-ink-2 leading-[1.5]">
            Genomes by name, such as GRCh38 or sacCer3, downloaded once and kept for every analysis on this machine.
          </p>
        </Panel>
      </div>
    </div>
  );
}

function Slot({ kind, data, choices, readers, files, onAdd, onRemove }: {
  kind: string; data: AnalysisData; choices: File[]; readers: Reader[]; files: File[];
  onAdd: (path: string, typeId: string) => void; onRemove: (index: number) => void;
}) {
  const typeName = useTypeNames();
  const [find, setFind] = useState("");
  const index = data.references.findIndex((r) => r.type_id === kind);
  const ref = index >= 0 ? data.references[index] : null;
  const name = typeName(kind);
  // The kind's own extension, and the family a reader groups it with (`.fasta` → `.fna`, `.fa`).
  const suffix = `.${kind.split(".").pop()}`;
  const family = readers.find((r) => r.extensions.includes(suffix))?.extensions ?? [suffix];
  const fits = (f: File) => family.some((e) => f.name.toLowerCase().replace(/\.gz$/, "").endsWith(e));
  const ranked = choices.filter(fits).sort((a, b) => Number(b.used_as === "candidate") - Number(a.used_as === "candidate"));
  const found = find.trim() ? choices.filter((f) => f.name.toLowerCase().includes(find.trim().toLowerCase())).slice(0, 8) : [];
  const size = ref ? files.find((f) => f.path === ref.path)?.size : undefined;

  return (
    <Panel title={chipName(name)} hint={ref ? "chosen" : `${family.join(" ")}`}>
      {ref ? (
        <div className="grid grid-cols-[minmax(0,1fr)_auto] gap-3 items-center px-5 py-3 border-t border-line-soft">
          <span className="flex flex-col gap-[3px] min-w-0">
            <span className="font-data text-[13px] font-semibold text-ink truncate">{ref.name}</span>
            <span className="text-[12.5px] text-ink-2">
              {[size !== undefined ? bytes(size) : null, `in ${folderOf(ref.path)}`].filter(Boolean).join(" · ")}
              {ref.origin === "ai" ? " · set by the AI" : ""}
            </span>
          </span>
          <button type="button" aria-label={`Change ${ref.name}`} onClick={() => onRemove(index)}
                  className={`${BUTTON} border border-line-2 bg-surface text-ink`}>Change</button>
        </div>
      ) : (
        <>
          {ranked.length > 0 && <div className="px-5 pb-[6px] text-[12.5px] font-semibold text-ink-3">From your folders</div>}
          {ranked.slice(0, 3).map((f) => <Candidate key={f.path} file={f} label={chipName(name).toLowerCase()} onUse={() => onAdd(f.path, kind)} />)}
          {ranked.length === 0 && <p className="m-0 px-5 pb-2 text-[13px] text-ink-3">No file in the ticked folders looks like one.</p>}
          <div className="flex flex-wrap items-center gap-[10px] px-5 py-3 border-t border-line-soft">
            <input aria-label={`Find another file for the ${name}`} placeholder="Another file in your folders" value={find}
                   onChange={(e) => setFind(e.target.value)}
                   className="flex-1 min-w-[200px] h-9 px-[10px] border border-line-2 rounded-control bg-surface text-[13px] text-ink" />
          </div>
          {found.map((f) => <Candidate key={f.path} file={f} label={chipName(name).toLowerCase()} onUse={() => onAdd(f.path, kind)} />)}
        </>
      )}
    </Panel>
  );
}

function Candidate({ file, label, onUse }: { file: File; label: string; onUse: () => void }) {
  return (
    <div data-testid="candidate" className="grid grid-cols-[minmax(0,1fr)_auto] gap-3 items-center px-5 py-[10px] border-t border-line-soft">
      <span className="flex flex-col gap-[3px] min-w-0">
        <span className="font-data text-[13px] font-semibold text-ink truncate">{file.name}</span>
        <span className="text-[12.5px] text-ink-2">in {folderOf(file.path)}{file.used_as === "candidate" ? ", a folder for references" : ""}</span>
      </span>
      <button type="button" onClick={onUse}
              className={`${BUTTON} border-0 bg-action text-on-action shadow-raise font-semibold`}>Use as the {label}</button>
    </div>
  );
}

/** A reference the pipeline does not ask for (yet), added by kind. */
function ByKind({ choices, onAdd }: { choices: File[]; onAdd: (path: string, typeId: string) => void }) {
  const typeName = useTypeNames();
  const [open, setOpen] = useState(false);
  const [path, setPath] = useState("");
  const [kind, setKind] = useState("");
  const types = useQuery({ queryKey: ["reference-types"], queryFn: () => get<string[]>("/data/reference-types"), enabled: open });
  const field = "h-9 px-2 border border-line-2 rounded-control bg-surface text-[13px] text-ink";
  if (!open) {
    return (
      <div className="flex flex-wrap items-center gap-3 px-5 py-[14px] bg-surface border border-line rounded-panel">
        <span className="text-[13px] text-ink-2">Another reference a step could use, such as a genome index?</span>
        <button type="button" onClick={() => setOpen(true)}
                className="ml-auto border-0 bg-transparent p-0 text-[12.5px] font-semibold text-now-ink cursor-pointer">Add a reference by kind</button>
      </div>
    );
  }
  return (
    <Panel title="Add a reference by kind">
      <div className="flex flex-wrap items-end gap-2 px-5 pb-4">
        <label className="flex flex-col gap-1 text-[12px] text-ink-3 min-w-[200px] flex-1">File
          <select aria-label="File" value={path} onChange={(e) => setPath(e.target.value)} className={field}>
            <option value="">Choose a file in your folders</option>
            {choices.map((f) => <option key={f.path} value={f.path}>{f.name}</option>)}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-[12px] text-ink-3 min-w-[200px] flex-1">Kind
          <select aria-label="Kind" value={kind} onChange={(e) => setKind(e.target.value)} className={field}>
            <option value="">What it is</option>
            {(types.data ?? []).map((t) => <option key={t} value={t}>{typeName(t)}</option>)}
          </select>
        </label>
        <button type="button" disabled={!path || !kind} onClick={() => { onAdd(path, kind); setPath(""); setKind(""); setOpen(false); }}
                className={`${BUTTON} border-0 bg-action text-on-action shadow-raise font-semibold disabled:opacity-50`}>Add reference</button>
      </div>
    </Panel>
  );
}
