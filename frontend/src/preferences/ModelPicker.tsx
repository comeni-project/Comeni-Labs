import { useQueries } from "@tanstack/react-query";
import { useState } from "react";

import { listModels } from "./useAction";
import { FIELD } from "./shared";
import type { Entry, Menu } from "./usePreferences";

/** A model for one purpose (spec §6): *same as the default*, a model listed by any connection,
 * or *Other…*, a typed `provider/model` on a chosen connection — for a hosted provider, which
 * lists nothing. */
/** A model's name as a person reads it: the provider prefix LiteLLM needs is the value, not the
 *  label (`ollama_chat/gemma3:4b` reads *gemma3:4b*). */
const short = (model: string) => model.includes("/") ? model.slice(model.indexOf("/") + 1) : model;

type Choice = { connection: string; model: string } | null;

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
  const [other, setOther] = useState<{ connection: string; model: string } | null>(null);
  const encode = (c: Choice) => (c ? `${c.connection}\u0000${c.model}` : "");
  const options = records.flatMap((r, i) =>
    (lists[i].data?.values ?? []).map((model) => ({ connection: r.name, model })));
  const known = current && options.some((o) => encode(o) === encode(current));
  const failed = records.flatMap((r, i) =>
    lists[i].error ? [{ name: r.name, says: lists[i].error?.message ?? "" }]
      : lists[i].data?.ok === false ? [{ name: r.name, says: lists[i].data?.says ?? "" }] : []);

  return (
    <span className="flex flex-wrap items-center gap-[8px]">
      <select
        aria-label={entry.setting.label}
        disabled={entry.shown.locked}
        value={other ? "\u0001" : encode(current)}
        onChange={(event) => {
          const v = event.target.value;
          if (v === "\u0001") return setOther({ connection: records[0]?.name ?? "", model: "" });
          setOther(null);
          onWrite(v ? { connection: v.split("\u0000")[0], model: v.split("\u0000")[1] } : null);
        }}
        className={FIELD}
      >
        <option value="">Same as the default</option>
        {current && !known && <option value={encode(current)}>{current.connection} · {short(current.model)}</option>}
        {options.map((o) => <option key={encode(o)} value={encode(o)}>{o.connection} · {short(o.model)}</option>)}
        <option value={"\u0001"}>Other…</option>
      </select>
      {/* One line however many connections failed, naming them; the server's own words are in
          its title. A connection whose list could not be read still offers *Other…*. */}
      {failed.length > 0 && (
        <span className="basis-full text-label text-fault" title={failed.map((f) => f.says).join("\n")}>
          Could not list models on {failed.map((f) => f.name).join(", ")}.
        </span>
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
          <button type="button" disabled={!other.model.includes("/")}
                  onClick={() => { onWrite(other); setOther(null); }}
                  className="bg-transparent text-link cursor-pointer text-secondary">Use</button>
        </>
      )}
    </span>
  );
}
