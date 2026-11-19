import { useQueries } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";

import { listModels } from "./useAction";
import { FIELD } from "./shared";
import type { Entry, Menu } from "./usePreferences";

/** A model for one purpose (spec §6): *same as the default*, a model listed by any connection,
 * or *Other…*, a typed `provider/model` on a chosen connection — for a hosted provider, which
 * lists nothing. */
/** A model's name as a person reads it: the provider prefix LiteLLM needs is the value, not the
 *  label (`ollama_chat/gemma3:4b` reads *gemma3:4b*). */
const short = (model: string) => model.includes("/") ? model.slice(model.indexOf("/") + 1) : model;

type Tuning = { temperature?: number; reasoning_effort?: string; timeout_seconds?: number };
type Choice = ({ connection: string; model: string } & Tuning) | null;

const EFFORTS = ["none", "minimal", "low", "medium", "high"];

/** What a tuned call sends, in a line: *Temperature 1 · effort high · 180 s*. */
function tuned(c: Tuning): string {
  const parts = [
    c.temperature !== undefined && `Temperature ${c.temperature}`,
    c.reasoning_effort && `effort ${c.reasoning_effort}`,
    c.timeout_seconds !== undefined && `${c.timeout_seconds} s`,
  ].filter(Boolean);
  // The defaults are the installation's (`COMENI_AI_TEMPERATURE`, `…_TIMEOUT_SECONDS`), which
  // this page does not read, so it does not name a number.
  return parts.length ? parts.join(" · ") : "Installation defaults";
}

/** A chosen model's call settings (issue 457): a reasoning model refuses temperature 0, and a slow
 *  one needs longer than a minute. An empty field sends the installation's default. */
function CallSettings({ choice, disabled, onWrite }: {
  choice: NonNullable<Choice>; disabled: boolean; onWrite: (v: Choice) => void;
}) {
  const [temperature, setTemperature] = useState(choice.temperature?.toString() ?? "");
  const [effort, setEffort] = useState(choice.reasoning_effort ?? "");
  const [timeout, setTimeout_] = useState(choice.timeout_seconds?.toString() ?? "");
  const save = () => {
    const { connection, model } = choice;
    onWrite({
      connection, model,
      ...(temperature !== "" && { temperature: Number(temperature) }),
      ...(effort && { reasoning_effort: effort }),
      ...(timeout !== "" && { timeout_seconds: Number(timeout) }),
    });
  };
  return (
    <details className="basis-full text-label text-ink-2">
      <summary className="cursor-pointer min-h-[24px]">
        Call settings <span aria-hidden="true" className="text-ink-3">·</span> <span className="text-ink-3">{tuned(choice)}</span>
      </summary>
      <span className="mt-[8px] flex flex-wrap items-end gap-x-[16px] gap-y-[8px]">
        <label className="flex flex-col gap-[4px]">Temperature
          <input type="number" min={0} max={2} step={0.1} placeholder="default" value={temperature}
                 disabled={disabled} onChange={(e) => setTemperature(e.target.value)}
                 className={`${FIELD} max-w-[110px]`} />
        </label>
        <label className="flex flex-col gap-[4px]">Reasoning effort
          <select value={effort} disabled={disabled} onChange={(e) => setEffort(e.target.value)}
                  className={`${FIELD} max-w-[150px]`}>
            <option value="">Not sent</option>
            {EFFORTS.map((e) => <option key={e}>{e}</option>)}
          </select>
        </label>
        <label className="flex flex-col gap-[4px]">Timeout (seconds)
          <input type="number" min={1} step={1} placeholder="default" value={timeout}
                 disabled={disabled} onChange={(e) => setTimeout_(e.target.value)}
                 className={`${FIELD} max-w-[110px]`} />
        </label>
        <button type="button" disabled={disabled} onClick={save}
                className="h-[34px] bg-transparent text-now-ink cursor-pointer text-secondary">
          Save call settings
        </button>
      </span>
    </details>
  );
}

