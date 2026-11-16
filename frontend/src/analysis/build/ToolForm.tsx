import { useState } from "react";
import { Link } from "react-router";

import { type Answered, type AnsweredStep, open, optionalOpen } from "../../build/useBuilder";
import { type Source, SourceTag } from "../../ui/SourceTag";

/** Where one input comes from: another step's output, or the analysis's Data (a table, by type). */
export type InputFrom = {
  port: string;
  from: { step: string } | { data: string; count?: number | null; href: string } | { none: true };
};

type AiChoice = { what: string; because: string };

/** A step's settings as a form (board: Build, the Step tab).
 *
 *  **Basic** is what the person has to look at: a value nobody decided, one a person set, one the
 *  AI set. **Advanced** is what a rule, a convention or a measurement settled; it stays folded. The
 *  registry declares no basic/advanced flag, no help line and no unit, so the split is derived from
 *  who decided each value, and the help is the value's own reason.
 *
 *  Inputs are **bindings, never paths**: an input reads another step's output or a Data table, and
 *  the form says which and links to it (invariant 15). */
export function ToolForm({ step, aiChoices, inputs, onSet, onAsk, onAccept, onConnect }: {
  step: AnsweredStep;
  aiChoices: AiChoice[];
  inputs: InputFrom[];
  onSet: (setting: string, value: string) => void;
  onAsk: (setting: string) => void;
  /** The person accepts what the AI chose at this step. */
  onAccept: () => void;
  /** Feed an input nothing feeds: pick a step that makes what it reads. */
  onConnect?: (port: string) => void;
}) {
  const [advanced, setAdvanced] = useState(false);
  const aiFor = (name: string) => aiChoices.find((c) => c.what.startsWith(`set ${name} to `));
  const basic = step.settings.filter((s) => isBasic(s, !!aiFor(s.name)));
  const rest = step.settings.filter((s) => !isBasic(s, !!aiFor(s.name)));
  const row = (s: Answered) => (
    <Row key={s.name} setting={s} process={step.process} ai={aiFor(s.name)} onSet={onSet} onAsk={onAsk}
         onAccept={onAccept} />
  );

  return (
    <div className="flex flex-col">
      {inputs.length > 0 && (
        <Section label="Inputs">
          {inputs.map(({ port, from }) => (
            <div key={port} className="flex items-baseline gap-3 px-5 py-[7px]">
              <span className="font-data text-[12.5px] text-ink">{port}</span>
              {"step" in from ? <span className="text-[12.5px] text-ink-3">from {from.step}</span>
                : "none" in from ? (
                  <>
                    <span className="text-[12.5px] text-ink-3">not connected</span>
                    {onConnect && (
                      <button type="button" onClick={() => onConnect(port)} aria-label={`Connect ${port}`}
                              className="ml-auto px-3 py-[3px] rounded-button border border-line bg-surface text-[12px]
                                         font-medium text-ink cursor-pointer hover:bg-hover">
                        Connect
                      </button>
                    )}
                  </>
                )
                : <Link to={from.href} className="text-[12.5px] text-now-ink">
                    {from.count != null ? `${from.data} · ${from.count}` : from.data}
                  </Link>}
            </div>
          ))}
        </Section>
      )}
      {step.settings.length === 0 && <p className="m-0 px-5 py-3 text-[13px] text-ink-3">No settings.</p>}
      {basic.length > 0 && <Section label="Basic">{basic.map(row)}</Section>}
      {rest.length > 0 && (
        <>
          <button type="button" aria-expanded={advanced} onClick={() => setAdvanced(!advanced)}
                  className="flex items-center gap-2 px-5 py-[10px] border-0 border-t border-line-soft bg-transparent
                             text-left text-[12.5px] font-semibold text-ink-2 cursor-pointer hover:text-ink">
            Advanced <span className="font-normal text-ink-3">{rest.length}</span>
            <span aria-hidden className="ml-auto">{advanced ? "▾" : "▸"}</span>
          </button>
          {advanced && <Section label="Advanced" bare>{rest.map(row)}</Section>}
        </>
      )}
    </div>
  );
}

function isBasic(s: Answered, ai: boolean): boolean {
  return ai || !!s.answered || open(s) || optionalOpen(s);
}

/** Who supplied a value, as the source tags say it. */
export function sourceOf(s: Answered, ai: boolean): Source {
  if (ai) return "ai";
  if (s.answered) return "you";
  if (s.tier === 4) return "not_set";
  if (s.tier === 3 && s.evidence === "measured") return "measured";
  return s.tier === 2 ? "default" : "rule";
}

function Section({ label, bare = false, children }: { label: string; bare?: boolean; children: React.ReactNode }) {
  return (
    <div role="group" aria-label={label} className="flex flex-col border-t border-line-soft first:border-t-0 pb-2">
      {!bare && (
        <div className="px-5 pt-3 pb-1 text-[12.5px] font-semibold text-ink-2">{label}</div>
      )}
      {children}
    </div>
  );
}

