import { useState } from "react";

import type { AuthoringBlock, AuthoringSession, AuthoringVocabulary, DraftGraph } from "../../api/types";
import { open, optionalOpen, type AnsweredStep } from "../useBuilder";
import { ChangeSetCard } from "./blocks/ChangeSetCard";
import { QuestionCard } from "./blocks/QuestionCard";
import { SettingCard } from "./blocks/SettingCard";
import { StepTools } from "./blocks/StepTools";
import { byEdit, SuggestionCard } from "./blocks/SuggestionCard";
import { Composer } from "./Composer";
import { CurrentFacts, type CorrectFact } from "./CurrentFacts";
import { docked, processName } from "./format";
import { QuestionDock } from "./QuestionDock";
import { StepLine } from "./StepLine";
import { StepStrip } from "./StepStrip";
import { Stream } from "./Stream";
import type { WaitingProps } from "./Waiting";

type ChangeBlock = Extract<AuthoringBlock, { kind: "change_set" }>;
type SettingBlock = Extract<AuthoringBlock, { kind: "setting_request" }>;
/** **One conversation beside the canvas** (one builder plan 3). The plan as a strip on top; then
 * what was said, with what the engine waits on as the newest message, and the changes offered
 * from the chat or from a hand edit after it; the open question docked above the composer once
 * the person talks past it; the composer, never locked. A step opened from the canvas or the strip
 * shows over the conversation, and closing it returns there.
 */
