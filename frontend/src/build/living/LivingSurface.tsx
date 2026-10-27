import { useEffect, useRef, useState } from "react";

import type {
  AuthoringBlock,
  AuthoringProposal,
  AuthoringSession,
  AuthoringVocabulary,
  DraftGraph,
  GoalIn,
  SampleInspected,
} from "../../api/types";
import type { components } from "../../api/schema";
import { Browse } from "../Browse";
import { withoutNode } from "../graphOps";
import { PipelineFile } from "./PipelineFile";
import type { AuthoringState, MotionEvent } from "./authoringReducer";
import type { CorrectFact } from "./CurrentFacts";
import type { FactValue } from "./FactEditor";
import { ChatPanel } from "./ChatPanel";
import { Understood } from "./Understood";
import { DescribePage } from "./DescribePage";
import { authorOf, type Author } from "./format";
import { LivingCanvas } from "./LivingCanvas";
import { LivingHeader } from "./LivingHeader";
import type { ReviewState } from "./LivingNode";
import type { Positions } from "../geometry";
import { stageOf } from "./stage";
import { valuesOf } from "./values";
import { type AnsweredStep, withTypedValues } from "../useBuilder";
import { useFocus } from "./useFocus";
import { useAlternativePreview, type PreviewSelection, type ReadPreview } from "./useAlternativePreview";

/** The living builder's composition: **wires state and callbacks, draws nothing itself.**
 *
 * Two stages (#377), chosen by `stageOf`. While there is nothing to draw, the describe page: the
 * sentence, the card waiting, what was understood, the conversation. After that, the canvas beside
 * a panel whose *Step* tab holds the engine's cards and whose *Assistant* tab is the chat. The
 * panel's widths are the artboards' (`.living` in `main.css`): 420px, 360px under 1180px, and
 * stacked under 1000px with the panel first *visually* while the canvas stays first in the
 * document for a screen reader. The panel stacks; it never overlays the graph.
 *
 * YAML and module browsing are contextual — a drawer over the canvas, and the existing `Browse`
 * overlay — not panels that are always there.
 */
