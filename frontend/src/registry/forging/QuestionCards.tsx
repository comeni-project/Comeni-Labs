import { useQuery } from "@tanstack/react-query";
import { useEffect, useId, useRef, useState } from "react";

import { get } from "../../api/client";
import type { components } from "../../api/schema";
import { Failed } from "../../ui/States";
import { RegistryPicker, type PickerEntry } from "../parts/RegistryPicker";
import { roleEntries, typeEntries, useChoices } from "../parts/useChoices";
import { QuestionRemoval } from "./QuestionRemoval";
import { ReviewComment, type Review } from "./Reviews";
import { nameOf, type ItemView } from "./useAdaptation";
import type { useForgeActions } from "./useForgeActions";

type Actions = ReturnType<typeof useForgeActions>;
type Context = components["schemas"]["QuestionContext"];
type Choice = components["schemas"]["ContextChoice"];
export type Finding = components["schemas"]["QuestionFinding"];

export type Asked = { asks: string; suggested?: string | null; allows_new?: boolean;
                      options: { id: string; label: string; because: string; new?: boolean }[] };

/** The question an item asks, from its revisions: once answered, its value is the answer. */
export function asked(item: ItemView): Asked | null {
  const found = item.revisions.findLast((r) => (r.value as Partial<Asked> | null)?.asks !== undefined);
  return found ? found.value as Asked : null;
}

const chosenOf = (item: ItemView) => (item.value as { choice?: string } | null)?.choice;

/** Which picker answers a question, from its key: its job, or an input's or output's type. */
function pickerFor(key: string): "role" | "type" | null {
  if (key === "questions:role") return "role";
  return /^questions:(input|output)_type:/.test(key) ? "type" : null;
}

function kindOf(key: string): string {
  if (key === "questions:role") return "Job";
  if (key.startsWith("questions:input_type:")) return "Input";
  if (key.startsWith("questions:output_type:")) return "Output";
  return key === "questions:competition" ? "Competition" : "Question";
}

/** A finding in a chip's few words; the full sentence is in the open card. */
export function shortFinding(f: Finding): string {
  if (f.code === "MF0520") return "Scope differs";
  if (f.code === "MF0521") return f.says.split(":")[0];
  return f.says.replace(/\.$/, "");
}

/** The questions of a piece as one list: one open at a time, each row saying where it stands. */
export function QuestionList({ id, items, reviews, actions, onReject, focus }: {
  id: string; items: ItemView[]; reviews: Review[]; actions: Actions;
  onReject: (key: string) => void; focus?: string | null;
}) {
  // `undefined` follows the work: the first question that still needs an answer.
  const [open, setOpen] = useState<string | null | undefined>(undefined);
  useEffect(() => { if (focus && items.some((i) => i.key === focus)) setOpen(focus); }, [focus, items]);
  const first = items.find((i) => i.status !== "removed" && !chosenOf(i))?.key ?? null;
  const current = open === undefined ? first : open;
  return <div role="list" aria-label="Questions">
    {items.map((item) => (
      <QuestionRow key={item.key} id={id} item={item} actions={actions} onReject={onReject}
        review={reviews.find((r) => r.item === item.key && r.revision === item.current_n)}
        open={current === item.key}
        onToggle={() => setOpen(current === item.key ? null : item.key)}
        onAnswered={() => setOpen(undefined)} />
    ))}
  </div>;
}

function StatusDot({ item }: { item: ItemView }) {
  if (item.status === "removed") return <span className="q-dot q-dot-removed"><span className="sr-only">Removed</span></span>;
  if (chosenOf(item)) return <span className="q-dot q-dot-done" aria-hidden="false"><span aria-hidden="true">✓</span><span className="sr-only">Answered</span></span>;
  if (item.findings.length) return <span className="q-dot q-dot-flag"><span className="sr-only">Check this</span></span>;
  return <span className="q-dot q-dot-wait"><span className="sr-only">Waiting for you</span></span>;
}

