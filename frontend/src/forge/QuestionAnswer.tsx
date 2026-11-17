import { useState } from "react";

import { Failed } from "../ui/States";
import { valueOf, type ItemView } from "./items";
import type { useForgeActions } from "./useForgeActions";

type Actions = ReturnType<typeof useForgeActions>;
type Option = { id: string; label: string; because: string; new: boolean };

/** Questions take an explicit answer; approval would approve the question itself. */
export function QuestionAnswer({ item, actions }: { item: ItemView; actions: Actions }) {
  const current = valueOf(item);
  const question = [current, ...[...item.revisions].reverse().map((revision) => revision.value)]
    .find((value) => value && typeof value === "object" && !Array.isArray(value)
      && "options" in value && Array.isArray(value.options)) as Record<string, unknown> | undefined;
  const options: Option[] = ((question?.options ?? []) as Record<string, unknown>[])
    .filter((option) => typeof option.id === "string")
    .map((option) => ({ id: String(option.id), label: String(option.label ?? option.id),
      because: String(option.because ?? ""), new: option.new === true }));
  const initial = typeof current.choice === "string" ? current.choice : String(question?.suggested ?? "");
  const [choice, setChoice] = useState(initial);
  const [custom, setCustom] = useState(!!current.new && !options.some((option) => option.id === initial));
  const selected = options.find((option) => option.id === choice);
  const saved = item.status === "approved" && current.choice === choice && current.new === (custom || selected?.new === true);
  return <div className="flex flex-col gap-3 min-w-0">
    <p className="m-0 text-[13px] text-ink">{String(question?.asks ?? "Choose an answer.")}</p>
    <div aria-label="Answer choices" className="flex flex-col gap-2">
      {options.map((option) => <button key={option.id} type="button" disabled={actions.command.isPending}
        aria-pressed={!custom && choice === option.id} onClick={() => { setCustom(false); setChoice(option.id); }}
        className={`flex flex-col gap-1 p-3 rounded-control border text-left cursor-pointer disabled:opacity-50 ${!custom && choice === option.id ? "border-now bg-now-soft" : "border-line-2 bg-surface hover:bg-surface-2"}`}>
        <span className="flex flex-wrap items-center gap-2 text-[13px] font-semibold text-ink">
          {option.label}
          {question?.suggested === option.id && <span className="text-[10.5px] font-medium text-now-ink">Suggested</span>}
        </span>
        <span className="font-data text-[11px] text-ink-3 break-all">{option.id}</span>
        {option.because && <span className="text-[12px] text-ink-2">{option.because}</span>}
      </button>)}
    </div>
    {question?.allows_new === true && <details>
      <summary className="cursor-pointer text-[12px] text-ink-2">Use another identifier</summary>
      <label className="flex flex-col gap-1 mt-2 text-[12px] text-ink-2">New identifier
        <input value={custom ? choice : ""} onChange={(event) => { setCustom(true); setChoice(event.target.value); }}
          disabled={actions.command.isPending} className="control w-full font-data" />
      </label>
    </details>}
    {item.findings?.map((finding, index) => <p key={index} className="m-0 text-[12px] text-measured-ink">{finding.says}</p>)}
    <button type="button" disabled={actions.command.isPending || !choice.trim() || saved}
      onClick={() => actions.command.mutate({ move: "answer", item: item.key, expected: item.current_n,
        value: { choice: choice.trim(), new: custom || selected?.new === true } })}
      className="self-start px-3 py-2 rounded-control border-0 bg-action text-on-action shadow-raise text-[13px] font-semibold cursor-pointer disabled:opacity-50">
      {actions.command.isPending ? "Saving answer…" : saved ? "Answer saved" : "Confirm answer"}
    </button>
    {actions.command.isError && actions.command.variables?.item === item.key && <Failed error={actions.command.error} padded={false} />}
  </div>;
}
