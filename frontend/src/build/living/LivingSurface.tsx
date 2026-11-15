import { useEffect, useState } from "react";

import type { AuthoringSession, AuthoringVocabulary, DraftGraph } from "../../api/types";
import type { components } from "../../api/schema";
import { Browse } from "../Browse";
import type { Positions } from "../geometry";
import { type AnsweredStep, withTypedValues } from "../useBuilder";
import type { AnswerValue } from "./AgentQuestion";
import { ChatPanel } from "./ChatPanel";
import type { CorrectFact } from "./CurrentFacts";
import { LivingCanvas } from "./LivingCanvas";
import { LivingHeader } from "./LivingHeader";
import type { ReviewState } from "./LivingNode";
import { PipelineFile } from "./PipelineFile";
import { Understood } from "./Understood";
import type { ServerNotice } from "./useAuthoringSession";
import { useFocus } from "./useFocus";
import { valuesOf } from "./values";

/** The builder's composition (#463): **wires state and callbacks, draws nothing itself.**
 *
 * The canvas, or what was understood, beside the conversation with the agent. The canvas is the
 * pipeline as it stands from the first message: empty until the agent builds, then each step as
 * it lands. The panel's widths are the artboards' (`.living` in `main.css`): 420px, 360px under
 * 1180px, and stacked under 1000px with the conversation first *visually* while the canvas stays
 * first in the document for a screen reader. The panel stacks; it never overlays the graph.
 */