function QuestionRow({ id, item, review, actions, onReject, open, onToggle, onAnswered }: {
  id: string; item: ItemView; review?: Review; actions: Actions; onReject: (key: string) => void;
  open: boolean; onToggle: () => void; onAnswered: () => void;
}) {
  const body = useId();
  const question = asked(item);
  const chosen = chosenOf(item);
  const label = (choice: string | null | undefined) =>
    question?.options.find((o) => o.id === choice)?.label ?? choice;
  const summary = item.status === "removed" ? "Not needed for this tool"
    : chosen ? label(chosen)
    : question?.suggested ? `AI suggests: ${label(question.suggested)}` : question?.asks;
  return (
    <div role="group" aria-label={nameOf(item.key)} data-item={item.key} className="border-t border-line-soft first:border-t-0">
      <h3 className="m-0 text-[inherit] font-[inherit]">
        <button type="button" className="q-row" aria-expanded={open} aria-controls={body} onClick={onToggle}>
          <StatusDot item={item} />
          <span className="flex-1 min-w-0 flex flex-col sm:flex-row sm:flex-wrap sm:items-baseline gap-x-3 gap-y-1">
            <span className="text-[12px] text-ink-3 sm:w-[150px] sm:flex-none">{kindOf(item.key)}{item.key.includes(":") && item.key !== "questions:role" && item.key !== "questions:competition"
              ? <> <span className="font-data text-ink">{nameOf(item.key)}</span></> : null}</span>
            <span className={`min-w-0 break-words text-[13.5px] ${chosen ? "text-ink" : "text-ink-2"}`}>{summary}</span>
            {item.findings.length > 0 && <span className="flex flex-wrap gap-[6px]">
              {item.findings.map((f, n) => <span key={n} className="chip chip-flag">{shortFinding(f)}</span>)}
            </span>}
          </span>
          <span aria-hidden="true" className="text-ink-3 font-data text-[16px] w-4 text-center">{open ? "−" : "+"}</span>
        </button>
      </h3>
      {open && <div id={body} className="q-body">
        {question ? <QuestionBody id={id} item={item} question={question} review={review}
          actions={actions} onReject={onReject} onAnswered={onAnswered} />
          : <p className="m-0">{item.status === "removed" ? "Removed." : "This question has no options."}</p>}
      </div>}
    </div>
  );
}

function useQuestionContext(id: string, item: string, revision: number) {
  return useQuery({
    queryKey: ["forge-context", id, item, revision],
    queryFn: () => get<Context>(`/forge/adaptations/${id}/context?item=${encodeURIComponent(item)}`),
  });
}

/** One open question: what it asks, the module's evidence, the engine's findings, the
 *  options as one card each, a second opinion, and the person's moves. */
