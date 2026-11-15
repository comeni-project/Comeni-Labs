import { useState } from "react";

import type { DraftGraph } from "../../api/types";
import { open, optionalOpen, type AnsweredStep } from "../useBuilder";
import { QuestionCard } from "./blocks/QuestionCard";
import { Secondary } from "./blocks/parts";
import { StepTools } from "./blocks/StepTools";
import { processName } from "./format";

type Setting = AnsweredStep["settings"][number];

export type CardKind = "settings" | "values" | "inputs" | "swap" | "remove";

/** Whether a step has anything for the *Inputs…* card: an optional input, or parts. */
export const hasInputs = (step: AnsweredStep | undefined) =>
  Boolean(step?.parts) || (step?.ports ?? []).some((p) => p.side === "in" && p.optional);

/** **A step's card, beside the step on the canvas** (#499; the *Question* board's content). One
 *  at a time, opened from a click (Settings) or the step's menu; the conversation stays where it
 *  is. *Settings*: what the AI chose there, then what still needs the person, as questions; then
 *  optional values, what was measured, and what a rule settled, folded — each opening its reason
 *  in place. *Inputs*: each optional input off, optional or required, and parts. *Swap* and
 *  *Remove* are the manual builder's tools, opened straight. × or Esc closes. */
export function StepCard({ node, kind, onKind, step, graph, onSetParam, onEdit, onClose, onSwitchInput,
  onWhole, aiChoices = [], onReviewed }: {
  node: string;
  kind: CardKind;
  /** Switch the card to another of the step's tools. */
  onKind: (kind: CardKind) => void;
  step: AnsweredStep | undefined;
  graph: DraftGraph;
  /** What the AI chose at this step that nobody has reviewed yet (#463): `chose …`, `set … to …`. */
  aiChoices?: string[];
  /** The person has looked at what the AI chose here. */
  onReviewed?: (node: string) => void;
  onSetParam: (node: string, setting: string, value: string, why?: string) => void;
  onEdit: (graph: DraftGraph) => void;
  onClose: () => void;
  /** Switch a tool's optional input off, optional or required: the person's change (issue 460). */
  onSwitchInput?: (contract: string, port: string, state: InputState) => void;
  /** Keep a tool whole, or let it run on parts of each sample again (issue 466). */
  onWhole?: (contract: string, whole: boolean) => void;
}) {
  const [showSettled, setShowSettled] = useState(false);
  const settings = step?.settings ?? [];
  // **Needs you, then optional, apart** (issues 384, 494): counted together, an optional prefix read
  // "Needs you · 1" beside "none need you".
  const asking = settings.filter(open);
  const optionalValues = settings.filter(optionalOpen);
  const measured = settings.filter((s) => s.tier === 3 && (s.evidence === "measured" || s.evidence === "read_by_ai"));
  const settled = settings.filter((s) => !asking.includes(s) && !measured.includes(s));
  const optional = (step?.ports ?? []).filter((p) => p.side === "in" && p.optional);

  return (
    <section aria-label={`step card ${processName(node)}`} className="flex flex-col gap-4"
             onKeyDown={(e) => { if (e.key === "Escape") { e.stopPropagation(); onClose(); } }}>
      <div className="flex items-start gap-2">
        <div className="flex-1 min-w-0">
          <p className="m-0 text-label text-ink-3">{KIND_WORDS[kind]}</p>
          <h2 className="m-0 mt-[2px] font-data text-[15px] font-semibold text-ink truncate" title={processName(node)}>
            {processName(node)}
          </h2>
          {step && <p className="m-0 mt-[2px] font-data text-[11.5px] text-ink-3 break-all">{step.contract_id}</p>}
        </div>
        <button type="button" aria-label="Close the step" onClick={onClose}
                className="w-[32px] h-[32px] grid place-items-center p-0 rounded-control border-0 bg-transparent
                           text-ink-2 text-[20px] leading-none cursor-pointer hover:text-ink focus-visible:shadow-[var(--ring)]">
          ×
        </button>
      </div>
      {kind === "swap" || kind === "remove" || kind === "values" ? (
        <StepTools key={`${node}-${kind}`} node={node} step={step} graph={graph} onEdit={onEdit}
                   start={kind === "values" ? "settings" : kind} onDone={onClose} />
      ) : kind === "inputs" ? (<>
      {optional.length > 0 && step && (
        <Group label="Optional inputs" count={optional.length}>
          {optional.map((port) => (
            <OptionalInput key={port.name} port={port}
                           onSwitch={onSwitchInput && ((state) => onSwitchInput(step.contract_id, port.name, state))} />
          ))}
        </Group>
      )}
      {step?.parts && (
        <section aria-label="Runs in parts" className="flex flex-col gap-2">
          <h3 className="m-0 text-label text-ink-3">
            {step.parts.on ? "Runs in parts" : "Can run in parts"}
          </h3>
          <p className="m-0 text-[12.5px] text-ink-2">{step.parts.because}</p>
          <label className="flex items-center gap-2 text-[12.5px] text-ink">
            <input type="checkbox" checked={!step.parts.on} disabled={!onWhole}
                   onChange={(e) => onWhole?.(step.contract_id, e.target.checked)} />
            Run each sample whole
          </label>
        </section>
      )}
      </>) : (<>
      {aiChoices.length > 0 && (
        <section aria-label="What the AI chose" className="flex flex-col gap-2 px-[12px] py-[10px] rounded-panel"
                 style={{ background: "var(--now-soft)" }}>
          <h3 className="m-0 text-[13px] font-semibold text-now-ink">Chosen by the AI</h3>
          <ul className="m-0 pl-[18px] text-[12.5px] text-ink flex flex-col gap-[2px]">
            {aiChoices.map((what) => <li key={what}>{what}</li>)}
          </ul>
          <p className="m-0 text-[12px] text-ink-2">Ask in the chat why, or change it below.</p>
          {onReviewed && (
            <span className="self-start"><Secondary onClick={() => onReviewed(node)}>Looks right</Secondary></span>
          )}
        </section>
      )}
      {([["Needs you", asking], ["Optional to answer", optionalValues]] as const).map(([label, list]) =>
        list.length > 0 && (
          <Group key={label} label={label} count={list.length}>
            {list.map((setting) => (
              <QuestionCard key={`${node}.${setting.name}`} setting={setting} step={processName(node)}
                            onSave={(value, why) => onSetParam(node, setting.name, value, why)} onCancel={onClose} />
            ))}
          </Group>
        ))}
      {measured.length > 0 && (
        <Group label="Measured" count={measured.length}>
          {measured.map((s) => <Value key={s.name} setting={s} />)}
        </Group>
      )}
      {settled.length > 0 && (
        <Group label="Settled by a rule" count={settled.length}
               toggle={<button type="button" onClick={() => setShowSettled(!showSettled)}
                               className="bg-transparent border-0 p-0 text-[11.5px] text-now-ink underline cursor-pointer">
                 {showSettled ? "hide" : "show"}
               </button>}>
          {showSettled && settled.map((s) => <Value key={s.name} setting={s} />)}
        </Group>
      )}
      <div className="flex flex-wrap gap-2">
        <Secondary disabled={!step} onClick={() => onKind("values")}>Edit values</Secondary>
        {hasInputs(step) && <Secondary onClick={() => onKind("inputs")}>Inputs…</Secondary>}
        <Secondary disabled={!step} onClick={() => onKind("swap")}>Swap tool…</Secondary>
      </div>
      </>)}
    </section>
  );
}

