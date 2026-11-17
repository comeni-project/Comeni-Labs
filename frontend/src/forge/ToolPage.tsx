import { useEffect, useState } from "react";

import { Failed } from "../ui/States";
import { Assistant } from "./Assistant";
import { useUpstream } from "./useUpstream";
import { Inspector, type Selection } from "./Inspector";
import { byAi, describe, live, valueOf, waiting, type ItemView } from "./items";
import type { AdaptationView } from "./useAdaptation";
import { useForgeActions } from "./useForgeActions";

const PIECE_WORDS: Record<string, string> = {
  questions: "the questions", contract: "the ports", parameters: "the parameters", vocabulary: "the vocabulary",
  rules: "the rules", tests: "the tests", measurers: "the measurers",
};

export const portsOf = (items: ItemView[], side: "input" | "output") =>
  live(items).filter((i) => i.key.startsWith(`contract:${side}:`))
    .sort((a, b) => Number(valueOf(a).position ?? 0) - Number(valueOf(b).position ?? 0));

/** "with ref": when an output is written, from its `produced_when` over inputs and parameters. */
export function conditionOf(item: ItemView): string | null {
  const when = valueOf(item).produced_when as Record<string, unknown> | null | undefined;
  if (!when) return null;
  return Object.keys(when).map((k) => (k.startsWith("given.") ? `with ${k.slice(6)}` : `when ${k.replace(/^param\./, "")}`)).join(", ");
}

/** `/forge/:id` · **Tool** (board "6 · Forging", Tool): the tool as a small pipeline — its
 *  inputs and outputs on the process, what it connects to in your registry — the part cards
 *  under it, and beside it the selected part or the assistant. */
export function ToolPage({ view, part }: { view: AdaptationView; part: string | null }) {
  const actions = useForgeActions(view.id);
  const items = live(view.items);
  const firstWaiting = items.find(waiting)?.key;
  const [sel, setSel] = useState<Selection>(part ? { key: part } : firstWaiting ? { key: firstWaiting } : { card: "params" });
  const [tab, setTab] = useState<"part" | "assistant">("part");
  useEffect(() => { if (part) { setSel({ key: part }); setTab("part"); } }, [part]);
  const pick = (s: Selection) => { setSel(s); setTab("part"); };

  const drafting = view.phase === "drafting" || view.phase === "asking";
  const next = view.next_piece;
  const nextEmpty = !!next && !items.some((i) => i.key.startsWith(`${next}:`));

  return (
    <div className="grid gap-[14px] items-start xl:grid-cols-[minmax(0,1fr)_340px]">
      <div className="flex flex-col gap-[14px] min-w-0">
        {(drafting || (nextEmpty && !["assembled", "testing", "tested", "publishing", "in_review", "merged"].includes(view.phase))) && (
          <div role="status" className="flex flex-wrap items-center gap-3 px-4 py-3 rounded-panel border border-ai-line bg-ai-soft text-[13px] text-ink">
            <span className="h-[18px] px-[5px] rounded-xs bg-surface text-ai text-[10.5px] font-bold leading-[18px]">AI</span>
            {drafting ? <span>Drafting {PIECE_WORDS[next ?? ""] ?? "the next part"}…</span>
              : <span>Next: {PIECE_WORDS[next ?? ""] ?? next}. The AI drafts them from the module; each choice waits here for review.</span>}
            {!drafting && next && (
              <button type="button" disabled={actions.draft.isPending} onClick={() => actions.draft.mutate(next)}
                      className="ml-auto h-[30px] px-3 rounded-control border-0 bg-action text-on-action shadow-raise text-[12.5px] font-semibold cursor-pointer disabled:opacity-50">
                Draft with the AI
              </button>
            )}
          </div>
        )}
        {actions.draft.isError && <Failed error={actions.draft.error} padded={false} />}
        <Canvas view={view} sel={sel} onPick={pick} />
        <Cards view={view} sel={sel} onPick={pick} />
      </div>
      <aside aria-label="Part and assistant" className="bg-surface border border-line rounded-panel overflow-hidden min-w-0 xl:sticky xl:top-4">
        <div role="tablist" className="grid grid-cols-2 border-b border-line">
          {(["part", "assistant"] as const).map((t) => (
            <button key={t} role="tab" type="button" aria-selected={tab === t} onClick={() => setTab(t)}
                    className={`h-10 border-0 bg-transparent text-[13px] cursor-pointer border-b-2 -mb-px
                                ${tab === t ? "border-b-now text-now-ink font-semibold" : "border-b-transparent text-ink-2 hover:text-ink"}`}>
              {t === "part" ? "Part" : "Assistant"}
            </button>
          ))}
        </div>
        {tab === "part" ? <Inspector view={view} sel={sel} onPick={pick} actions={actions} />
          : <Assistant view={view} about={sel.key ?? null} actions={actions} />}
      </aside>
    </div>
  );
}

