import { useState } from "react";

import type { AuthoringBlock, DraftGraph } from "../../api/types";
import { open, optionalOpen, type AnsweredStep } from "../useBuilder";
import { QuestionCard } from "./blocks/QuestionCard";
import { SettingCard } from "./blocks/SettingCard";
import { StepTools } from "./blocks/StepTools";
import { processName } from "./format";

type SettingBlock = Extract<AuthoringBlock, { kind: "setting_request" }>;
type Setting = AnsweredStep["settings"][number];

/** **A step opened over the conversation** (one builder plan 3; the *Question* board). Its values
 *  grouped by how they were decided — what still needs the person first, as questions; then what
 *  was measured; then what a rule settled, folded — each opening its reason in place; then the
 *  step's tools. × and *Back to the conversation* return to the chat where it was. */
export function StepSheet({ node, step, graph, requests, onSetParam, onEdit, onClose }: {
  node: string;
  step: AnsweredStep | undefined;
  graph: DraftGraph;
  /** The latest reply's setting requests for this step. */
  requests: SettingBlock[];
  onSetParam: (node: string, setting: string, value: string, why?: string) => void;
  onEdit: (graph: DraftGraph) => void;
  onClose: () => void;
}) {
  const [showSettled, setShowSettled] = useState(false);
  const settings = step?.settings ?? [];
  const asking = [...settings.filter(open), ...settings.filter(optionalOpen)];
  const measured = settings.filter((s) => s.tier === 3 && (s.evidence === "measured" || s.evidence === "read_by_ai"));
  const settled = settings.filter((s) => !asking.includes(s) && !measured.includes(s));

  return (
    <section aria-label={`step ${processName(node)}`} className="flex flex-col gap-4">
      <div className="flex items-start gap-2">
        <div className="flex-1 min-w-0">
          <button type="button" onClick={onClose}
                  className="bg-transparent border-0 p-0 text-[12px] text-now-ink cursor-pointer">
            ‹ Back to the conversation
          </button>
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
      {asking.length > 0 && (
        <Group label="Needs you" count={asking.length}>
          {/* What needs you first, then what is optional (issue 384). */}
          {asking.map((setting) => (
            <QuestionCard key={`${node}.${setting.name}`} setting={setting} step={processName(node)}
                          onSave={(value, why) => onSetParam(node, setting.name, value, why)} onCancel={onClose} />
          ))}
        </Group>
      )}
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
      <section aria-label="Change this step" className="flex flex-col gap-3">
        <h3 className="m-0 text-[13px] font-semibold text-ink-2">Change this step</h3>
        <StepTools key={node} node={node} step={step} graph={graph} onEdit={onEdit} />
        {requests.map((r) => <SettingCard key={r.id} block={r} onApply={onSetParam} />)}
      </section>
    </section>
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
