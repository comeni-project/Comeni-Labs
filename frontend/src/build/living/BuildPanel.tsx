import { useEffect, useRef, useState } from "react";

import type { AuthoringBlock, AuthoringSession, AuthoringVocabulary, DraftGraph } from "../../api/types";
import { open, optionalOpen, type AnsweredStep } from "../useBuilder";
import { ChangeSetCard } from "./blocks/ChangeSetCard";
import { QuestionCard } from "./blocks/QuestionCard";
import { SettingCard } from "./blocks/SettingCard";
import { StepTools } from "./blocks/StepTools";
import { byEdit, SuggestionCard } from "./blocks/SuggestionCard";
import { Chat } from "./Chat";
import { Composer } from "./Composer";
import { CurrentFacts, type CorrectFact } from "./CurrentFacts";
import { processName, waitingOn } from "./format";
import { StepLine } from "./StepLine";
import { Waiting, type WaitingProps } from "./Waiting";

type ChangeBlock = Extract<AuthoringBlock, { kind: "change_set" }>;
type SettingBlock = Extract<AuthoringBlock, { kind: "setting_request" }>;
type Tab = "step" | "assistant";

/** **The panel beside the canvas** (the *Build* and *Question* boards): *Step* holds what the engine
 * has settled and what it is waiting on; *Assistant* is the conversation.
 *
 * The composer sits under both, because a person can ask at any moment; what they say is a turn,
 * so the panel turns to the Assistant to show the answer. A reply that lands while Step is showing
 * marks the Assistant tab rather than taking the panel away from the card being read.
 */
