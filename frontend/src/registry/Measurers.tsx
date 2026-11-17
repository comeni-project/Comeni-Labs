import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router";

import { get } from "../api/client";
import type { components } from "../api/schema";
import { RailControls } from "../app/rail/RailContext";
import { useTitle } from "../app/useTitle";
import { useTypeNames } from "../build/living/useTypeNames";
import { Failed, Loading } from "../ui/States";
import { toneOf } from "./families";
import { RegistryTabs } from "./RegistryTabs";

type Reader = components["schemas"]["Reader"];

const label = "text-[11.5px] font-semibold text-ink-3";
const words = (id: string) => id.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase());
const fileOf = (r: Reader) => (r.by === "tool" ? r.type_id : r.id);
const WHERE: Record<string, string> = { server: "When data is read", pipeline: "In the run" };
const READER_NAME: Record<string, string> = { fastq: "FASTQ reader", fasta: "FASTA reader" };
const nameOf = (r: Reader) => READER_NAME[r.id] ?? (r.uses ? `${r.uses.replace(/^nf-core\//, "").split("@")[0].replace("/", " ")} output` : words(r.id));
const decides = (r: Reader) => r.facts.some((f) => f.rules.length + f.settings.length > 0);

function Fact({ id }: { id: string }) {
  return <span className="pill" style={{ background: "var(--measured-soft)", color: "var(--measured-ink)" }}>{id}</span>;
}

/** `/registry/measurers` · **Measurers** (board "7b · Registry · Measurers"): one entry a reader —
 *  a format our code reads, or a tool's output — what it reads, the facts it makes, and for each
 *  fact the rules and settings that decide by it and the cases its tests check. */