function AiTag() {
  return <span className="h-[16px] px-1 rounded-xs bg-ai-soft text-ai text-[10px] font-bold leading-[16px]">AI</span>;
}

function Canvas({ view, sel, onPick }: { view: AdaptationView; sel: Selection; onPick: (s: Selection) => void }) {
  const items = live(view.items);
  const inputs = portsOf(view.items, "input");
  const outputs = portsOf(view.items, "output");
  const process = items.find((i) => i.key === "contract:process");
  const pv = process ? valueOf(process) : {};
  const params = items.filter((i) => i.key.startsWith("parameters:") && !i.key.endsWith(":none"));
  const roles = (pv.roles as string[] | undefined) ?? [];
  const fits = useUpstream(view).data?.fits;
  const types = [...new Set(outputs.map((o) => String(valueOf(o).type_id ?? "")))].filter(Boolean);
  const newState = items.some((i) => i.key.startsWith("vocabulary:type:") && Array.isArray(valueOf(i).add_states));
  const port = (item: ItemView, side: "input" | "output") => {
    const v = valueOf(item);
    const on = sel.key === item.key;
    const optional = side === "input" && v.required === false;
    const cond = side === "output" ? conditionOf(item) : null;
    const name = describe(item).title;
    return (
      <button key={item.key} type="button" aria-pressed={on} onClick={() => onPick({ key: item.key })}
              aria-label={`${side === "input" ? "Input" : "Output"} ${name}`}
              className={`relative flex items-center gap-2 w-full py-[5px] border-0 rounded-control cursor-pointer text-left
                          ${side === "input" ? "pl-3 pr-2" : "pl-2 pr-3 justify-end"} ${on ? "bg-now-soft" : "bg-transparent hover:bg-surface-2"}`}>
        <span aria-hidden="true" className={`absolute top-1/2 -translate-y-1/2 w-[9px] h-[9px] rounded-full bg-surface border
                                             ${optional ? "border-dashed border-ink-3" : "border-ink-2"} ${side === "input" ? "-left-[5px]" : "-right-[5px]"}`} />
        {side === "output" && waiting(item) && <AiTag />}
        {side === "output" && cond && <span className="text-[11.5px] text-ink-3">{cond}</span>}
        <span className={`text-[12.5px] font-semibold ${on ? "text-now-ink" : "text-ink"}`}>{name}</span>
        {side === "input" && <span className="pill font-data text-[11px]" style={{ background: "var(--now-soft)", color: "var(--now-ink)" }}>{String(v.type_id ?? "")}</span>}
        {side === "input" && optional && <span className="text-[11.5px] text-ink-3">opt</span>}
        {side === "input" && waiting(item) && <AiTag />}
      </button>
    );
  };
  const neighbour = (path: string, via: string, side: "left" | "right") => (
    <div key={path} className="flex flex-col gap-[2px] w-[150px] px-3 py-2 rounded-control border border-dashed border-line-2 bg-surface text-[12px]">
      <span className="font-semibold text-ink truncate">{path}</span>
      <span className="text-ink-3">in registry · {side === "left" ? "makes" : "takes"} {via}</span>
    </div>
  );
  return (
    <section aria-label="The tool" className="bg-surface border border-line rounded-panel p-4 flex flex-col gap-3 min-w-0">
      <span className="text-[11.5px] font-semibold text-ink-3">From your registry</span>
      <div className="flex items-center justify-center gap-4 overflow-x-auto py-2">
        <div className="flex flex-col gap-2 shrink-0">{fits?.takes_from.slice(0, 2).map((f) => neighbour(f.path, f.via, "left"))}</div>
        <div className="w-[360px] shrink-0 rounded-panel border border-line-2 bg-surface shadow-e1 px-4 py-3 flex flex-col gap-3">
          <div className="flex items-start gap-2">
            <button type="button" onClick={() => onPick({ key: "contract:process" })} className="flex flex-col items-start border-0 bg-transparent p-0 cursor-pointer text-left">
              <span className="text-[15px] font-semibold text-ink">{String(pv.nf_process ?? view.path.toUpperCase())}</span>
              <span className="font-data text-[11.5px] text-ink-3">{[view.version, roles.map((r) => r.replace(/_/g, " ")).join(", ")].filter(Boolean).join(" · ")}</span>
            </button>
            <button type="button" onClick={() => onPick({ card: "params" })}
                    className="ml-auto h-[24px] px-2 rounded-control border border-line-2 bg-surface text-[11.5px] text-ink-2 cursor-pointer">
              {params.length} parameter{params.length === 1 ? "" : "s"}
            </button>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-[2px] -ml-4">
              <span className="pl-4 text-[11px] font-semibold text-ink-3">Takes</span>
              {inputs.map((i) => port(i, "input"))}
              <button type="button" onClick={() => onPick({ adding: "contract" })}
                      className="self-start ml-4 mt-2 h-[26px] px-2 rounded-control border border-line bg-surface text-[11.5px] text-now-ink cursor-pointer">+ Add input</button>
            </div>
            <div className="flex flex-col gap-[2px] items-end -mr-4">
              <span className="pr-4 text-[11px] font-semibold text-ink-3">Makes</span>
              {outputs.map((o) => port(o, "output"))}
              <button type="button" onClick={() => onPick({ adding: "contract" })}
                      className="self-end mr-4 mt-2 h-[26px] px-2 rounded-control border border-line bg-surface text-[11.5px] text-now-ink cursor-pointer">+ Add output</button>
            </div>
          </div>
        </div>
        <div className="flex flex-col gap-2 shrink-0">{fits?.feeds.slice(0, 2).map((f) => neighbour(f.path, f.via, "right"))}</div>
      </div>
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[11.5px] text-ink-3">
        {types.length === 1 && <span>All outputs are <span className="pill font-data">{types[0]}</span>{newState && <b className="ml-1 text-measured-ink">new state</b>}</span>}
        <span>Dashed pin: optional input</span>
        {inputs.length + outputs.length === 0 && <span>No ports drafted yet.</span>}
      </div>
    </section>
  );
}

