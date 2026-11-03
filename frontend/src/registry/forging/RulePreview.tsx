import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { post } from "../../api/client";
import type { components } from "../../api/schema";
import { Failed } from "../../ui/States";
import type { ItemView } from "./useAdaptation";
import { ValueDetails } from "./ValueDetails";

type Value = string | number | boolean | null;

/** Inputs are hypothetical; the resolver on the server supplies every result. */
export function RulePreview({ id, item }: { id: string; item: ItemView }) {
  const rows = (item.value as { rows?: { when: Record<string, unknown> }[] } | null)?.rows ?? [];
  const facts = [...new Set(rows.flatMap((r) => Object.keys(r.when)))];
  const [kinds, setKinds] = useState<Record<string, string>>({});
  const [values, setValues] = useState<Record<string, Value>>({});
  const preview = useQuery({
    queryKey: ["forge-rule-preview", id, item.key, item.current_n, values],
    queryFn: () => post<components["schemas"]["Preview"]>(`/forge/adaptations/${id}/rule-preview`, {
      item: item.key, expected: item.current_n, premises: values,
    }),
    retry: false,
  });
  return <section aria-label="Try this rule" className="mt-3 border border-line rounded-control p-3 flex flex-col gap-3">
    <h3 className="m-0 text-[13px] font-semibold">Try this rule</h3>
    <p className="m-0 text-[12.5px] text-ink-3">Hypothetical facts. The server runs this revision of the rule; your draft stays as it is. Rows are tried in order.</p>
    {facts.map((fact) => {
      const numeric = /read.*length/.test(fact) || rows.some((r) => typeof r.when[fact] === "number"
        || typeof r.when[fact] === "string" && /^[<>!=]=? -?\d/.test(String(r.when[fact])));
      const boolean = rows.some((r) => typeof r.when[fact] === "boolean");
      const kind = kinds[fact] ?? (numeric ? "number" : boolean ? "boolean" : "text");
      const slider = kind === "number" && /read.*length/.test(fact);
      return <div key={fact} className="flex flex-col gap-1 text-[12.5px]">
        <span className="[overflow-wrap:anywhere]">{fact.replaceAll("_", " ")}</span>
        <select aria-label={`${fact} kind`} className="control" value={kind} onChange={(e) => {
          setKinds({ ...kinds, [fact]: e.target.value });
          setValues({ ...values, [fact]: null });
        }}>
          <option value="text">Text</option><option value="number">Number</option><option value="boolean">Boolean</option>
        </select>
        {kind === "boolean" ? <select aria-label={fact} value={String(values[fact] ?? "")} className="control"
          onChange={(e) => setValues({ ...values, [fact]: e.target.value === "" ? null : e.target.value === "true" })}>
          <option value="">Not supplied</option><option value="true">Yes</option><option value="false">No</option>
        </select> : <input aria-label={fact} type={kind === "number" ? "number" : "text"} value={String(values[fact] ?? "")}
          className="control w-full" onChange={(e) => setValues({ ...values,
            [fact]: e.target.value === "" ? null : kind === "number" ? e.target.valueAsNumber : e.target.value })} />}
        {slider && <input aria-label={`${fact} slider`} type="range" min="1" max="1000" step="1"
          value={typeof values[fact] === "number" ? values[fact] : 1}
          onChange={(e) => setValues({ ...values, [fact]: e.target.valueAsNumber })} />}
      </div>;
    })}
    <div aria-live="polite">
      {preview.isFetching ? <p className="m-0 text-[13px]">Trying the rule…</p>
        : preview.isError ? <Failed error={preview.error} padded={false} />
        : preview.data && (preview.data.effects.length ? preview.data.effects.map((effect, n) =>
          <div key={n} className="border-t border-line-soft pt-2"><ValueDetails value={{
            decides: `${effect.effect} · ${effect.role}${effect.name ? ` · ${effect.name}` : ""}`,
            value: effect.value, because: effect.because, cite: effect.cite,
          }} /></div>) : <p className="m-0 text-[13px]">No row matches. This choice remains unresolved.</p>)}
    </div>
  </section>;
}