function QuestionBody({ id, item, question, review, actions, onReject, onAnswered }: {
  id: string; item: ItemView; question: Asked; review?: Review; actions: Actions;
  onReject: (key: string) => void; onAnswered: () => void;
}) {
  const context = useQuestionContext(id, item.key, item.current_n);
  const chosen = chosenOf(item);
  const ordered = [...question.options].sort((a, b) =>
    Number(b.id === question.suggested) - Number(a.id === question.suggested));
  // A suggestion the engine flags is not pre-selected: accepting it takes a deliberate pick.
  const flagged = item.findings.some((f) => f.option === question.suggested);
  const [picked, setPicked] = useState<string | null>(
    chosen ?? (flagged ? null : question.suggested) ?? null);
  const [all, setAll] = useState(false);
  const [removing, setRemoving] = useState(false);
  const pending = actions.command.isPending;
  const waiting = item.status === "proposed" || item.status === "reopened";
  const removed = item.status === "removed";
  const data = context.data;
  const choiceOf = (optionId: string): Choice | undefined => data?.choices.find((c) => c.id === optionId);
  const option = question.options.find((o) => o.id === picked);
  const pickedName = option ? choiceOf(option.id)?.name ?? option.label : picked;
  const isNew = (optionId: string) => choiceOf(optionId)?.proposed ?? question.options.find((o) => o.id === optionId)?.new ?? false;
  const answer = (value: { choice: string; new?: boolean }) =>
    actions.command.mutate({ move: "answer", item: item.key, expected: item.current_n, value },
                           { onSuccess: onAnswered });
  const radios = useRef<(HTMLButtonElement | null)[]>([]);
  const move = (from: number, by: number) => {
    const next = (from + by + ordered.length) % ordered.length;
    setPicked(ordered[next].id);
    radios.current[next]?.focus();
  };
  const hidden = (n: number) => !all && n >= 2 && ordered[n].id !== picked;
  const more = ordered.filter((_, n) => hidden(n)).length;

  return <div className="flex flex-col gap-3">
    <div>
      <p className="m-0 text-[16px] font-medium text-ink">{question.asks}</p>
      {data && <p className="m-0 text-[13px] text-ink-2">{data.decides}</p>}
      {data?.optional && <p className="m-0 text-[12.5px] text-ink-3">Declaring this output is optional. Include it when a pipeline should be able to use it.</p>}
    </div>
    {context.isError && <Failed error={context.error} padded={false} />}
    {!data && !context.isError && <p role="status" className="m-0 text-[13px] text-ink-3">Reading the question’s context…</p>}
    {data && <ModuleEvidence context={data} />}
    {item.findings.map((f, n) => <div key={n} role="note" className="q-finding">
      <p className="m-0">{f.says}</p>
      <p className="m-0 text-[12px] opacity-80">Engine check · {f.code} · advice, you decide</p>
    </div>)}

    {removed ? <p className="m-0 text-ink-3">Removed: not needed for this tool.</p> : <>
    {item.status === "rejected" && <p className="m-0 text-[13px]">
      This still needs an answer, correction or explicit removal. Rejecting it does not settle the question.
    </p>}
    {ordered.length > 0 && <div role="radiogroup" aria-label={question.asks} className="flex flex-col gap-2">
      {ordered.map((o, n) => {
        const c = choiceOf(o.id);
        const checked = picked === o.id;
        const fresh = isNew(o.id);
        const clash = !fresh && !!data?.arrival && !!c?.scope && c.scope !== data.arrival;
        return <div key={o.id} className={`option-card ${checked ? "is-checked" : ""} ${hidden(n) ? "is-folded" : ""}`}>
          <button type="button" role="radio" aria-checked={checked} tabIndex={checked || (!picked && n === 0) ? 0 : -1}
            ref={(el) => { radios.current[n] = el; }} className="option" disabled={pending}
            onClick={() => setPicked(o.id)}
            onKeyDown={(e) => {
              if (e.key === "ArrowDown" || e.key === "ArrowRight") { e.preventDefault(); move(n, 1); }
              if (e.key === "ArrowUp" || e.key === "ArrowLeft") { e.preventDefault(); move(n, -1); }
            }}>
            <span aria-hidden="true" className="option-dot" />
            <span className="flex flex-col gap-[2px] min-w-0">
              <span className="font-medium text-ink">{c?.name ?? o.label}</span>
              <span className="flex flex-wrap gap-[6px] items-center">
                {(c?.name ?? o.label) !== o.id && <span className="font-data text-[12px] text-ink-3 break-all">{o.id}</span>}
                {fresh ? <span className="chip chip-new">new{data?.arrival ? ` · one per ${data.arrival}` : ""}</span>
                  : c?.scope && <span className={`chip ${clash ? "chip-flag" : "chip-plain"}`}>one per {c.scope}</span>}
                {chosen === o.id && <span className="chip chip-done">chosen by you</span>}
                {!chosen && question.suggested === o.id && <span className="chip chip-now">AI suggests</span>}
              </span>
              {c?.explain && <span className="text-[13px] text-ink-2">{c.explain}</span>}
              {o.because && <span className="text-[12.5px] text-ink-3">AI: {o.because}</span>}
            </span>
          </button>
          {c && <details className="option-tools">
            <summary>{c.tools.length ? `Which tools use it (${c.tools.length})` : "No tool uses this yet"}</summary>
            {c.tools.length > 0 && <p className="m-0 font-data text-[12px] break-words">{c.tools.join(", ")}</p>}
          </details>}
        </div>;
      })}
      {more > 0 && <button type="button" className="option-more sm:hidden" onClick={() => setAll(true)}>
        {more} more
      </button>}
    </div>}
    <OtherAnswer item={item} question={question} chosen={chosen} options={ordered.map((o) => o.id)}
                 onAnswer={answer} pending={pending} />
    </>}

    {review && <ReviewComment review={review} />}

    {removing && !removed ? <QuestionRemoval item={item} actions={actions} onClose={() => setRemoving(false)} />
      : !removed && <div className="flex flex-wrap gap-2 pt-1 max-sm:[&>button]:min-h-[44px]">
        {picked && picked !== chosen && <button type="button" className="control-primary max-sm:w-full"
          disabled={pending} aria-busy={pending}
          onClick={() => answer({ choice: picked, ...(isNew(picked) ? { new: true } : {}) })}>
          Answer: {pickedName}
        </button>}
        <button type="button" className="control max-sm:flex-1" disabled={pending} onClick={() => setRemoving(true)}>
          Not needed for this tool
        </button>
        {waiting && <button type="button" className="control max-sm:flex-1" disabled={pending}
          onClick={() => { actions.command.mutate({ move: "reject", item: item.key, expected: item.current_n });
                           onReject(item.key); }}>
          Ask it again
        </button>}
      </div>}
  </div>;
}

