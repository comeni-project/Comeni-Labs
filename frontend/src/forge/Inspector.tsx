import { useState } from "react";

import { typeEntries, useChoices } from "../registry/parts/useChoices";
import { Failed } from "../ui/States";
import { ItemConstructor } from "./ItemConstructor";
import { byAi, describe, live, reasonOf, valueOf, waiting, type ItemView } from "./items";
import type { AdaptationView } from "./useAdaptation";
import type { useForgeActions } from "./useForgeActions";
import { ValueDetails } from "./ValueDetails";

type Actions = ReturnType<typeof useForgeActions>;
export interface Selection { key?: string; card?: "params" | "rules" | "measurers" | "vocabulary"; adding?: string }

const label = "text-[11.5px] font-semibold text-ink-3";
const ctl = "h-[32px] w-full px-[10px] rounded-control border border-line-2 bg-surface text-[13px] text-ink";
const loud = "h-[30px] px-3 rounded-control border-0 bg-action text-on-action shadow-raise text-[12.5px] font-semibold cursor-pointer disabled:opacity-50";
const quiet = "h-[30px] px-3 rounded-control border border-line-2 bg-surface text-[12.5px] text-ink cursor-pointer disabled:opacity-50";

const CARD_TITLE: Record<NonNullable<Selection["card"]>, { title: string; prefix: string; piece: string; empty: string }> = {
  params: { title: "Parameters", prefix: "parameters:", piece: "parameters", empty: "No parameters drafted yet." },
  rules: { title: "Rules", prefix: "rules:", piece: "rules", empty: "No rule drafted yet." },
  measurers: { title: "Measurers", prefix: "measurers:", piece: "measurers",
               empty: "A measurer reads a fact from this tool’s output so later steps and rules can use it. Most tools need none." },
  vocabulary: { title: "Vocabulary", prefix: "vocabulary:", piece: "vocabulary", empty: "This tool adds nothing to the shared vocabulary." },
};

function Seg<T extends string>({ value, options, onChange, name }: { value: T; options: [T, string][]; onChange: (v: T) => void; name: string }) {
  return (
    <span role="radiogroup" aria-label={name} className="inline-flex rounded-control border border-line-2 overflow-hidden self-start">
      {options.map(([v, text]) => (
        <button key={v} type="button" role="radio" aria-checked={value === v} onClick={() => onChange(v)}
                className={`h-[30px] px-3 border-0 text-[12.5px] cursor-pointer ${value === v ? "bg-action text-on-action shadow-raise font-semibold" : "bg-surface text-ink-2"}`}>{text}</button>
      ))}
    </span>
  );
}

/** **Part** (board "6 · Forging", the inspector): the selected part — a port, a parameter, a card's
 *  list, or a new item — with its fields; an AI proposal waiting shows the AI's reason with
 *  *Looks right* and *Change*. Every save is a person's command on the item. */