export function ChatPanel({
  session,
  waiting,
  selected,
  onSelect,
  graph,
  steps,
  onEdit,
  onSetParam,
  onApplyChange,
  suggestions,
  composer,
  composerHint,
  composerDisabled,
  onCompose,
  onSay,
  sending,
  onRetry,
  declarations,
  onCorrect,
  onRelease,
  correcting,
  factsRequest,
  notices,
}: {
  session: AuthoringSession;
  waiting: Omit<WaitingProps, "session" | "onAsk" | "saying" | "onSelect">;
  sending: string[];
  selected: string | null;
  onSelect: (node: string | null) => void;
  /** The draft as drawn — what a step's tools change. */
  graph: DraftGraph;
  /** Each step with what the person typed laid over it, so an answered value is not asked again. */
  steps: Record<string, AnsweredStep>;
  onEdit: (graph: DraftGraph) => void;
  onSetParam: (node: string, setting: string, value: string, why?: string) => void;
  onApplyChange: (block: ChangeBlock) => void;
  suggestions: {
    busy: boolean;
    onApply: (id: string) => void;
    onDismiss: (id: string) => void;
  };
  composer: string;
  composerHint: string | undefined;
  composerDisabled: boolean;
  onCompose: (text: string) => void;
  onSay: (text: string) => void;
  onRetry: () => void;
  declarations?: AuthoringVocabulary["measurements"];
  onCorrect?: CorrectFact;
  onRelease?: (type: string, states: string[]) => Promise<unknown>;
  correcting: boolean;
  factsRequest: number;
  notices: React.ReactNode;
}) {
  const [showRequest, setShowRequest] = useState(0);
  const [planOpen, setPlanOpen] = useState(false);
  const say = (text: string) => {
    onSelect(null);
    onSay(text);
  };

  const pending = session.pending_proposal;
  const ghost = pending?.block.kind === "step_proposal" ? pending.block.node : null;
  // **A selected step that is in the draft gets its tools**; the step on offer has its own card.
  const editable = selected !== null && selected !== ghost && graph.nodes.some((n) => n.id === selected)
    ? selected : null;
  const latest = [...session.turns].reverse().find((t) => t.role === "assistant" && t.state === "answered");
  const changes = (latest?.blocks ?? []).filter((b): b is ChangeBlock => b.kind === "change_set");
  const requests = (latest?.blocks ?? []).filter((b): b is SettingBlock => b.kind === "setting_request");
  const needing = Object.entries(steps)
    .map(([node, step]) => [node, step.settings.filter(open).length] as const)
    .filter(([, count]) => count > 0)
    .sort(([a], [b]) => a.localeCompare(b));
  const waits = pending !== null || session.phase === "stopped" || session.phase === "resolving";
  const dock = pending !== null && !editable && docked(session) && (pending.kind === "gap" ||
    pending.kind === "pacing" || pending.kind === "step");
  // **A hand edit's reading comes first**: nothing it means changes until the person says yes.
  const { readings, suggestions: offered } = byEdit(session.suggestions ?? []);
  const fromChat = offered.length > 0 || changes.length > 0
    || requests.some((r) => r.node !== editable);

  return (
    <section aria-label="build panel"
             className="living-rail flex flex-col min-h-0 ml-[8px] mr-[28px] mt-[4px] mb-[24px] rounded-panel border border-line overflow-hidden"
             style={{ background: "var(--surface)" }}>
      {notices}
      <StepStrip session={session} selected={editable} onSelect={onSelect}
                 planOpen={planOpen} onTogglePlan={() => setPlanOpen(!planOpen)} />
      {planOpen && !editable && (
        <div className="max-h-[45%] overflow-auto px-4 pt-3 pb-2 border-b border-line">
          <StepLine session={session} steps={steps} selected={selected} onSelect={onSelect} />
        </div>
      )}
      <div className="flex-1 min-h-0 overflow-auto px-4 pt-4 pb-4">
        {editable ? (
          // **A step opened over the conversation** (one builder plan 3); × returns to it.
          <section aria-label={`step ${processName(editable)}`} className="flex flex-col gap-4">
            <div className="flex items-start gap-2">
              <div className="flex-1 min-w-0">
                <button type="button" onClick={() => onSelect(null)}
                        className="bg-transparent border-0 p-0 text-[12px] text-now-ink cursor-pointer">
                  ‹ Back to the conversation
                </button>
                <h2 className="m-0 mt-[2px] font-data text-[15px] font-semibold text-ink truncate" title={processName(editable)}>
                  {processName(editable)}
                </h2>
                {steps[editable] && (
                  <p className="m-0 mt-[2px] font-data text-[11.5px] text-ink-3 break-all">{steps[editable].contract_id}</p>
                )}
              </div>
              <button type="button" aria-label="Close the step" onClick={() => onSelect(null)}
                      className="w-[32px] h-[32px] grid place-items-center p-0 rounded-control border-0
                                 bg-transparent text-ink-2 text-[20px] leading-none cursor-pointer hover:text-ink
                                 focus-visible:shadow-[var(--ring)]">
                ×
              </button>
            </div>
            {/* What needs you first, then what is optional (issue 384). */}
            {[...(steps[editable]?.settings ?? []).filter(open),
              ...(steps[editable]?.settings ?? []).filter(optionalOpen)].map((setting) => (
              <QuestionCard key={`${editable}.${setting.name}`} setting={setting}
                            step={processName(editable)}
                            onSave={(value, why) => onSetParam(editable, setting.name, value, why)}
                            onCancel={() => onSelect(null)} />
            ))}
            <section aria-label="Change this step" className="flex flex-col gap-3">
              <h3 className="m-0 text-[13px] font-semibold text-ink-2">Change this step</h3>
              <StepTools key={editable} node={editable} step={steps[editable]} graph={graph} onEdit={onEdit} />
              {requests.filter((r) => r.node === editable).map((r) => (
                <SettingCard key={r.id} block={r} onApply={onSetParam} />
              ))}
            </section>
          </section>
        ) : (
          <div className="flex flex-col gap-4">
            <Stream session={session} sending={sending} onRetry={onRetry} onAsk={say}
                    waiting={{ ...waiting, onSelect }} showRequest={showRequest} />
            {readings.length > 0 && (
              <section aria-label="From your edit" className="flex flex-col gap-2">
                {readings.map((r) => (
                  <SuggestionCard key={r.id} suggestion={r} busy={suggestions.busy}
                                  onApply={suggestions.onApply} onDismiss={suggestions.onDismiss} />
                ))}
              </section>
            )}
            {fromChat && (
              <section aria-label="From the conversation" className="flex flex-col gap-3">
                {offered.length > 0 && (
                  <div role="list" aria-label="suggestions waiting for you" className="flex flex-col gap-2">
                    {offered.map((s) => (
                      <div role="listitem" key={s.id}>
                        <SuggestionCard suggestion={s} busy={suggestions.busy}
                                        onApply={suggestions.onApply} onDismiss={suggestions.onDismiss} />
                      </div>
                    ))}
                  </div>
                )}
                {requests.filter((r) => r.node !== editable).map((r) => (
                  <SettingCard key={r.id} block={r} onApply={onSetParam} />
                ))}
                {changes.map((c) => <ChangeSetCard key={c.id} block={c} onApply={onApplyChange} />)}
              </section>
            )}
            {!waits && needing.length > 0 && (
              // **Not "nothing is waiting" while a value needs you** (issue 385): the engine says
              // which steps still do, each the way to open it.
              <section aria-label="Still needs you" className="flex flex-col gap-2">
                <p className="m-0 text-[13px] text-ink">Some values still need you before it can run:</p>
                {needing.map(([node, count]) => (
                  <button key={node} type="button" onClick={() => onSelect(node)}
                          className="text-left px-[12px] py-[9px] rounded-button border bg-transparent cursor-pointer
                                     text-[13px] text-ink hover:bg-[var(--hover)] focus-visible:shadow-[var(--ring)]"
                          style={{ borderColor: "var(--needs-you)" }}>
                    <span className="font-data font-semibold">{processName(node)}</span>{" "}
                    <span className="text-needs-you-ink">
                      has {count} {count === 1 ? "value that needs" : "values that need"} you
                    </span>
                  </button>
                ))}
              </section>
            )}
            <CurrentFacts session={session} declarations={declarations} onCorrect={onCorrect} onRelease={onRelease}
              openRequest={factsRequest}
              disabled={correcting || session.retired || session.turns.some((t) => t.state === "pending") ||
                session.phase === "resolving"} />
          </div>
        )}
      </div>
      {dock && pending && (
        <QuestionDock proposal={pending} busy={waiting.busy(pending.id)}
                      onAnswer={(option) => waiting.onAccept(pending, option)}
                      onShow={() => setShowRequest((n) => n + 1)} />
      )}
      <div className="px-[16px] pt-[8px] pb-[16px]">
        <Composer value={composer} onChange={onCompose} onSend={say}
                  disabled={composerDisabled} placeholder={composerHint} />
      </div>
    </section>
  );
}
