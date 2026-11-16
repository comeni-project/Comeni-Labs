import { useMemo, useState } from "react";

import { DataTable, type Column } from "../../ui/DataTable";
import { Panel } from "../../ui/Panel";
import { Segmented } from "../../ui/Segmented";
import { SourceTag } from "../../ui/SourceTag";
import { useTypeNames } from "../../build/living/useTypeNames";
import type { AnalysisData } from "./types";
import { plain } from "./values";

type Sample = AnalysisData["samples"][number];

const words = (id: string) => id.replace(/[_.]/g, " ").replace(/^./, (c) => c.toUpperCase());
const base = (path: string) => path.split("/").pop() ?? path;
/** Data · Samples (#511): how the files were read into samples, as examples you can confirm or
 *  change, and the samples table. Its columns follow the kind of data. */
export function Samples({ data, setRule, confirmRule, undoFix, setCell, addColumn }: {
  data: AnalysisData;
  /** Resolves once the rule is saved; rejects when it is refused, and the editor stays open. */
  setRule: (pattern: string | null) => Promise<unknown>;
  confirmRule: () => void;
  undoFix: (index: number) => void;
  setCell: (column: string, sample: string, value: string) => void;
  addColumn: (name: string) => void;
}) {
  const typeName = useTypeNames();
  const [filter, setFilter] = useState<"all" | "check">("all");
  const [find, setFind] = useState("");
  const [adding, setAdding] = useState(false);
  const [showRule, setShowRule] = useState(false);
  const flagged = useMemo(() => new Set(data.checks.map((c) => c.sample)), [data.checks]);
  // Flagged for one measurement, so only that column's bar is amber (an assembly odd in its
  // contigs is not odd in its length).
  const odd = useMemo(() => new Set(data.checks.map((c) => `${c.sample}|${c.measurement ?? ""}`)), [data.checks]);
  // **One tab a kind of data** (board 2026-11-16): reads and assemblies have different columns.
  const kinds = [...new Set(data.samples.map((s) => s.type_id).filter((t): t is string => !!t))].sort();
  const [picked, setKind] = useState<string | null>(null);
  const count = (k: string) => data.samples.filter((s) => s.type_id === k).length;
  const most = [...kinds].sort((a, b) => count(b) - count(a))[0] ?? null;
  const kind = picked && kinds.includes(picked) ? picked : most;
  const ofKind = kinds.length > 1 ? data.samples.filter((s) => s.type_id === kind) : data.samples;
  const rows = ofKind.filter((s) => (filter === "all" || flagged.has(s.name))
    && s.name.toLowerCase().includes(find.trim().toLowerCase()));

  const paired = ofKind.filter((s) => s.files.length === 2).length > ofKind.length / 2;
  const facts = [...new Set(ofKind.flatMap((s) => s.facts.map((f) => f.measurement)))].sort();
  const units = Object.fromEntries(data.summary.compare_by.map((c) => [c.measurement, c.unit]));
  const top = Object.fromEntries(facts.map((m) => [m, Math.max(0, ...ofKind.map((s) => {
    const v = s.facts.find((f) => f.measurement === m)?.value;
    return typeof v === "number" ? v : 0;
  }))]));
  // The rule shows itself while the AI's pattern waits for you, or files did not fit it.
  const ruleOpen = showRule || (data.rule.origin === "ai" && !data.rule.confirmed) || data.rule_result.unfit > 0;
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
    ...facts.map((m) => ({ id: `fact-${m}`, header: words(m), width: top[m] > 0 ? "170px" : "110px", cell: (s: Sample) => {
      const value = s.facts.find((f) => f.measurement === m)?.value;
      if (typeof value !== "number" || top[m] <= 0) return <Mono>{plain(value, units[m])}</Mono>;
      const amber = odd.has(`${s.name}|${m}`);
      return (
        <span className="flex items-center gap-2 min-w-0">
          <span aria-hidden="true" className="shrink-0 w-[72px] h-[6px] rounded-full bg-surface-2 flex overflow-hidden">
            <span data-testid="fact-bar" className={`rounded-full ${amber ? "bg-measured" : "bg-now-mid"}`}
                  style={{ width: `${Math.max(4, (100 * value) / top[m])}%` }} />
          </span>
          <Mono>{plain(value, units[m])}</Mono>
        </span>
      );
    } })),
    ...Object.entries(data.columns).map(([name, values]) => ({ id: `col-${name}`, header: name, width: "130px",
      cell: (s: Sample) => (
        <input aria-label={`${name} for ${s.name}`} defaultValue={values[s.name] ?? ""}
               onBlur={(e) => { if ((values[s.name] ?? "") !== e.target.value.trim())
                 setCell(name, s.name, e.target.value.trim()); }}
               className="w-full h-7 px-2 border border-line rounded-control bg-surface text-[12.5px] text-ink" />
      ) })),
  ];

  return (
    <div className="flex flex-col gap-4">
      {ruleOpen && <ReadingRule data={data} setRule={setRule} confirmRule={confirmRule} />}
      <Panel title="Samples" hint={
        <span className="flex items-center gap-2 flex-wrap">
          {kinds.length === 1 && <span className="px-2 py-[1px] rounded-xs border border-line bg-surface-2 text-[12px] text-ink-2">{typeName(kinds[0])}</span>}
          <span>{data.rule.pattern ? `by the rule ${data.rule.pattern}` : paired ? "read 1 and 2 from the file names" : "one file each, named by the file"}</span>
          {!ruleOpen && (
            <button type="button" onClick={() => setShowRule(true)}
                    className="border-0 bg-transparent p-0 text-[12.5px] font-semibold text-now-ink cursor-pointer">How</button>
          )}
        </span>
      } actions={
        <span className="flex items-center gap-2 flex-wrap">
          {kinds.length > 1 && (
            <Segmented<string> label="Kind of data" value={kind ?? ""} onChange={setKind}
                               options={kinds.map((k) => ({ id: k, label: `${typeName(k)} · ${count(k)}` }))} />
          )}
          <Segmented<"all" | "check"> label="Show" value={filter} onChange={setFilter}
                                     options={[{ id: "all", label: "All" }, { id: "check", label: `To check · ${flagged.size}` }]} />
          <input aria-label="Find a sample" placeholder="Find a sample" value={find} onChange={(e) => setFind(e.target.value)}
                 className="h-8 w-[180px] px-[10px] border border-line-2 rounded-control bg-surface text-[13px] text-ink" />
          {adding ? <AddColumn onAdd={(name) => {
            // A column that exists is not added again: its values stay.
            if (!(name in data.columns)) addColumn(name);
            setAdding(false);
          }} />
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
    <>
    {data.fixes[index].by === "ai" && <SourceTag source="ai" />}
    <button type="button" onClick={() => undoFix(index)} aria-label={`Bring ${sample} back`}
            className="shrink-0 h-6 px-2 rounded-control border border-line-2 bg-surface text-[11.5px] text-ink-2 cursor-pointer">
      left out · undo
    </button>
    </>
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
  data: AnalysisData; setRule: (pattern: string | null) => Promise<unknown>; confirmRule: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const [pattern, setPattern] = useState(data.rule.pattern ?? "{sample}_R{read}.fastq.gz");
  const { samples, unfit } = data.rule_result;
  const paired = data.samples.filter((s) => s.files.length === 2).length > data.samples.length / 2;
  return (
    <section aria-label="How the samples were read"
             className="flex flex-col gap-[10px] px-5 py-4 bg-surface border border-line rounded-panel">
      <div className="flex items-center gap-2">
        {/* AI until the person keeps it: confirmed, it is theirs. */}
        <SourceTag source={data.rule.origin === "ai" && !data.rule.confirmed ? "ai"
          : data.rule.origin === "rule" ? "rule" : "you"} />
        <span className="text-[15px] font-semibold text-ink">How the samples were read</span>
        {data.rule.confirmed && <span className="text-[12.5px] text-done-ink">· confirmed</span>}
      </div>
      {data.rule.reason && <span className="text-[12.5px] text-ink-3">{data.rule.reason}</span>}
      <div className="grid grid-cols-[minmax(0,auto)_auto_minmax(0,1fr)] gap-x-3 gap-y-1 items-center text-[13px]">
        {data.scan.examples.map(([file, sample, read]) => (
          <span key={file} data-testid="rule-example" className="contents">
            <span className="font-data text-[12px] text-ink-2 break-all">{file}</span>
            <span className="text-ink-3">→</span>
            <span>sample <b>{sample}</b>{read ? `, read ${read}` : ""}</span>
          </span>
        ))}
      </div>
      <span className="text-[13px] text-ink-2">
        {data.rule.pattern ? <>Rule <span className="font-data">{data.rule.pattern}</span>: </>
          : paired ? "Paired by name: " : "One sample per file: "}
        <b>{samples} {samples === 1 ? "sample" : "samples"}</b>{paired ? ", paired" : ""}.
        {unfit > 0 && ` ${unfit} ${unfit === 1 ? "file did" : "files did"} not fit the pattern.`}
      </span>
      {editing ? (
        <span className="flex items-center gap-2 flex-wrap">
          <input aria-label="Reading rule" value={pattern} onChange={(e) => setPattern(e.target.value)}
                 className="h-8 w-[320px] max-w-full px-[10px] border border-line-2 rounded-control bg-surface font-data text-[12.5px] text-ink" />
          <button type="button" onClick={() => setRule(pattern.trim()).then(() => setEditing(false), () => undefined)}
                  className="h-8 px-3 rounded-control bg-action text-on-action shadow-raise border-0 text-[12.5px] font-semibold cursor-pointer">
            Use this rule
          </button>
          {data.rule.pattern && (
            <button type="button" onClick={() => setRule(null).then(() => setEditing(false), () => undefined)}
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