export function ModelPicker({ entry, menu, onWrite }: { entry: Entry; menu: Menu; onWrite: (v: Choice) => void }) {
  const of = (entry.setting as unknown as { of: string }).of;
  const records = (menu.sections.flatMap((s) => s.entries).find((e) => e.setting.key === of)
    ?.shown.value as { name: string }[] | null) ?? [];
  const lists = useQueries({
    queries: records.map((r) => ({
      queryKey: ["models", of, r.name],
      queryFn: () => listModels(of, r.name),
      staleTime: 60_000,
    })),
  });
  const current = entry.shown.value as Choice;
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const box = useRef<HTMLSpanElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const searchInput = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (!open) return;
    searchInput.current?.focus();
    const away = (e: PointerEvent) => { if (!box.current?.contains(e.target as Node)) setOpen(false); };
    const escape = (e: KeyboardEvent) => { if (e.key === "Escape") { setOpen(false); trigger.current?.focus(); } };
    document.addEventListener("pointerdown", away);
    document.addEventListener("keydown", escape);
    return () => { document.removeEventListener("pointerdown", away); document.removeEventListener("keydown", escape); };
  }, [open]);
  const [other, setOther] = useState<{ connection: string; model: string } | null>(null);
  const encode = (c: Choice) => (c ? `${c.connection}\u0000${c.model}` : "");
  const options = records.flatMap((r, i) =>
    (lists[i].data?.values ?? []).map((model) => ({ connection: r.name, model })));
  const known = current && options.some((o) => encode(o) === encode(current));
  const failed = records.flatMap((r, i) =>
    lists[i].error ? [{ name: r.name, says: lists[i].error?.message ?? "" }]
      : lists[i].data?.ok === false ? [{ name: r.name, says: lists[i].data?.says ?? "" }] : []);

  const isDefault = entry.setting.key === "models.default";
  const emptyLabel = isDefault ? "No default model" : entry.setting.inherit_default === false ? "Off" : "Same as the default";
  const choose = (choice: Choice) => {
    setOther(null); setOpen(false);
    onWrite(choice?.model.startsWith("chatgpt/") && choice.temperature === undefined ? { ...choice, temperature: 1 } : choice);
    trigger.current?.focus();
  };
  const visible = options.filter((o) => `${o.connection} ${o.model}`.toLowerCase().includes(search.toLowerCase()));
  const listing = lists.some((l) => l.isPending);

  return (
    <span ref={box} className="relative flex flex-wrap items-center gap-[8px]">
      <button ref={trigger} id={entry.setting.key} type="button" aria-label={entry.setting.label}
        aria-haspopup="dialog" aria-expanded={open} disabled={entry.shown.locked}
        onClick={() => {
          setSearch(""); setOpen(!open);
          if (!open) lists.forEach((list) => { if (list.isStale) void list.refetch(); });
        }}
        className={`${FIELD} flex items-center justify-between gap-2 text-left cursor-pointer`}>
        <span className="truncate">{current ? short(current.model) : emptyLabel}</span><span aria-hidden>⌄</span>
      </button>
      {open && <div role="dialog" aria-label={`Choose model for ${entry.setting.label}`} className="model-popover">
        <label className="sr-only" htmlFor={`search-${entry.setting.key}`}>Search models</label>
        <input ref={searchInput} id={`search-${entry.setting.key}`} type="search" value={search}
          onChange={(e) => setSearch(e.target.value)} placeholder="Search models or connections…" className="connection-field" />
        <div className="model-popover-options">
          <button type="button" onClick={() => choose(null)} className="model-popover-option">
            <span>{emptyLabel}</span>{!current && <span aria-hidden>✓</span>}
          </button>
          {current && !known && <button type="button" onClick={() => choose(current)} className="model-popover-option">
            <span>{short(current.model)}<small>{current.connection}</small></span><span aria-hidden>✓</span>
          </button>}
          {visible.map((o) => <button type="button" key={encode(o)} onClick={() => choose(o)} className="model-popover-option">
            <span>{short(o.model)}<small>{o.connection}</small></span>{encode(o) === encode(current) && <span aria-hidden>✓</span>}
          </button>)}
          {listing && <p role="status" className="m-0 p-3 text-secondary text-ink-3">Loading models…</p>}
          {!listing && !visible.length && <p role="status" className="m-0 p-3 text-secondary text-ink-3">{records.length ? "No models match. Check a connection or enter an ID below." : "Add a connection above to discover models."}</p>}
        </div>
        {records.length > 0 && <button type="button" className="model-popover-option text-now-ink" onClick={() => {
          setOther({ connection: records[0].name, model: "" }); setOpen(false);
        }}>Enter a model ID…</button>}
        <button type="button" className="connection-text-button" onClick={() => { setOpen(false); trigger.current?.focus(); }}>Close</button>
      </div>}
      {/* One line however many connections failed, naming them; the server's own words are in
          its title. A connection whose list could not be read still offers *Other…*. */}
      {failed.length > 0 && (
        <span className="basis-full text-label text-needs-you-ink" title={failed.map((f) => f.says).join("\n")}>
          Could not list models on {failed.map((f) => f.name).join(", ")}.
        </span>
      )}
      {current && !other && (
        <CallSettings key={JSON.stringify(current)} choice={current}
                      disabled={entry.shown.locked} onWrite={onWrite} />
      )}
      {other && (
        <>
          <select aria-label="Connection" value={other.connection}
                  onChange={(e) => setOther({ ...other, connection: e.target.value })}
                  className={`${FIELD} max-w-[160px]`}>
            {records.map((r) => <option key={r.name}>{r.name}</option>)}
          </select>
          <input aria-label="Model id" placeholder="provider/model" value={other.model}
                 onChange={(e) => setOther({ ...other, model: e.target.value })}
                 className={FIELD} />
          <button type="button" disabled={!other.connection || !other.model.includes("/") || entry.shown.locked}
                  onClick={() => choose(other)}
                  className="bg-transparent text-now-ink cursor-pointer text-secondary">Use</button>
        </>
      )}
    </span>
  );
}