export function BuildPanel({
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
  saying,
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
  saying: string | null;
  onRetry: () => void;
  declarations?: AuthoringVocabulary["measurements"];
  onCorrect?: CorrectFact;
  onRelease?: (type: string, states: string[]) => Promise<unknown>;
  correcting: boolean;
  factsRequest: number;
  notices: React.ReactNode;
}) {
  const [tab, setTab] = useState<Tab>("step");
  const [unread, setUnread] = useState(false);
  const replies = session.turns.filter((t) => t.role === "assistant" && t.state === "answered").length;
  const seen = useRef(replies);
  useEffect(() => {
    if (replies > seen.current && tab !== "assistant") setUnread(true);
    seen.current = replies;
  }, [replies, tab]);

  const show = (next: Tab) => {
    setTab(next);
    if (next === "assistant") setUnread(false);
  };
  const say = (text: string) => {
    show("assistant");
    onSay(text);
  };
  const point = (node: string | null) => {
    show("step");
    if (node) onSelect(node);
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
  const waits = pending !== null || session.phase === "stopped" || session.phase === "resolving"
    || (saying === null && waitingOn(session) !== null);
  // **A hand edit's reading comes first**: nothing it means changes until the person says yes.
  const { readings, suggestions: offered } = byEdit(session.suggestions ?? []);
  const fromChat = offered.length > 0 || changes.length > 0
    || requests.some((r) => r.node !== editable);

  return (
    <section aria-label="build panel"
             className="living-rail flex flex-col min-h-0 ml-[8px] mr-[28px] mt-[4px] mb-[24px] rounded-panel border border-line overflow-hidden"
             style={{ background: "var(--surface)" }}>
      <div className="flex items-center mx-4 mt-4">
        <div role="tablist" aria-label="the panel" className="flex gap-1 p-1 rounded-button"
             style={{ background: "var(--paper)" }}>
          <PanelTab id="step" current={tab} onShow={show}>Step</PanelTab>
          <PanelTab id="assistant" current={tab} onShow={show} unread={unread}>Assistant</PanelTab>
        </div>
        {/* The × the *Question* board draws: only while a step is open, and it closes that step. */}
        {editable && (
          <button type="button" aria-label="Close the step" onClick={() => onSelect(null)}
                  className="ml-auto w-[32px] h-[32px] grid place-items-center p-0 rounded-control border-0
                             bg-transparent text-ink-2 text-[20px] leading-none cursor-pointer hover:text-ink
                             focus-visible:shadow-[var(--ring)]">
            ×
          </button>
        )}
      </div>
      {notices}
      <div className="flex-1 min-h-0 overflow-auto px-4 pt-4 pb-4">
        {tab === "step" ? (
          <div role="tabpanel" id="panel-step" aria-labelledby="tab-step" className="flex flex-col gap-4">
            {readings.length > 0 && (
              <section aria-label="From your edit" className="flex flex-col gap-2">
                {readings.map((r) => (
                  <SuggestionCard key={r.id} suggestion={r} busy={suggestions.busy}
                                  onApply={suggestions.onApply} onDismiss={suggestions.onDismiss} />
                ))}
              </section>
            )}
            {/* **An opened step takes the line's place** (the *Question* board): its name and tool,
                each value it still needs you for as a question, then the quieter tools. */}
            {!editable && <StepLine session={session} steps={steps} selected={selected} onSelect={onSelect} />}
            {editable ? (
              <section aria-label={`step ${processName(editable)}`} className="flex flex-col gap-4">
                <div>
                  <h2 className="m-0 font-data text-[15px] font-semibold text-ink truncate" title={processName(editable)}>
                    {processName(editable)}
                  </h2>
                  {steps[editable] && (
                    <p className="m-0 mt-[2px] font-data text-[11.5px] text-ink-3 break-all">{steps[editable].contract_id}</p>
                  )}
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
            ) : waits ? (
              <Waiting session={session} onAsk={say} saying={saying} onSelect={onSelect} {...waiting} />
            ) : needing.length > 0 ? (
              // **Not "nothing is waiting" while a value needs you** (issue 385): each step that still
              // does, as the way to open it.
              <section aria-label="Still needs you" className="flex flex-col gap-2">
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
            ) : (
              <p className="m-0 text-[13px] text-ink-2">Nothing is waiting for you.</p>
            )}
            {fromChat && (
              <section aria-label="From the conversation" className="flex flex-col gap-3">
                <h2 className="m-0 text-label text-ink-3">From the conversation</h2>
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
            <CurrentFacts session={session} declarations={declarations} onCorrect={onCorrect} onRelease={onRelease}
              openRequest={factsRequest}
              disabled={correcting || session.retired || session.turns.some((t) => t.state === "pending") ||
                session.phase === "resolving"} />
          </div>
        ) : (
          <div role="tabpanel" id="panel-assistant" aria-labelledby="tab-assistant">
            <Chat session={session} saying={saying} failedPhase={session.phase === "failed"}
                  onRetry={onRetry} onPoint={point} />
          </div>
        )}
      </div>
      <div className="px-[16px] pt-[8px] pb-[16px]">
        <Composer value={composer} onChange={onCompose} onSend={say}
                  disabled={composerDisabled} placeholder={composerHint} />
      </div>
    </section>
  );
}

function PanelTab({ id, current, onShow, unread = false, children }: {
  id: Tab; current: Tab; onShow: (tab: Tab) => void; unread?: boolean; children: string;
}) {
  const on = id === current;
  return (
    <button type="button" role="tab" id={`tab-${id}`} aria-controls={`panel-${id}`} aria-selected={on}
            aria-label={unread ? `${children}, new reply` : undefined}
            onClick={() => onShow(id)}
            className={`relative px-3 py-[5px] rounded-control border text-[13px] cursor-pointer
                        focus-visible:shadow-[var(--ring)] ${on ? "text-ink font-semibold" : "text-ink-2 bg-transparent border-transparent"}`}
            style={on ? { background: "var(--surface)", borderColor: "var(--line)" } : undefined}>
      {children}
      {unread && <span aria-hidden className="absolute top-1 right-1 w-[7px] h-[7px] rounded-full"
                       style={{ background: "var(--now)" }} />}
    </button>
  );
}