export function Inspector({ view, sel, onPick, actions }: { view: AdaptationView; sel: Selection; onPick: (s: Selection) => void; actions: Actions }) {
  const items = live(view.items);
  const [editing, setEditing] = useState<string | null>(null);

  if (sel.adding) {
    return (
      <div className="flex flex-col gap-3 p-4">
        <span className={label}>New · {sel.adding}</span>
        <ItemConstructor id={view.id} piece={sel.adding} items={view.items} actions={actions} onCancel={() => onPick({ card: "params" })} />
      </div>
    );
  }
  if (sel.card) {
    const c = CARD_TITLE[sel.card];
    const its = items.filter((i) => i.key.startsWith(c.prefix));
    return (
      <div className="flex flex-col gap-3 p-4">
        <span className={label}>{c.title}</span>
        {its.length === 0 && <p className="m-0 text-[13px] text-ink-2">{c.empty}</p>}
        {its.length > 0 && (
          <div className="flex flex-col rounded-control border border-line overflow-hidden">
            {its.map((i) => {
              const d = describe(i);
              const v = valueOf(i);
              return (
                <button key={i.key} type="button" onClick={() => onPick({ key: i.key })}
                        className="flex flex-col gap-[2px] px-3 py-2 border-0 border-t border-line-soft first:border-t-0 bg-transparent text-left cursor-pointer hover:bg-surface-2">
                  <span className="flex items-center gap-2">
                    <span className="text-[13px] font-semibold text-ink">{d.title}</span>
                    {typeof v.key === "string" && <span className="font-data text-[11.5px] text-ink-3">{v.key}</span>}
                    {waiting(i) && <span className="ml-auto h-[16px] px-1 rounded-xs bg-ai-soft text-ai text-[10px] font-bold leading-[16px]">AI</span>}
                  </span>
                  <span className="text-[11.5px] text-ink-3 truncate">
                    {v.default !== undefined ? `default ${String(v.default)}` : i.sentence ?? String(v.because ?? v.explain ?? "")}
                  </span>
                </button>
              );
            })}
          </div>
        )}
        <span className="flex gap-2">
          <button type="button" className={quiet} onClick={() => onPick({ adding: c.piece })}>Write it myself</button>
        </span>
      </div>
    );
  }

  const item = items.find((i) => i.key === sel.key) ?? view.items.find((i) => i.key === sel.key);
  if (!item) return <p className="m-0 p-4 text-[13px] text-ink-3">Pick a part of the tool to see it here.</p>;
  const d = describe(item);
  const piece = item.key.split(":")[0];
  const isPort = item.key.startsWith("contract:input:") || item.key.startsWith("contract:output:");
  const isParam = item.key.startsWith("parameters:param:");
  const changing = editing === item.key;

  return (
    <div className="flex flex-col gap-3 p-4">
      <div className="flex flex-col gap-1">
        <span className={label}>{d.kind}</span>
        <h2 className="m-0 text-[16px] font-semibold break-words">{d.title}</h2>
        <span className="flex items-center gap-2 text-[11.5px] text-ink-3">
          <span className={`px-[5px] rounded-xs font-bold ${byAi(item) ? "bg-ai-soft text-ai" : "bg-done-soft text-done-ink"}`}>{byAi(item) ? "AI" : "You"}</span>
          {item.status === "approved" ? "approved" : item.status === "removed" ? "removed" : waiting(item) ? "waiting for review" : item.status}
        </span>
      </div>
      {changing ? (
        <ItemConstructor key={item.key} id={view.id} piece={piece} items={view.items} item={item} actions={actions} onCancel={() => setEditing(null)} />
      ) : isPort ? (
        <PortFields view={view} item={item} actions={actions} />
      ) : isParam ? (
        <ParamFields item={item} actions={actions} />
      ) : (
        <div className="text-[12.5px] text-ink-2 min-w-0 break-words">
          {item.sentence ? <p className="m-0">{item.sentence}</p> : <ValueDetails value={item.value} />}
        </div>
      )}
      {!changing && !isPort && !isParam && item.status !== "removed" && (
        <button type="button" className={`${quiet} self-start`} onClick={() => setEditing(item.key)}>Change</button>
      )}
      {waiting(item) && (
        <div className="flex flex-col gap-2 p-3 rounded-control border border-ai-line bg-ai-soft">
          <span className="text-[12.5px] text-ink"><b className="text-ai">AI</b>{reasonOf(item) ? ` · ${reasonOf(item)}` : " · proposed this; nobody has reviewed it yet."}</span>
          <span className="flex gap-2">
            <button type="button" className={loud} disabled={actions.command.isPending}
                    onClick={() => actions.command.mutate({ move: "approve", item: item.key, expected: item.current_n })}>Looks right</button>
            <button type="button" className={quiet} onClick={() => setEditing(item.key)}>Change</button>
          </span>
        </div>
      )}
      {actions.command.isError && <Failed error={actions.command.error} padded={false} />}
    </div>
  );
}