export function MeasurersPage() {
  useTitle("Measurers");
  const typeName = useTypeNames();
  const readers = useQuery({ queryKey: ["data-readers"], queryFn: () => get<Reader[]>("/data/readers") });
  const [where, setWhere] = useState<string | null>(null);
  const [chip, setChip] = useState<"all" | "code" | "tool" | "rules">("all");
  const [find, setFind] = useState("");
  const [picked, setPicked] = useState<string | null>(null);
  const all = readers.data ?? [];
  const q = find.trim().toLowerCase();
  const shown = all.filter((r) => (!where || r.runs.includes(where))
    && (chip === "all" || (chip === "rules" ? decides(r) : r.by === chip))
    && (!q || r.id.includes(q) || r.type_id.includes(q) || r.facts.some((f) => f.measurement.replace(/_/g, " ").includes(q))));
  const cur = shown.find((r) => r.id === picked) ?? shown[0];
  const count = (f: (r: Reader) => boolean) => all.filter(f).length;
  const chipCls = (on: boolean) => `inline-flex items-center gap-[7px] h-[30px] px-3 rounded-full border text-[12.5px] cursor-pointer
    ${on ? "bg-now-soft border-now-line text-now-ink font-semibold" : "bg-surface border-line text-ink-2 hover:text-ink"}`;

  return (
    <div className="overflow-y-auto h-full">
      <RegistryTabs />
      {all.length > 0 && (
        <RailControls label="Where it runs">
          <div role="group" aria-label="Where it runs" className="flex flex-col gap-[2px]">
            {Object.entries(WHERE).map(([key, name]) => {
              const n = count((r) => r.runs.includes(key));
              const on = where === key;
              return (
                <button key={key} type="button" aria-pressed={on} onClick={() => setWhere(on ? null : key)}
                        className={`relative flex items-center gap-2 h-[26px] px-[10px] rounded-control border-0 bg-transparent text-left text-[12.5px] cursor-pointer
                                    ${on ? "text-now-ink font-semibold" : "text-ink-2 hover:text-ink"}`}>
                  <span aria-hidden="true" className={`absolute inset-y-[2px] left-0 rounded-control ${on ? "bg-now-soft" : "bg-surface-2"}`}
                        style={{ width: `${Math.max(8, (100 * n) / Math.max(1, all.length))}%` }} />
                  <span className="relative">{name}</span>
                  <span className="relative ml-auto text-[11.5px] text-ink-3">{n}</span>
                </button>
              );
            })}
          </div>
        </RailControls>
      )}
      <div className="page">
        <label className="flex items-center gap-2 h-11 px-4 rounded-panel border border-line bg-surface">
          <svg aria-hidden="true" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-ink-3">
            <circle cx="11" cy="11" r="7" /><path d="M20 20l-4-4" />
          </svg>
          <input aria-label="Search measurers" placeholder="Search, or try “fasta”, “read length”, “n50”" value={find}
                 onChange={(e) => setFind(e.target.value)} className="flex-1 min-w-0 border-0 outline-0 bg-transparent text-[14px] text-ink" />
        </label>
        {readers.isPending && <Loading what="the measurers" />}
        {readers.isError && <Failed error={readers.error} />}
        {readers.data && (
          <>
            <div role="group" aria-label="Measurers by kind" className="flex flex-wrap gap-2">
              {([["all", "All", all.length, "bg-ink"], ["code", "By our code", count((r) => r.by === "code"), "bg-done"],
                 ["tool", "By a tool in the run", count((r) => r.by === "tool"), "bg-now-mid"],
                 ["rules", "Decides a rule", count(decides), "bg-measured"]] as const).map(([key, name, n, dot]) => (
                <button key={key} type="button" aria-pressed={chip === key} onClick={() => setChip(key)} className={chipCls(chip === key)}>
                  <span aria-hidden="true" className={`w-[7px] h-[7px] rounded-full ${dot}`} />{name}
                  <span className="font-data text-[11.5px] text-ink-3">{n}</span>
                </button>
              ))}
            </div>
            <div className="grid gap-[14px] items-start lg:grid-cols-[minmax(0,360px)_minmax(0,1fr)]">
              <section aria-label="Measurers" className="bg-surface border border-line rounded-panel overflow-hidden min-w-0">
                <div className="flex items-center gap-2 px-4 py-3 border-b border-line">
                  <span className="text-[13.5px] font-semibold">Measurers</span>
                  <span className="text-[12px] text-ink-3">{shown.length} shown</span>
                </div>
                {shown.map((r) => {
                  const on = r.id === cur?.id;
                  const tone = toneOf(fileOf(r));
                  return (
                    <button key={r.id} type="button" aria-pressed={on} onClick={() => setPicked(r.id)}
                            className={`w-full flex flex-col gap-[6px] pl-[13px] pr-4 py-3 border-0 border-b border-line-soft border-l-[3px] text-left cursor-pointer
                                        ${on ? "bg-now-soft border-l-now" : "bg-transparent border-l-transparent hover:bg-hover"}`}>
                      <span className="flex items-center gap-2 w-full">
                        <span aria-hidden="true" className="w-[7px] h-[7px] rounded-full bg-done shrink-0" />
                        <span className="text-[13.5px] font-semibold text-ink">{nameOf(r)}</span>
                        <span className="ml-auto font-data text-[11.5px] text-ink-3">by {r.by === "tool" ? "a tool" : "code"}</span>
                      </span>
                      <span className="pl-[15px] text-[12px] text-ink-2">{r.facts.map((f) => f.measurement.replace(/_/g, " ")).join(", ")}</span>
                      <span className="pl-[15px] flex flex-wrap items-center gap-1">
                        <span className="pill" style={{ background: tone.soft, color: tone.ink }}>{fileOf(r)}</span>
                        <span className="text-[12px] text-ink-3">→</span>
                        {r.facts.map((f) => <Fact key={f.measurement} id={f.measurement} />)}
                      </span>
                    </button>
                  );
                })}
                {shown.length === 0 && <p className="m-0 px-4 py-6 text-[13px] text-ink-3">No measurer matches. Clear a filter.</p>}
              </section>
              {cur && <Detail reader={cur} typeName={typeName} />}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function Detail({ reader: r, typeName }: { reader: Reader; typeName: (id: string) => string }) {
  const tone = toneOf(fileOf(r));
  const reads = r.by === "tool" ? `written by ${(r.uses ?? "").replace(/^nf-core\//, "").split("@")[0].replace("/", " ")}`
    : `${r.extensions.join(" ")}${r.compressed.length ? ` · and ${r.compressed.join(" ")}` : ""}`;
  return (
    <section aria-label="Selected measurer" className="bg-surface border border-line rounded-panel p-5 flex flex-col gap-4 min-w-0">
      <header className="flex flex-wrap items-start gap-3">
        <span className="flex flex-wrap items-center gap-[10px] flex-1 min-w-0">
          <h2 className="m-0 text-[20px] font-semibold">{nameOf(r)}</h2>
          <span className="font-data text-[12px] text-ink-3">{r.id}</span>
          <span className="px-[9px] py-[2px] rounded-full bg-done-soft text-done-ink text-[12px] font-semibold">In your registry</span>
        </span>
        <span className="flex flex-wrap items-center gap-2">
          <Link to="/forge" className="self-start shrink-0 inline-flex items-center h-[34px] px-[14px] whitespace-nowrap rounded-control border-0 bg-action text-on-action shadow-raise text-[13px] font-semibold no-underline">
            Add a measurement
          </Link>
        </span>
      </header>

      <div aria-label="Reads and measures" className="flex items-center justify-center px-4 py-6 rounded-panel bg-surface-2 border border-line-soft">
        <div className="flex flex-col items-end gap-[6px] min-w-0">
          <span className={label}>Reads</span>
          <span className="pill" style={{ background: tone.soft, color: tone.ink }} title={typeName(r.type_id)}>{fileOf(r)}</span>
          <span className="font-data text-[11.5px] text-ink-3">{reads}</span>
        </div>
        <span aria-hidden="true" className="w-[36px] h-px bg-line-2 shrink-0" />
        <div className="flex flex-col items-center gap-[2px] min-w-[170px] px-5 py-4 rounded-panel border border-line-2 bg-surface text-center">
          <span className="text-[15px] font-semibold text-ink">{nameOf(r)}</span>
          <span className="font-data text-[11.5px] text-ink-3">{r.by === "tool" ? "a tool's output" : `records of ${typeName(r.type_id)}`}</span>
        </div>
        <span aria-hidden="true" className="w-[36px] h-px bg-line-2 shrink-0" />
        <div className="flex flex-col items-start gap-[6px] min-w-0">
          <span className={label}>Measures</span>
          {r.facts.map((f) => <Fact key={f.measurement} id={f.measurement} />)}
        </div>
      </div>

      <dl className="m-0 grid grid-cols-3 gap-2">
        {([["Runs", r.runs.map((w) => WHERE[w] ?? w).join(" · ")], ["Reads of the data", r.by === "tool" ? "the whole output" : "the start of each file"],
           ["Trusted", r.by === "tool" ? "Curated · runs in the pipeline" : "Curated · runs here"]] as const).map(([k, v]) => (
          <div key={k} className="flex flex-col gap-[3px] px-3 py-[10px] rounded-control border border-line">
            <dt className={label}>{k}</dt>
            <dd className="m-0 text-[13.5px] font-semibold text-ink">{v}</dd>
          </div>
        ))}
      </dl>

      <div className="flex flex-col gap-2">
        <span className={label}>What it measures</span>
        {r.facts.map((f) => (
          <div key={f.measurement} data-testid="fact" className="rounded-control border border-line overflow-hidden">
            <div className="flex flex-wrap items-baseline gap-[10px] px-3 py-[10px]">
              <span className="text-[13.5px] font-semibold">{words(f.measurement)}</span>
              <Fact id={f.measurement} />
              {f.unit && <span className="text-[12px] text-ink-3">{f.unit}</span>}
              {f.description && <span className="ml-auto text-[12px] text-ink-3">{f.description}</span>}
            </div>
            {f.rules.map((rule, n) => (
              <div key={`${rule.role}-${n}`} className="border-t border-line-soft">
                <div className="px-3 py-2 text-[12.5px] font-semibold">Decides · which {rule.role.replace(/_/g, " ")}</div>
                <table className="w-full border-collapse text-[12.5px]">
                  <thead><tr className="bg-surface-2 text-left text-[11.5px] text-ink-3">
                    <th className="px-3 py-[6px] font-semibold w-[34%]">When</th><th className="px-3 py-[6px] font-semibold">Choose</th>
                  </tr></thead>
                  <tbody>{rule.rows.map((row, m) => (
                    <tr key={m} className="border-t border-line-soft">
                      <td className="px-3 py-2 font-data">{Object.entries(row.when).map(([k, v]) => `${k.replace(/_/g, " ")} ${v}`).join(", ") || "otherwise"}</td>
                      <td className="px-3 py-2 font-semibold">{(row.then ?? "").replace(/^nf-core\//, "").replace("@", " ")}</td>
                    </tr>
                  ))}</tbody>
                </table>
              </div>
            ))}
            {f.settings.map((setting) => (
              <div key={setting.name} className="border-t border-line-soft">
                <div className="px-3 py-2 text-[12.5px] font-semibold">Decides · {setting.name.replace(/_/g, " ")}</div>
                <table className="w-full border-collapse text-[12.5px]">
                  <thead><tr className="bg-surface-2 text-left text-[11.5px] text-ink-3">
                    <th className="px-3 py-[6px] font-semibold w-[34%]">When</th><th className="px-3 py-[6px] font-semibold">Value</th>
                  </tr></thead>
                  <tbody><tr className="border-t border-line-soft">
                    <td className="px-3 py-2 font-data">any genome</td><td className="px-3 py-2 font-semibold font-data">{setting.formula}</td>
                  </tr></tbody>
                </table>
              </div>
            ))}
            {f.tests.length > 0 && (
              <div className="flex flex-wrap gap-x-4 gap-y-1 px-3 py-2 border-t border-line-soft bg-surface-2">
                {f.tests.map((t) => (
                  <span key={t} className="inline-flex items-center gap-[6px] text-[12.5px] text-ink-2">
                    <span aria-hidden="true" className="w-[15px] h-[15px] rounded-full bg-done-soft text-done-ink text-[9px] font-bold grid place-items-center">✓</span>{t}
                  </span>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </section>
  );
}
