import { useMemo, useState } from "react";

import { DataTable, type Column } from "../../ui/DataTable";
import { Panel } from "../../ui/Panel";
import { Segmented } from "../../ui/Segmented";
import { SourceTag } from "../../ui/SourceTag";
import type { AnalysisData } from "./types";

type Sample = AnalysisData["samples"][number];

const words = (id: string) => id.replace(/[_.]/g, " ").replace(/^./, (c) => c.toUpperCase());
const base = (path: string) => path.split("/").pop() ?? path;
const plain = (value: unknown) => value === true ? "yes" : value === false ? "no" : value == null ? "—" : String(value);

/** Data · Samples (#511): how the files were read into samples, as examples you can confirm or
 *  change, and the samples table. Its columns follow the kind of data. */
export function Samples({ data, setRule, confirmRule, undoFix, setColumn }: {
  data: AnalysisData;
  setRule: (pattern: string | null) => void;
  confirmRule: () => void;
  undoFix: (index: number) => void;
  setColumn: (name: string, values: Record<string, string>) => void;
}) {
  const [filter, setFilter] = useState<"all" | "check">("all");
  const [find, setFind] = useState("");
  const [adding, setAdding] = useState(false);
  const flagged = useMemo(() => new Set(data.checks.map((c) => c.sample)), [data.checks]);
  const rows = data.samples.filter((s) => (filter === "all" || flagged.has(s.name))
    && s.name.toLowerCase().includes(find.trim().toLowerCase()));

  const paired = data.samples.filter((s) => s.files.length === 2).length > data.samples.length / 2;
  const facts = [...new Set(data.samples.flatMap((s) => s.facts.map((f) => f.measurement)))].sort();
  const columns: Column<Sample>[] = [
    { id: "name", header: "Sample", width: "minmax(140px,1.2fr)", cell: (s) => (
      <span className="flex items-center gap-2 min-w-0">
        <span className={`truncate font-medium ${s.left_out ? "text-ink-3 line-through" : "text-ink"}`}>{s.name}</span>
        {s.left_out && <BringBack sample={s.name} data={data} undoFix={undoFix} />}
      </span>
    ) },
    ...(paired
      ? [{ id: "r1", header: "Read 1", cell: (s: Sample) => <Mono>{base(s.files[0] ?? "")}</Mono> },
         { id: "r2", header: "Read 2", cell: (s: Sample) => <Mono>{s.files[1] ? base(s.files[1]) : "—"}</Mono> }]
      : [{ id: "file", header: "File", cell: (s: Sample) => <Mono>{s.files.map(base).join(", ")}</Mono> }]),
    ...facts.map((m) => ({ id: `fact-${m}`, header: words(m), width: "110px", cell: (s: Sample) => (
      <Mono>{plain(s.facts.find((f) => f.measurement === m)?.value)}</Mono>
    ) })),
    ...Object.entries(data.columns).map(([name, values]) => ({ id: `col-${name}`, header: name, width: "130px",
      cell: (s: Sample) => (
        <input aria-label={`${name} for ${s.name}`} defaultValue={values[s.name] ?? ""}
               onBlur={(e) => { if ((values[s.name] ?? "") !== e.target.value.trim())
                 setColumn(name, { ...values, [s.name]: e.target.value.trim() }); }}
               className="w-full h-7 px-2 border border-line rounded-control bg-surface text-[12.5px] text-ink" />
      ) })),
  ];

  return (
    <div className="flex flex-col gap-4">
      <ReadingRule data={data} setRule={setRule} confirmRule={confirmRule} />
      <Panel title="Samples" actions={
        <span className="flex items-center gap-2 flex-wrap">
          <Segmented<"all" | "check"> label="Show" value={filter} onChange={setFilter}
                                     options={[{ id: "all", label: "All" }, { id: "check", label: `To check · ${flagged.size}` }]} />
          <input aria-label="Find a sample" placeholder="Find a sample" value={find} onChange={(e) => setFind(e.target.value)}
                 className="h-8 w-[180px] px-[10px] border border-line-2 rounded-control bg-surface text-[13px] text-ink" />
          {adding ? <AddColumn onAdd={(name) => { setColumn(name, {}); setAdding(false); }} />
            : <button type="button" onClick={() => setAdding(true)}
                      className="h-8 px-3 rounded-control border border-line-2 bg-surface text-[12.5px] text-now-ink cursor-pointer">
                + Add column
              </button>}
        </span>
      }>
        <DataTable label="Samples" rows={rows} columns={columns} rowKey={(s) => s.name}
                   height={Math.min(560, 38 * Math.max(rows.length, 3))} highlight={(s) => flagged.has(s.name)} />
        <p className="m-0 px-5 py-3 border-t border-line-soft text-[12.5px] text-ink-3">
          Columns follow the kind of data: paired reads get read 1 and read 2, assemblies one file. Add a column for a
          condition or a batch, or for a fact nothing measured, such as strandedness.
        </p>
      </Panel>
    </div>
  );
}