const KIND_WORDS: Record<CardKind, string> = {
  settings: "Settings", values: "Edit values", inputs: "Inputs", swap: "Swap tool", remove: "Remove step",
};

type InputState = "off" | "optional" | "required";
const STATES: { value: InputState; label: string }[] = [
  { value: "off", label: "Off" }, { value: "optional", label: "Optional" }, { value: "required", label: "Required" },
];

/** One input the tool can run without: what it adds, its state and why, and the switch. Optional
 *  means each run may supply the file or leave it empty; required means every run supplies it. */
function OptionalInput({ port, onSwitch }: {
  port: AnsweredStep["ports"][number];
  onSwitch?: (state: InputState) => void;
}) {
  const state = (port.state ?? "off") as InputState;
  return (
    <div className="rounded-button border border-dashed border-line-2 px-[10px] py-[8px] flex flex-col gap-[6px]">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <span className="font-data text-[13px] text-ink">{port.name}</span>
        <span className="font-data text-[12px] text-ink-3">{port.type_id}</span>
      </div>
      {(port.adds ?? []).length > 0 && (
        <p className="m-0 text-[12px] text-ink-2">adds {(port.adds ?? []).join(", ")}</p>
      )}
      <div role="radiogroup" aria-label={`${port.name}: off, optional or required`} className="flex flex-wrap gap-[6px]">
        {STATES.map(({ value, label }) => (
          <label key={value}
                 className={`min-h-[32px] px-[10px] inline-flex items-center gap-[6px] rounded-control border text-[12.5px] cursor-pointer
                             ${state === value ? "border-now bg-now-soft text-ink" : "border-line text-ink-2"}`}>
            <input type="radio" name={`input-${port.name}`} value={value} checked={state === value}
                   disabled={!onSwitch} onChange={() => onSwitch?.(value)} className="accent-[var(--now)]" />
            {label}
          </label>
        ))}
      </div>
      {port.reason && <p className="m-0 text-[11.5px] text-ink-3">{port.reason}</p>}
    </div>
  );
}

function Group({ label, count, toggle, children }: {
  label: string; count: number; toggle?: React.ReactNode; children: React.ReactNode;
}) {
  return (
    <section aria-label={label} className="flex flex-col gap-2">
      <h3 className="m-0 text-label text-ink-3">{label} · {count} {toggle}</h3>
      {children}
    </section>
  );
}

/** One value, its reason opening in place, as the pipeline file opens it. */
function Value({ setting }: { setting: Setting }) {
  const [open, setOpen] = useState(false);
  const reason = setting.reason || setting.because;
  return (
    <div className="rounded-button border border-line">
      <button type="button" aria-expanded={open} onClick={() => setOpen(!open)}
              className="w-full flex items-baseline justify-between gap-3 px-[10px] py-[8px] bg-transparent border-0
                         text-left text-[13px] text-ink cursor-pointer hover:bg-[var(--hover)]">
        <span className="font-data">{setting.name}</span>
        <span className="font-data text-ink-2 truncate">{String(setting.value ?? "")}</span>
      </button>
      {open && reason && <p className="m-0 px-[10px] pb-[8px] text-[12px] text-ink-2">{reason}</p>}
    </div>
  );
}