/** What the module says about this channel: its upstream description, its main.nf line and
 *  how it arrives. The full excerpt stays one click away. */
function ModuleEvidence({ context }: { context: Context }) {
  if (!context.source_available) return <p className="m-0 text-[13px]">Module source is unavailable.</p>;
  if (!context.upstream && !context.channel && context.lines.length === 0) return null;
  return <div className="q-evidence">
    <p className="m-0 text-[12px] text-ink-3">From the module</p>
    {context.upstream && <p className="m-0 whitespace-pre-wrap">“{context.upstream}”</p>}
    {context.channel && <code className="font-data text-[12px] text-ink break-words">{context.channel}</code>}
    {context.arrival && <p className="m-0 text-[12px] text-ink-3">one per {context.arrival}, by the module’s meta naming</p>}
    {context.lines.length > 0 && <details>
      <summary className="cursor-pointer text-[12.5px] text-ink-2">From main.nf</summary>
      <pre className="font-data text-[12px] whitespace-pre-wrap break-words max-w-full overflow-auto m-0 mt-1">{context.lines.map((line) => `${line.number}  ${line.text}`).join("\n")}</pre>
    </details>}
  </div>;
}

/** Another registry entry, or a new name of the person's own where the question allows one. */
function OtherAnswer({ item, question, chosen, options, onAnswer, pending }: {
  item: ItemView; question: Asked; chosen?: string; options: string[]; pending: boolean;
  onAnswer: (value: { choice: string; new?: boolean }) => void;
}) {
  const kind = pickerFor(item.key);
  const [picking, setPicking] = useState(false);
  const [proposing, setProposing] = useState(false);
  const [own, setOwn] = useState("");
  const input = useId();
  const choices = useChoices(picking);
  const entries: PickerEntry[] = !choices.data || !kind ? []
    : kind === "role" ? roleEntries(choices.data) : typeEntries(choices.data);
  const allowsNew = question.allows_new !== false;
  const noun = kind === "role" ? "job" : kind === "type" ? "type" : "answer";
  return <div className="flex flex-col gap-2">
    <div className="flex flex-wrap gap-2">
      {kind && <button type="button" className="option-more flex-1" onClick={() => setPicking(true)}>
        Pick another registry {noun}…
      </button>}
      {allowsNew && !proposing && <button type="button" className="option-more flex-1" onClick={() => setProposing(true)}>
        {kind ? `Propose a new ${noun}` : "Another answer"}
      </button>}
    </div>
    {picking && choices.isError && <Failed error={choices.error} padded={false} />}
    {picking && choices.data && (
      <div className="picker-anchor">
        <button type="button" aria-label="Close the picker" className="picker-outside" onClick={() => setPicking(false)} />
        <RegistryPicker
          title={kind === "role" ? "Choose a job" : "Choose a type"}
          entries={entries} closest={options} chosen={chosen}
          before={kind === "role" ? "Tools doing this job read" : "Made by"}
          after={kind === "role" ? "and make" : "Read by"}
          emptyBefore={kind === "role" ? "No tool yet" : "Nothing: a person supplies it"}
          onClose={() => setPicking(false)}
          onPick={(picked) => { onAnswer({ choice: picked }); setPicking(false); }}
          onNew={allowsNew && kind === "type" ? (name) => { onAnswer({ choice: name, new: true }); setPicking(false); } : undefined}
          newLabel="New type"
        />
      </div>
    )}
    {proposing && <form className="flex flex-wrap gap-2" onSubmit={(e) => {
      e.preventDefault();
      if (own.trim()) onAnswer({ choice: own.trim(), new: true });
    }}>
      <label className="sr-only" htmlFor={input}>{kind ? `A new ${noun}'s name` : "Another answer"}</label>
      <input id={input} value={own} onChange={(e) => setOwn(e.target.value)} autoFocus
             placeholder={kind === "type" ? "e.g. assembly.fasta" : kind === "role" ? "e.g. binning" : "Your answer"}
             className="flex-1 min-w-0 font-data text-[12.5px] p-2 bg-surface text-ink border border-line-2 rounded-control" />
      <button type="submit" className="control" disabled={pending || !own.trim()}>Answer with it</button>
      <button type="button" className="control" onClick={() => setProposing(false)}>Cancel</button>
    </form>}
    {kind && allowsNew && <p className="m-0 text-[12px] text-ink-3">A new {noun} becomes a vocabulary proposal that a person reviews.</p>}
  </div>;
}
