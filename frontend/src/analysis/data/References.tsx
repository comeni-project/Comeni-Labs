import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { get } from "../../api/client";
import type { components } from "../../api/schema";
import { Panel } from "../../ui/Panel";
import type { AnalysisData } from "./types";

type FilesPage = components["schemas"]["FilesPage"];

/** Data · References (#511): the study-wide files a pipeline reads once, such as a genome and its
 *  annotation. Standard references, downloaded once per machine, come later (#514). */
export function References({ data, onAdd, onRemove }: {
  data: AnalysisData; onAdd: (path: string, typeId: string) => void; onRemove: (index: number) => void;
}) {
  const types = useQuery({ queryKey: ["reference-types"], queryFn: () => get<string[]>("/data/reference-types") });
  const files = useQuery({
    queryKey: ["analysis-files", data.draft_id, data.revision],
    queryFn: () => get<FilesPage>(`/data/${encodeURIComponent(data.draft_id)}/files?limit=1000`),
  });
  const [path, setPath] = useState("");
  const [kind, setKind] = useState("");
  const named = new Set(data.references.map((r) => r.path));
  // Any file in the ticked folders that is not reads: a reference is one of those.
  const choices = (files.data?.files ?? []).filter((f) => !named.has(f.path) && f.recognised !== "fastq.reads");
  const field = "h-8 px-2 border border-line-2 rounded-control bg-surface text-[13px] text-ink";

  return (
    <div className="flex flex-col gap-4">
      <Panel title="References" hint="one file each, for the whole analysis">
        {data.references.length === 0 && <p className="m-0 px-5 pb-4 text-[13px] text-ink-3">None yet.</p>}
        {data.references.map((ref, index) => (
          <div key={ref.path} className="flex items-center gap-3 px-5 py-[10px] border-t border-line-soft text-[13px]">
            <span className="font-data text-[12.5px] text-ink">{ref.name}</span>
            <span className="text-ink-3">{ref.type_id}</span>
            <button type="button" aria-label={`Remove ${ref.name}`} onClick={() => onRemove(index)}
                    className="ml-auto h-7 px-[10px] rounded-control border border-line-2 bg-surface text-[12px] text-ink-2 cursor-pointer">
              Remove
            </button>
          </div>
        ))}
      </Panel>
      <div className="grid gap-4 md:grid-cols-2">
        <Panel title="From a file">
          <div className="flex flex-col gap-2 px-5 pb-4">
            <label className="flex flex-col gap-1 text-[12px] text-ink-3">File
              <select aria-label="File" value={path} onChange={(e) => setPath(e.target.value)} className={field}>
                <option value="">Choose a file in your folders</option>
                {choices.map((f) => <option key={f.path} value={f.path}>{f.name}</option>)}
              </select>
            </label>
            <label className="flex flex-col gap-1 text-[12px] text-ink-3">Kind
              <select aria-label="Kind" value={kind} onChange={(e) => setKind(e.target.value)} className={field}>
                <option value="">What it is</option>
                {(types.data ?? []).map((t) => <option key={t} value={t}>{t}</option>)}
              </select>
            </label>
            <button type="button" disabled={!path || !kind} onClick={() => { onAdd(path, kind); setPath(""); setKind(""); }}
                    className="self-start h-8 px-3 rounded-control bg-action text-on-action shadow-raise border-0 text-[12.5px]
                               font-semibold cursor-pointer disabled:opacity-50">
              Add reference
            </button>
            <span className="text-[12px] text-ink-3">The file stays where it is. Tick its folder in Folders first.</span>
          </div>
        </Panel>
        <Panel title="Standard" hint="later">
          <p className="m-0 px-5 pb-4 text-[13px] text-ink-3">
            Standard references are downloaded once and kept for every analysis on this machine.
          </p>
        </Panel>
      </div>
    </div>
  );
}