const CARDS: { card: Selection["card"]; title: string; prefix: string; piece: string; empty: string }[] = [
  { card: "params", title: "Parameters", prefix: "parameters:", piece: "parameters", empty: "None yet." },
  { card: "rules", title: "Rules", prefix: "rules:", piece: "rules", empty: "None yet." },
  { card: "measurers", title: "Measurers", prefix: "measurers:", piece: "measurers", empty: "None yet. Optional." },
  { card: "vocabulary", title: "Vocabulary", prefix: "vocabulary:", piece: "vocabulary", empty: "No change." },
];

function Cards({ view, sel, onPick }: { view: AdaptationView; sel: Selection; onPick: (s: Selection) => void }) {
  const items = live(view.items);
  return (
    <div className="grid gap-3 grid-cols-2 lg:grid-cols-4">
      {CARDS.map((c) => {
        const its = items.filter((i) => i.key.startsWith(c.prefix) && !i.key.endsWith(":none"));
        const on = sel.card === c.card;
        return (
          <div key={c.title} className={`relative flex flex-col gap-2 p-3 rounded-panel border bg-surface min-w-0 ${on ? "border-now shadow-[0_0_0_1px_var(--now)]" : "border-line"}`}>
            <button type="button" aria-label={c.title} onClick={() => onPick({ card: c.card })} className="absolute inset-0 border-0 bg-transparent cursor-pointer rounded-panel" />
            <span className="flex items-center gap-2">
              <span className="text-[13px] font-semibold text-ink">{c.title}</span>
              <span className="text-[11.5px] text-ink-3">{its.length}</span>
              {its.some(waiting) && <AiTag />}
              <button type="button" onClick={() => onPick({ adding: c.piece })}
                      className="relative ml-auto h-[24px] px-2 rounded-control border border-line-2 bg-surface text-[11.5px] text-ink-2 cursor-pointer">+ Add</button>
            </span>
            <span className="flex flex-col text-[12px] text-ink-2 min-w-0">
              {its.length === 0 && <span className="text-ink-3">{items.some((i) => i.key === `${c.piece}:none`) ? "None needed." : c.empty}</span>}
              {its.slice(0, 3).map((i) => <span key={i.key} className="truncate">{describe(i).title}{byAi(i) && waiting(i) ? " · AI" : ""}</span>)}
              {its.length > 3 && <span className="text-ink-3">and {its.length - 3} more</span>}
            </span>
          </div>
        );
      })}
    </div>
  );
}
