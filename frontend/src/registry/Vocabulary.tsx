import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { get } from "../api/client";
import type { components } from "../api/schema";
import { useTitle } from "../app/useTitle";
import { Panel } from "../ui/Panel";
import { Failed, Loading } from "../ui/States";
import { toneOf } from "./families";
import { RegistryTabs } from "./RegistryTabs";

type Vocabulary = components["schemas"]["AuthoringVocabulary"];

const words = (id: string) => id.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase());
const suffix = (typeId: string) => typeId.split(".").pop() ?? typeId;

/** **Registry · Vocabulary** (#511; the board names the page, this draws it in the Tools page's
 *  grammar): the data types a pipeline passes between steps, and the measurements the builder
 *  reads facts as, each with what measures it — a reader when data is read, a tool in the run,
 *  or a person who says it. */
export function VocabularyPage() {
  useTitle("Vocabulary");
  const vocabulary = useQuery({
    queryKey: ["authoring-vocabulary"],
    queryFn: () => get<Vocabulary>("/pipeline/authoring/vocabulary"),
    staleTime: Infinity,
  });
  const [find, setFind] = useState("");
  const q = find.trim().toLowerCase();
  const data = vocabulary.data;
  const types = Object.entries(data?.types ?? {})
    .filter(([id]) => !q || id.includes(q) || (data?.names[id] ?? "").toLowerCase().includes(q))
    .sort(([a], [b]) => a.localeCompare(b));
  const measurements = Object.values(data?.measurements ?? {})
    .filter((m) => !q || m.id.includes(q) || (m.description ?? "").toLowerCase().includes(q))
    .sort((a, b) => a.id.localeCompare(b.id));
  const byWhom = (id: string) => (data?.measurers ?? []).filter((m) => m.measurement === id);

  return (
    <div className="overflow-y-auto h-full">
      <RegistryTabs />
      <div className="page">
        <label className="flex items-center gap-2 h-11 px-4 rounded-panel border border-line bg-surface">
          <svg aria-hidden="true" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-ink-3">
            <circle cx="11" cy="11" r="7" /><path d="M20 20l-4-4" />
          </svg>
          <input aria-label="Search the vocabulary" placeholder="Search types and measurements, or try “reads”, “length”"
                 value={find} onChange={(e) => setFind(e.target.value)}
                 className="flex-1 min-w-0 border-0 outline-0 bg-transparent text-[14px] text-ink" />
        </label>
        {vocabulary.isPending && <Loading what="the vocabulary" />}
        {vocabulary.isError && <Failed error={vocabulary.error} />}
        {data && (
          <div className="grid gap-[14px] items-start lg:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)]">
            <Panel title="Data types" hint={String(types.length)}>
              {types.map(([id, states]) => {
                const tone = toneOf(suffix(id));
                return (
                  <div key={id} data-testid="type-row" className="flex flex-col gap-1 px-5 py-[10px] border-t border-line-soft">
                    <span className="flex items-center gap-2 min-w-0">
                      <span className="px-[7px] py-[1px] rounded-xs font-data text-[11.5px]" style={{ background: tone.soft, color: tone.ink }}>
                        {suffix(id)}
                      </span>
                      <span className="truncate text-[13.5px] font-semibold text-ink">{data.names[id] ?? id}</span>
                      <span className="ml-auto shrink-0 text-[12px] text-ink-3">
                        {data.grains[id] === "study" ? "for the whole run" : "one per sample"}
                      </span>
                    </span>
                    <span className="flex flex-wrap items-center gap-1">
                      <span className="font-data text-[11.5px] text-ink-3">{id}</span>
                      {states.map((s) => (
                        <span key={s} className="px-[6px] rounded-xs border border-line text-[11px] text-ink-2">{s}</span>
                      ))}
                    </span>
                  </div>
                );
              })}
              {types.length === 0 && <p className="m-0 px-5 pb-4 text-[13px] text-ink-3">No type matches.</p>}
            </Panel>
            <Panel title="Measurements" hint={String(measurements.length)}>
              {measurements.map((m) => {
                const who = byWhom(m.id);
                const said = who.length
                  ? who.map((w) => (w.runs.includes("server") ? "read with the data" : "measured in the run")).filter((v, i, a) => a.indexOf(v) === i).join(" · ")
                  : m.assertion_only ? "you say it" : "nothing measures it yet";
                return (
                  <div key={m.id} data-testid="measurement-row" className="flex flex-col gap-1 px-5 py-[10px] border-t border-line-soft">
                    <span className="flex items-center gap-2 min-w-0">
                      <span className="truncate text-[13.5px] font-semibold text-ink">{words(m.id)}</span>
                      {m.unit && <span className="text-[12px] text-ink-3">{m.unit}</span>}
                      {m.describes && (
                        <span className="px-[7px] py-[1px] rounded-xs font-data text-[11px]"
                              style={{ background: toneOf(suffix(m.describes)).soft, color: toneOf(suffix(m.describes)).ink }}>
                          {suffix(m.describes)}
                        </span>
                      )}
                      <span className={`ml-auto shrink-0 text-[12px] ${who.length ? "text-done-ink" : "text-ink-3"}`}>{said}</span>
                    </span>
                    {(m.explain || m.description) && <span className="text-[12.5px] text-ink-2">{m.explain || m.description}</span>}
                  </div>
                );
              })}
              {measurements.length === 0 && <p className="m-0 px-5 pb-4 text-[13px] text-ink-3">No measurement matches.</p>}
            </Panel>
          </div>
        )}
      </div>
    </div>
  );
}