export function LivingSurface({
  session, graph, preview, selected, onSelect, composer, onCompose, sending, onSay, onAnswer, onRetry,
  onUpload, onReviewed, notice = null, onDismiss, declarations, onCorrect, onRelease, onUnits, onTable,
  correcting = false, onSetParam, onSwitchInput, onWhole, onEdit, onAddStep, onRename, run = null,
}: {
  session: AuthoringSession;
  /** The draft as saved — what an edit changes. The canvas draws the session's frame. */
  graph: DraftGraph;
  preview: components["schemas"]["AuthoringPreview"] | null;
  selected: string | null;
  onSelect: (node: string | null) => void;
  composer: string;
  onCompose: (text: string) => void;
  sending: string[];
  onSay: (text: string) => void;
  onAnswer: (questionId: string, value: AnswerValue) => void;
  onRetry: (seq: number) => void;
  onUpload?: (questionId: string, files: File[]) => Promise<unknown>;
  onReviewed: (node: string) => void;
  notice?: ServerNotice | null;
  onDismiss: () => void;
  declarations?: AuthoringVocabulary["measurements"];
  onCorrect?: CorrectFact;
  onRelease?: (type: string, states: string[]) => Promise<unknown>;
  onUnits?: (type: string, on: boolean) => Promise<unknown>;
  onTable?: (type: string, on: boolean) => Promise<unknown>;
  correcting?: boolean;
  onSetParam: (node: string, setting: string, value: string, why?: string) => void;
  onSwitchInput?: (contract: string, port: string, state: "off" | "optional" | "required") => void;
  onWhole?: (contract: string, whole: boolean) => void;
  /** A direct change to the drawn pipeline, as the whole next graph — the person's. */
  onEdit: (graph: DraftGraph) => void;
  onAddStep: (contractId: string) => void;
  onRename?: (name: string) => void;
  /** The Run sequence — keep, lint, run sheet — when the page has one. The fixtures do not. */
  run?: {
    onRun: () => void;
    busy: boolean;
    stage: string | null;
    error: string | null;
    kept: boolean;
    sheet: React.ReactNode;
  } | null;
}) {
  const [view, setView] = useState<"canvas" | "artifact">("canvas");
  const [browsing, setBrowsing] = useState(false);
  const [left, setLeft] = useState<"canvas" | "understood">("canvas");
  const [pane, setPane] = useState<"chat" | "canvas" | "understood">("chat");

  // **The server's frame, whole**: the visible graph, each step's recorded metadata, and the
  // channels that really enter. Nothing here re-derives or guesses any of it.
  const frame = session.canvas ?? null;
  const answered = (frame?.steps ?? []).map((step) => withTypedValues(step, graph));
  const steps: Record<string, AnsweredStep> = Object.fromEntries(answered.map((step) => [step.id, step]));
  const values = valuesOf(answered);
  const aiChosen = [...new Set(session.ai_unreviewed.map((c) => c.node))].sort();
  const reviews: Record<string, ReviewState> = {};

  // **A step the agent just built is brought on screen**, as the person's selection is.
  const [newest, setNewest] = useState<string | null>(null);
  const ids = (frame?.graph.nodes ?? []).map((n) => n.id).join(",");
  const [seen, setSeen] = useState(ids);
  if (ids !== seen) {
    const before = new Set(seen.split(","));
    setNewest(ids.split(",").find((id) => id && !before.has(id)) ?? null);
    setSeen(ids);
  }
  const focus = useFocus(newest, selected);
  useEffect(() => {
    if (selected) setPane("chat");
  }, [selected]);

  const notices = (
    <>
      {notice && (
        <div role="alert" data-testid="living-notice"
             className="mx-4 mt-4 px-3 py-2 border rounded-button flex items-baseline gap-3"
             style={{ borderColor: "var(--needs-you)", background: "var(--needs-you-soft)" }}>
          <span className="text-[12.5px] text-ink flex-1">{notice.text}</span>
          {notice.code && <span className="font-data text-[10px] text-ink-2">{notice.code}</span>}
          <button type="button" onClick={onDismiss}
                  className="bg-transparent border-0 text-ink-2 cursor-pointer text-[11px]">
            Dismiss
          </button>
        </div>
      )}
      {session.retired && <p className="mx-4 mt-4 text-[12px] text-ink-2">
        This archived conversation is read-only. <a href="/build" className="text-now-ink underline">Start a new analysis</a>.
      </p>}
      {!session.model_configured && (
        <div data-testid="no-model" className="mx-4 mt-4">
          <p className="m-0 text-[13px] text-ink">No model is configured here</p>
          <p className="m-0 mt-1 text-[12.5px] text-ink-2">
            The builder agent needs one. Everything else works: draw the pipeline yourself on the
            canvas, and the engine settles every step it can prove.
          </p>
        </div>
      )}
    </>
  );

  const runnable = run !== null && !session.retired;
  const factsDisabled = correcting || session.retired || session.working;

  return (
    <div className="grid grid-rows-[auto_1fr] h-full overflow-hidden" data-testid="living">
      <LivingHeader
        session={session}
        view={view}
        onView={setView}
        onRun={run ? run.onRun : () => setView("artifact")}
        running={run ? run.busy : false}
        stage={run?.stage ?? null}
        runError={run?.error ?? null}
        runnable={runnable}
        openValues={values.open}
        onRename={session.retired ? undefined : onRename}
      />
      {/* **On a phone, one pane at a time**: the conversation first. Hidden above 640px. */}
      <div role="tablist" aria-label="on a phone" className="phone-tabs gap-1 px-[16px] pt-[8px]">
        {(["chat", "canvas", "understood"] as const).map((name) => (
          <button key={name} type="button" role="tab" aria-selected={pane === name}
                  onClick={() => { setPane(name); if (name !== "chat") setLeft(name); }}
                  className="flex-1 px-2 py-[5px] rounded-button border text-[12px] cursor-pointer"
                  style={pane === name ? { background: "var(--now-soft)", borderColor: "var(--now-line)", color: "var(--now-ink)" }
                    : { background: "transparent", borderColor: "var(--line)", color: "var(--ink-2)" }}>
            {PANE_WORDS[name]}
          </button>
        ))}
      </div>
      {run?.sheet}
      {view === "artifact" && !run?.sheet && (
        <div className="min-h-0" style={{ borderTop: "1px solid var(--line)" }}>
          <PipelineFile steps={answered} preview={preview} draftId={session.draft_id} kept={run?.kept ?? false}
                        onChange={(node) => { setView("canvas"); setPane("chat"); onSelect(node); }}
                        onAsk={(text) => { setView("canvas"); setPane("chat"); onCompose(text); }} />
        </div>
      )}
      {/* **Kept mounted while the pipeline file or the run sheet shows**, so the canvas's view is as
          it was. Hidden by an inline style: `.living` sets `display: grid` and would win over a class. */}
      <div className="living min-h-0" data-pane={pane}
           inert={view === "artifact" || run?.sheet ? true : undefined}
           style={{ display: view === "artifact" || run?.sheet ? "none" : undefined }}>
        <section aria-label="pipeline canvas"
                 className="living-canvas relative flex flex-col min-h-0 ml-[28px] mr-[8px] mt-[4px] mb-[24px] rounded-panel border border-line overflow-hidden">
          <div role="radiogroup" aria-label="beside the conversation"
               className="beside-switch flex gap-1 mx-4 mt-3 self-start p-1 rounded-button" style={{ background: "var(--paper)" }}>
            {(["canvas", "understood"] as const).map((name) => (
              <button key={name} type="button" role="radio" aria-checked={left === name} onClick={() => setLeft(name)}
                      className={`px-3 py-[4px] rounded-control border text-[12.5px] cursor-pointer
                                  ${left === name ? "text-ink font-semibold" : "text-ink-2 bg-transparent border-transparent"}`}
                      style={left === name ? { background: "var(--surface)", borderColor: "var(--line)" } : undefined}>
                {name === "canvas" ? "Canvas" : "What was understood"}
              </button>
            ))}
          </div>
          {left === "understood" && (
            <Understood session={session} declarations={declarations} onCorrect={onCorrect} onRelease={onRelease}
                        onUnits={onUnits} onTable={onTable} disabled={factsDisabled} />
          )}
          <div className="relative flex-1 min-h-0 flex flex-col"
               inert={left === "understood" ? true : undefined} data-testid="build-canvas"
               style={left === "understood" ? { display: "none" } : undefined}>
            <LivingCanvas
              shown={`${pane}:${view}:${left}`}
              empty={session.working
                ? "The agent is working — steps appear here as it builds them"
                : "The pipeline appears here as the agent builds it, or add a step yourself"}
              graph={frame?.graph ?? { nodes: [], edges: [] }}
              stale={frame !== null && !frame.current}
              working={session.working}
              reviews={reviews}
              aiChosen={aiChosen}
              channels={frame?.channels ?? []}
              positions={{ ...session.placement, ...(frame?.placement as Positions | undefined) }}
              steps={steps}
              authors={{}}
              selected={selected}
              onSelect={onSelect}
              focus={focus}
              onEdit={session.retired ? undefined : onEdit}
              footer={
                <button type="button" data-testid="add-step" onClick={() => setBrowsing(true)}
                        className="px-[14px] py-[6px] rounded-button border border-line-2 bg-surface text-[13px]
                                   font-semibold text-now-ink cursor-pointer hover:bg-[var(--hover)]
                                   focus-visible:shadow-[var(--ring)]">
                  + Add step
                </button>
              }
            />
          </div>
          {browsing && (
            <Browse onAdd={(contract) => { onAddStep(contract); setBrowsing(false); }}
                    onClose={() => setBrowsing(false)} />
          )}
        </section>

        <ChatPanel
          session={session} sending={sending} composer={composer} onCompose={onCompose} onSay={onSay}
          onAnswer={onAnswer} onRetry={onRetry} onUpload={onUpload}
          selected={selected} onSelect={onSelect} graph={graph} steps={steps} onEdit={onEdit}
          onSetParam={onSetParam} onSwitchInput={onSwitchInput} onWhole={onWhole} onReviewed={onReviewed}
          notices={notices}
        />
      </div>
    </div>
  );
}

const PANE_WORDS = { chat: "Chat", canvas: "Canvas", understood: "Understood" } as const;