function Mono({ children }: { children: React.ReactNode }) {
  return <span className="font-data text-[12px] text-ink-2 truncate">{children}</span>;
}

function BringBack({ sample, data, undoFix }: { sample: string; data: AnalysisData; undoFix: (i: number) => void }) {
  const index = data.fixes.findIndex((f) => f.kind === "leave_out" && f.sample === sample);
  if (index < 0) return null;
  return (
    <button type="button" onClick={() => undoFix(index)} aria-label={`Bring ${sample} back`}
            className="shrink-0 h-6 px-2 rounded-control border border-line-2 bg-surface text-[11.5px] text-ink-2 cursor-pointer">
      left out · undo
    </button>
  );
}

function AddColumn({ onAdd }: { onAdd: (name: string) => void }) {
  const [name, setName] = useState("");
  return (
    <span className="flex items-center gap-1">
      <input aria-label="New column" placeholder="condition" value={name} onChange={(e) => setName(e.target.value)}
             className="h-8 w-[130px] px-2 border border-line-2 rounded-control bg-surface text-[13px] text-ink" />
      <button type="button" disabled={!name.trim()} onClick={() => onAdd(name.trim())}
              className="h-8 px-3 rounded-control border border-line-2 bg-surface text-[12.5px] text-ink cursor-pointer">Add</button>
    </span>
  );
}

function ReadingRule({ data, setRule, confirmRule }: {
  data: AnalysisData; setRule: (pattern: string | null) => void; confirmRule: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const [pattern, setPattern] = useState(data.rule.pattern ?? "{sample}_R{read}.fastq.gz");
  const { samples, unfit } = data.rule_result;
  const paired = data.samples.some((s) => s.files.length === 2);
  return (
    <section aria-label="How the samples were read"
             className="flex flex-col gap-[10px] px-5 py-4 bg-surface border border-line rounded-panel">
      <div className="flex items-center gap-2">
        <SourceTag source={data.rule.origin === "ai" ? "ai" : data.rule.origin === "you" ? "you" : "rule"} />
        <span className="text-[15px] font-semibold text-ink">How the samples were read</span>
        {data.rule.confirmed && <span className="text-[12.5px] text-done-ink">· confirmed</span>}
      </div>
      <div className="grid grid-cols-[auto_auto_1fr] gap-x-3 gap-y-1 items-center text-[13px]">
        {data.scan.examples.map(([file, sample, read]) => (
          <span key={file} data-testid="rule-example" className="contents">
            <span className="font-data text-[12px] text-ink-2">{file}</span>
            <span className="text-ink-3">→</span>
            <span>sample <b>{sample}</b>{read ? `, read ${read}` : ""}</span>
          </span>
        ))}
      </div>
      <span className="text-[13px] text-ink-2">
        {data.rule.pattern ? <>Rule <span className="font-data">{data.rule.pattern}</span>: </> : "Paired by name: "}
        <b>{samples} samples</b>{paired ? ", paired" : ""}.
        {unfit > 0 && ` ${unfit} ${unfit === 1 ? "file did" : "files did"} not fit the pattern.`}
      </span>
      {editing ? (
        <span className="flex items-center gap-2 flex-wrap">
          <input aria-label="Reading rule" value={pattern} onChange={(e) => setPattern(e.target.value)}
                 className="h-8 w-[320px] max-w-full px-[10px] border border-line-2 rounded-control bg-surface font-data text-[12.5px] text-ink" />
          <button type="button" onClick={() => { setRule(pattern.trim()); setEditing(false); }}
                  className="h-8 px-3 rounded-control bg-action text-on-action shadow-raise border-0 text-[12.5px] font-semibold cursor-pointer">
            Use this rule
          </button>
          {data.rule.pattern && (
            <button type="button" onClick={() => { setRule(null); setEditing(false); }}
                    className="h-8 px-3 rounded-control border border-line-2 bg-surface text-[12.5px] text-ink cursor-pointer">
              Pair by name again
            </button>
          )}
          <span className="text-[12px] text-ink-3">{"{sample}"} is the sample's name, {"{read}"} is 1 or 2.</span>
        </span>
      ) : (
        <span className="flex gap-2">
          {!data.rule.confirmed && (
            <button type="button" onClick={confirmRule}
                    className="h-[30px] px-[11px] rounded-control border border-line-2 bg-surface text-[12.5px] text-ink cursor-pointer">
              Looks right
            </button>
          )}
          <button type="button" onClick={() => setEditing(true)}
                  className="h-[30px] px-[11px] rounded-control border border-line-2 bg-surface text-[12.5px] text-ink cursor-pointer">
            Change the rule
          </button>
        </span>
      )}
    </section>
  );
}