function Row({ setting: s, process, ai, onSet, onAsk, onAccept }: {
  setting: Answered; process: string; ai: AiChoice | undefined;
  onSet: (setting: string, value: string) => void; onAsk: (setting: string) => void; onAccept: () => void;
}) {
  // An open value's recorded reason is the resolver's placeholder for *nobody decided this*; say
  // it in the person's words (issue 384). The pipeline file keeps the record verbatim.
  const help = ai?.because
    || (optionalOpen(s) ? `No rule or answer decides this. Left unset, ${process} uses its tool's own default.`
      : open(s) ? `No rule or answer decides this, and ${process} cannot run without it.`
      : s.reason || s.because);
  return (
    <div data-setting={s.name} className="flex flex-col gap-[6px] px-5 py-[9px]">
      <div className="flex items-center gap-2 min-w-0">
        <span className="font-data text-[12.5px] font-medium text-ink truncate">{s.name}</span>
        <SourceTag source={sourceOf(s, !!ai)} />
        <button type="button" onClick={() => onAsk(s.name)} aria-label={`Ask AI about ${s.name}`}
                className="ml-auto shrink-0 px-2 py-[3px] rounded-control border border-ai-line bg-ai-soft text-[11.5px]
                           font-semibold text-ai cursor-pointer hover:brightness-95">
          ✦ Ask AI
        </button>
      </div>
      <Control setting={s} onSet={(v) => onSet(s.name, v)} />
      {help && <p className="m-0 text-[12px] text-ink-2">{help}</p>}
      {ai && (
        <div className="flex items-center gap-2 px-3 py-2 rounded-control bg-ai-soft border border-ai-line">
          <span className="text-[12px] text-ink">The AI chose this. Keep it?</span>
          <button type="button" onClick={onAccept}
                  className="ml-auto px-3 py-[3px] rounded-button border border-line bg-surface text-[12px] font-medium cursor-pointer">
            Accept
          </button>
        </div>
      )}
    </div>
  );
}

const FIELD = `px-[10px] py-[6px] rounded-control border border-line bg-surface text-[13px] text-ink outline-none
               focus:shadow-[var(--ring)]`;

/** The control a setting's kind calls for. A value is sent as text, as the draft stores it. */
function Control({ setting: s, onSet }: { setting: Answered; onSet: (value: string) => void }) {
  const kind = s.domain?.kind;
  const value = s.value ?? "";
  if (kind === "boolean") {
    return (
      <div role="radiogroup" aria-label={s.name} className="flex self-start rounded-control border border-line overflow-hidden">
        {(["true", "false"] as const).map((v) => (
          <button key={v} type="button" role="radio" aria-checked={value === v} onClick={() => onSet(v)}
                  className={`px-3 py-[4px] border-0 text-[12.5px] cursor-pointer
                              ${value === v ? "bg-now-soft text-now-ink" : "bg-surface text-ink-2"}`}>
            {v === "true" ? "Yes" : "No"}
          </button>
        ))}
      </div>
    );
  }
  if (kind === "enum" && s.domain!.values.length > 0) {
    return (
      <select aria-label={s.name} value={value} onChange={(e) => onSet(e.target.value)} className={`${FIELD} self-start`}>
        {!value && <option value="">Choose…</option>}
        {s.domain!.values.map((v) => <option key={v} value={v}>{v}</option>)}
      </select>
    );
  }
  if (kind === "integer" || kind === "number") {
    const { minimum: min, maximum: max } = s.domain!;
    return <NumberField name={s.name} value={value} min={min} max={max} step={kind === "integer" ? 1 : "any"} onSet={onSet} />;
  }
  return <TextField name={s.name} value={value} onSet={onSet} />;
}

/** Sent when the person leaves the field or presses Enter, not on every key. */
function TextField({ name, value, onSet }: { name: string; value: string; onSet: (v: string) => void }) {
  const [text, setText] = useState(value);
  const [was, setWas] = useState(value);
  if (value !== was) { setWas(value); setText(value); }
  const send = () => { if (text !== value) onSet(text); };
  return (
    <input aria-label={name} value={text} onChange={(e) => setText(e.target.value)} onBlur={send}
           onKeyDown={(e) => { if (e.key === "Enter") send(); }} className={FIELD} />
  );
}

function NumberField({ name, value, min, max, step, onSet }: {
  name: string; value: string; min?: number | null; max?: number | null; step: number | "any"; onSet: (v: string) => void;
}) {
  const [text, setText] = useState(value);
  const [was, setWas] = useState(value);
  if (value !== was) { setWas(value); setText(value); }
  const send = () => { if (text !== value && text.trim() !== "") onSet(text.trim()); };
  const range = min != null && max != null ? `${min}–${max}` : min != null ? `≥ ${min}` : max != null ? `≤ ${max}` : null;
  return (
    <div className="flex items-center gap-3">
      <input type="number" aria-label={name} value={text} min={min ?? undefined} max={max ?? undefined} step={step}
             onChange={(e) => setText(e.target.value)} onBlur={send}
             onKeyDown={(e) => { if (e.key === "Enter") send(); }} className={`${FIELD} w-[140px]`} />
      {range && <span className="text-[12px] text-ink-3">{range}</span>}
    </div>
  );
}