export function LivingSurface({
  session,
  graph,
  state,
  preview,
  busy,
  onAccept,
  onReject,
  onPreviewOption,
  onSelect,
  onCompose,
  onSay,
  onRetry,
  onApplySuggestion = () => {},
  onDismissSuggestion = () => {},
  suggesting = false,
  onUpload,
  onAddStep,
  onDismiss,
  vocabulary = null,
  declarations, onCorrect, onRelease, onDisagreement, correcting = false,
  onSetParam,
  onApplyChange,
  onEdit,
  onRename,
  onPlayed = () => undefined,
  reveal = {},
  run = null,
  readPreview,
}: {
  session: AuthoringSession;
  /** The draft as saved — what an edit changes. The canvas draws the session's frame instead. */
  graph: DraftGraph;
  state: AuthoringState;
  preview: components["schemas"]["AuthoringPreview"] | null;
  busy: (proposalId: string) => boolean;
  onAccept: (
    proposal: AuthoringProposal, option?: string, goal?: GoalIn, value?: string | number | boolean,
  ) => void;
  onReject: (proposal: AuthoringProposal) => void;
  onPreviewOption: (option: string | null) => void;
  onSelect: (node: string | null) => void;
  onCompose: (text: string) => void;
  onSay: (text: string) => void;
  onRetry: () => void;
  /** Apply or set aside one of the model's suggestions (Part I.0). */
  onApplySuggestion?: (id: string) => void;
  onDismissSuggestion?: (id: string) => void;
  suggesting?: boolean;
  /** Answer a gap with a sample (issue 134). Absent where nothing can be uploaded. */
  onUpload?: (proposal: AuthoringProposal, files: File[]) => Promise<SampleInspected>;
  onAddStep: (contractId: string) => void;
  onDismiss: () => void;
  vocabulary?: Record<string, string[]> | null;
  declarations?: AuthoringVocabulary["measurements"];
  onCorrect?: CorrectFact;
  onRelease?: (type: string, states: string[]) => Promise<unknown>;
  onDisagreement?: (proposal: AuthoringProposal, option: string, value?: FactValue) => Promise<unknown>;
  correcting?: boolean;
  onSetParam: (node: string, setting: string, value: string, why?: string) => void;
  onApplyChange: (block: Extract<AuthoringBlock, { kind: "change_set" }>) => void;
  /** A direct change to a step already drawn — swap, settings, remove — as the whole next graph,
   *  for the session's edit verb to save, stamp as the person's and write a receipt for. */
  onEdit: (graph: DraftGraph) => void;
  /** Rename the pipeline. Absent on the fakes, whose name is fixed. */
  onRename?: (name: string) => void;
  onPlayed?: (event: MotionEvent) => void;
  reveal?: Record<string, number>;
  /** The Run sequence — keep, lint, run sheet — when the page has one. The fixtures do not. */
  run?: {
    onRun: () => void;
    busy: boolean;
    stage: string | null;
    error: string | null;
    kept: boolean;
    sheet: React.ReactNode;
  } | null;
  /** How a saved complete preview is read; the endpoint unless a fixture supplies its own. */
  readPreview?: ReadPreview;
}) {
  const [factsRequest, setFactsRequest] = useState(0);
  const [view, setView] = useState<"canvas" | "artifact">("canvas");
  const [browsing, setBrowsing] = useState(false);

  const pending = session.pending_proposal;
  // **The server's frame, whole**: the visible graph with the step on offer, each step's recorded
  // metadata, and the channels that really enter. Nothing here re-derives or guesses any of it —
  // an offered step is drawn only when the frame says it holds that offer.
  const frame = session.canvas ?? null;
  const ghost = pending?.block.kind === "step_proposal" && frame?.proposal_id === pending.id
    ? pending.block.node : null;
  // **Each step with what the person typed laid over it** — what the pipeline file, the header,
  // the canvas's counts and an opened step's questions all count as answered.
  const answered = (frame?.steps ?? []).map((step) => withTypedValues(step, graph));
  const steps: Record<string, AnsweredStep> = Object.fromEntries(answered.map((step) => [step.id, step]));
  const values = valuesOf(answered);
  const reviews: Record<string, ReviewState> = Object.fromEntries(
    Object.entries(session.review_applicability ?? {}).map(([node, status]) =>
      [node, status === "retained" ? "reviewed" : "again"] as const));
  if (ghost && session.progress?.active?.again) reviews[ghost] = "again";

  const authors: Record<string, Author> = {};
  for (const decision of session.history) {
    if (decision.block.kind === "step_proposal" && decision.state === "accepted") {
      authors[decision.block.node] = authorOf(decision);
    }
  }

  const pendingTurn = session.turns.some((turn) => turn.state === "pending");
  const [left, setLeft] = useState<"canvas" | "understood">("canvas");
  const [pane, setPane] = useState<"chat" | "canvas" | "understood">("chat");
  const [questionRequest, setQuestionRequest] = useState(0);
  const openQuestion = () => { setPane("chat"); setQuestionRequest((n) => n + 1); };
  const factsDisabled = correcting || session.retired || pendingTurn || session.phase === "resolving";
  const focus = useFocus(ghost, state.selected);

  // **A complete preview belongs to one offer in one context.** A selection made against another
  // proposal or context is no selection, so a change of either clears it without an effect.
  const offer = pending?.kind === "step" ? pending.id : null;
  const context = JSON.stringify(frame?.context ?? null);
  const [picked, setPicked] =
    useState<{ option: string; pinned: boolean; offer: string | null; context: string } | null>(null);
  const live = picked && picked.offer === offer && picked.context === context ? picked : null;
  const selection: PreviewSelection = live ? { option: live.option, pinned: live.pinned } : null;
  const trigger = useRef<HTMLElement | null>(null);
  const alternative = useAlternativePreview(session, selection, readPreview);
  const showing = alternative.preview;

  const onPreview = (option: string | null, mode: "temporary" | "pinned") => {
    onPreviewOption(option);
    if (mode === "pinned") {
      if (option === null || (live?.pinned && live.option === option)) {
        setPicked(null);
        return;
      }
      trigger.current = document.activeElement as HTMLElement | null;
      setPicked({ option, pinned: true, offer, context });
      return;
    }
    // A moment's look — hover or focus — never replaces or clears a pinned preview.
    if (live?.pinned) return;
    setPicked(option === null ? null : { option, pinned: false, offer, context });
  };
  /** Focus goes back to **Preview** only when a pinned preview closes, and only once: a moment's
   *  look never owned the focus, and an old trigger must not take it from where the person is. */
  const closePreview = () => {
    const back = live?.pinned ? trigger.current : null;
    trigger.current = null;
    setPicked(null);
    back?.focus();
  };
  const previewOpen = live !== null;
  const close = useRef(closePreview);
  useEffect(() => {
    close.current = closePreview;
  });
  useEffect(() => {
    if (!previewOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") close.current();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [previewOpen]);

  const notices = (
    <>
      {state.notice && (
        <div role="alert" data-testid="living-notice"
             className="mx-4 mt-4 px-3 py-2 border rounded-button flex items-baseline gap-3"
             style={{ borderColor: "var(--needs-you)", background: "var(--needs-you-soft)" }}>
          <span className="text-[12.5px] text-ink flex-1">{state.notice.text}</span>
          {state.notice.code && <span className="font-data text-[10px] text-ink-2">{state.notice.code}</span>}
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
            The builder needs one to read what you describe. Everything else works: draw the
            pipeline yourself, and the engine settles every step it can prove.
          </p>
        </div>
      )}
      {session.projection_current === false && <p role="status" className="mx-4 mt-3 mb-0 text-[12px] text-ink-2">
        Pipeline outdated. Your answers are saved; follow the Step panel to provide missing inputs or release a tool choice.
      </p>}
    </>
  );
  const waiting = {
    busy, onAccept, onReject, onPreview, pinnedPreview: live?.pinned ? live.option : null,
    onUpload, vocabulary, declarations, onDisagreement, correcting,
    onCorrectAnswers: onCorrect ? () => {
      setLeft("understood");
      setPane("understood");
      setFactsRequest((n) => n + 1);
    } : undefined,
  };
  const talk = {
    composer: state.composer,
    composerHint: composerHint(session, pendingTurn),
    // **Never locked by work in flight** (issue 392): what is typed meanwhile waits in line.
    composerDisabled: session.retired || session.phase === "stopped",
    onCompose, onSay, saying: state.sending.at(-1) ?? null, sending: state.sending, onRetry,
    declarations, onCorrect, onRelease, correcting, factsRequest, notices,
  };

  if (stageOf(session) === "describe") {
    // **No header strip while describing** (the *Describe* board): there is no pipeline yet to
    // name, view or run, so the page is the sentence and what was understood.
    return (
      <div className="h-full min-h-0 grid overflow-hidden" data-testid="living">
        <DescribePage session={session} waiting={{ ...waiting, onSelect }} {...talk} />
      </div>
    );
  }

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
        runnable={run !== null && session.projection_current !== false && !session.retired && !showing}
        openValues={values.open}
        onRename={session.retired ? undefined : onRename}
      />
      {/* **On a phone, one pane at a time** (one builder plan 3): the conversation first. Hidden
          above 640px by `.phone-tabs`. */}
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
      {/* **The run sheet takes the canvas's place** (the *Run sheet* board), under the header. */}
      {run?.sheet}
      {view === "artifact" && !run?.sheet && (
        <div className="min-h-0" style={{ borderTop: "1px solid var(--line)" }}>
          <PipelineFile steps={answered} preview={preview} draftId={session.draft_id} kept={run?.kept ?? false} />
        </div>
      )}
      {/* **Kept mounted while the pipeline file or the run sheet shows**, so the canvas's view is as
          it was. Hidden by an inline style: `.living` sets `display: grid` and would win over a class. */}
      <div className="living min-h-0" data-pane={pane}
           inert={view === "artifact" || run?.sheet ? true : undefined}
           style={{ display: view === "artifact" || run?.sheet ? "none" : undefined }}>
        <section aria-label="pipeline canvas"
                 className="living-canvas relative flex flex-col min-h-0 ml-[28px] mr-[8px] mt-[4px] mb-[24px] rounded-panel border border-line overflow-hidden">
          {/* **The canvas, or what was understood** (one builder plan 3): the record the Step tab
              held, one switch away. */}
          <div role="radiogroup" aria-label="beside the conversation"
               className="flex gap-1 mx-4 mt-3 self-start p-1 rounded-button" style={{ background: "var(--paper)" }}>
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
                        openRequest={factsRequest} disabled={factsDisabled}
                        onOpenQuestion={openQuestion} />
          )}
          {(alternative.loading || alternative.error) && (
            <div role="status" data-testid={alternative.error ? "preview-error" : "preview-loading"}
                 className="mx-5 mt-3 flex items-baseline gap-3 text-[12px] text-ink-2">
              {alternative.error
                ? <>This preview could not be read. {alternative.error.message}
                    <button type="button" data-testid="preview-retry" onClick={() => void alternative.retry()}
                            className="bg-transparent border-0 p-0 text-now-ink underline cursor-pointer">
                      Retry
                    </button></>
                : "Loading preview…"}
            </div>
          )}
          {showing && (
            <div data-testid="alternative-preview" className="relative flex-1 min-h-0 flex flex-col">
              <div role="status" className="mx-5 mt-3 px-3 py-2 border flex items-baseline gap-3"
                   style={{ borderColor: "var(--now-line)", background: "var(--paper-2)" }}>
                <span className="text-[12.5px] text-ink flex-1">
                  <strong className="font-semibold">Preview — not applied.</strong>{" "}
                  The whole pipeline {showing.contract} gives; nothing changes until you choose it.
                </span>
                <button type="button" data-testid="preview-close" onClick={closePreview}
                        className="bg-transparent border-0 text-now-ink cursor-pointer text-[11px]">
                  Close preview
                </button>
              </div>
              <LivingCanvas
                readOnly
                graph={showing.frame.graph}
                ghost={null}
                positions={showing.frame.placement as Positions}
                steps={Object.fromEntries(showing.frame.steps.map((step) => [step.id, step]))}
                channels={showing.frame.channels}
                reviews={Object.fromEntries(showing.frame.graph.nodes.map((n) => [n.id, "proposed" as const]))}
                authors={{}}
                selected={null}
                onSelect={() => undefined}
              />
            </div>
          )}
          {/* **Kept mounted while a preview shows**, so its viewport, moved steps and selection are
              exactly as they were when the preview closes. */}
          <div className={showing ? "hidden" : "relative flex-1 min-h-0 flex flex-col"}
               inert={showing || left === "understood" ? true : undefined} data-testid="build-canvas"
               style={left === "understood" ? { display: "none" } : undefined}>
          <LivingCanvas
            empty={session.phase === "stopped"
              ? "This analysis stopped before anything was built — see why on the right"
              : undefined}
            graph={frame?.graph ?? { nodes: [], edges: [] }}
            stale={frame !== null && !frame.current}
            working={state.inFlight !== null}
            reviews={reviews}
            ghost={ghost}
            ghostProposal={pending?.kind === "step" ? pending.id : null}
            ghostEdges={ghost ? (pending?.edges ?? []) : []}
            channels={frame?.channels ?? []}
            events={state.events}
            onPlayed={onPlayed}
            reveal={reveal}
            positions={{ ...session.placement, ...(frame?.placement as Positions | undefined) }}
            steps={steps}
            authors={authors}
            selected={state.selected}
            onSelect={onSelect}
            focus={focus}
            // **The edit is of the pipeline, never of the step on offer**: the frame draws it, the
            // saved graph does not hold it, and sending it would read as "you added it".
            onEdit={session.retired ? undefined : (next) => onEdit(
              ghost && !graph.nodes.some((n) => n.id === ghost) ? withoutNode(next, ghost) : next)}
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
          session={session}
          waiting={waiting}
          selected={state.selected}
          onSelect={onSelect}
          graph={graph}
          steps={steps}
          onEdit={onEdit}
          onSetParam={onSetParam}
          onApplyChange={onApplyChange}
          suggestions={{ busy: suggesting, onApply: onApplySuggestion, onDismiss: onDismissSuggestion }}
          questionRequest={questionRequest}
          {...talk}
        />
      </div>
    </div>
  );
}

const PANE_WORDS = { chat: "Chat", canvas: "Canvas", understood: "Understood" } as const;

/** What the composer invites, by where the session is. */
function composerHint(session: AuthoringSession, pendingTurn: boolean): string | undefined {
  if (session.phase === "stopped") return "Correct your current answers to continue";
  if (pendingTurn) return "Ask anything, or answer in your own words";
  if (session.phase === "understanding") return "Say what you have and what you want";
  if (session.phase === "goal_review") return "Say what is wrong with the goal, or confirm it above";
  if (session.phase === "gathering") return "Answer the question above, or say it in your own words";
  return undefined;
}