function PortFields({ view, item, actions }: { view: AdaptationView; item: ItemView; actions: Actions }) {
  const v = valueOf(item);
  const input = item.key.startsWith("contract:input:");
  const choices = useChoices(true);
  const drafted = live(view.items).filter((i) => i.key.startsWith("vocabulary:type:")).map((i) => i.key.slice("vocabulary:type:".length));
  const [type, setType] = useState(String(v.type_id ?? ""));
  const [format, setFormat] = useState(Array.isArray(v.format) ? (v.format as string[]).join(" ") : "");
  const [required, setRequired] = useState(v.required !== false);
  const [always, setAlways] = useState(!v.produced_when);
  const [find, setFind] = useState("");
  const entries = choices.data ? typeEntries(choices.data) : [];
  const ids = [...new Set([...drafted, ...entries.map((e) => e.id)])];
  const q = find.trim().toLowerCase();
  const shown = ids.filter((id) => !q || id.includes(q) || (entries.find((e) => e.id === id)?.says ?? "").toLowerCase().includes(q)).slice(0, 8);
  const save = () => actions.command.mutate({
    move: "change", item: item.key, expected: item.current_n,
    value: input ? { ...v, type_id: type, required }
      : { ...v, type_id: type, format: format.split(/[\s,]+/).filter(Boolean), produced_when: always ? null : v.produced_when ?? null },
  });
  const dirty = type !== String(v.type_id ?? "") || (input ? required !== (v.required !== false)
    : format !== (Array.isArray(v.format) ? (v.format as string[]).join(" ") : "") || always !== !v.produced_when);
  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-col gap-1">
        <span className={label}>Data type <span className="font-normal">from the registry vocabulary</span></span>
        <div className="rounded-control border border-line-2 overflow-hidden">
          <input aria-label="Search data types" placeholder="Search data types" value={find} onChange={(e) => setFind(e.target.value)}
                 className="h-[32px] w-full px-[10px] border-0 border-b border-line-soft bg-surface text-[12.5px] text-ink outline-0" />
          {shown.map((id) => {
            const e = entries.find((x) => x.id === id);
            const on = id === type;
            return (
              <button key={id} type="button" aria-pressed={on} onClick={() => setType(id)}
                      className={`w-full flex flex-col px-[10px] py-[6px] border-0 border-t border-line-soft first:border-t-0 text-left cursor-pointer ${on ? "bg-now-soft" : "bg-surface hover:bg-surface-2"}`}>
                <span className="flex items-center gap-2">
                  <span className={`font-data text-[12px] ${on ? "text-now-ink font-semibold" : "text-ink"}`}>{id}</span>
                  {drafted.includes(id) && <span className="text-[10px] font-bold text-measured-ink">new</span>}
                </span>
                {e?.says && <span className="text-[11.5px] text-ink-3 truncate">{e.says}</span>}
              </button>
            );
          })}
        </div>
      </div>
      {!input && (
        <label className="flex flex-col gap-1"><span className={label}>Format</span>
          <input className={`${ctl} font-data`} value={format} onChange={(e) => setFormat(e.target.value)} /></label>
      )}
      {input ? (
        <div className="flex flex-col gap-1"><span className={label}>Needed</span>
          <Seg name="Needed" value={required ? "y" : "n"} options={[["y", "Required"], ["n", "Optional"]]} onChange={(x) => setRequired(x === "y")} /></div>
      ) : (
        <div className="flex flex-col gap-1"><span className={label}>Always made</span>
          <Seg name="Always made" value={always ? "y" : "n"} options={[["y", "Always"], ["n", "Only sometimes"]]} onChange={(x) => setAlways(x === "y" || !v.produced_when)} />
          {!always && <span className="text-[12px] text-ink-3">{Object.entries((v.produced_when ?? {}) as Record<string, unknown>).map(([k, x]) => `${k} is ${String(x)}`).join(", ")}</span>}
        </div>
      )}
      {dirty && <button type="button" className={`${loud} self-start`} disabled={actions.command.isPending} onClick={save}>Save</button>}
    </div>
  );
}

const KIND: Record<string, string> = { integer: "Number", number: "Number", boolean: "Yes / no", enum: "Choice" };

function ParamFields({ item, actions }: { item: ItemView; actions: Actions }) {
  const v = valueOf(item);
  const domain = (v.domain ?? null) as { kind?: string; values?: string[] } | null;
  const [def, setDef] = useState(v.default === undefined || v.default === null ? "" : String(v.default));
  const [help, setHelp] = useState(String(v.explain ?? ""));
  const flag = typeof v.template === "string" ? v.template : typeof v.key === "string" ? `ext.${v.key}` : String(v.via ?? "");
  const dirty = def !== (v.default === undefined || v.default === null ? "" : String(v.default)) || help !== String(v.explain ?? "");
  return (
    <div className="flex flex-col gap-3">
      <div className="grid grid-cols-2 gap-2">
        <div className="flex flex-col gap-1"><span className={label}>Kind</span><span className="text-[13px] text-ink">{domain?.kind ? KIND[domain.kind] ?? domain.kind : "Text"}</span></div>
        <div className="flex flex-col gap-1"><span className={label}>Reaches the tool by</span><span className="font-data text-[12.5px] text-ink">{flag}</span></div>
      </div>
      {domain?.values && domain.values.length > 0 && <span className="text-[12px] text-ink-3">One of {domain.values.join(", ")}</span>}
      <label className="flex flex-col gap-1"><span className={label}>Default</span>
        <input className={`${ctl} font-data`} value={def} onChange={(e) => setDef(e.target.value)} /></label>
      <label className="flex flex-col gap-1"><span className={label}>Help shown to people</span>
        <input className={ctl} value={help} onChange={(e) => setHelp(e.target.value)} placeholder="What the setting is, in one plain sentence" /></label>
      {typeof v.because === "string" && v.because && <p className="m-0 text-[12px] text-ink-3">Why this default: {v.because}</p>}
      {dirty && (
        <button type="button" className={`${loud} self-start`} disabled={actions.command.isPending}
                onClick={() => actions.command.mutate({ move: "change", item: item.key, expected: item.current_n,
                                                       value: { ...v, default: def === "" ? null : def, explain: help } })}>Save</button>
      )}
    </div>
  );
}
