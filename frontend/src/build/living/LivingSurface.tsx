import { useEffect, useRef, useState } from "react";

import type {
  AuthoringBlock,
  AuthoringProposal,
  AuthoringSession,
  AuthoringVocabulary,
  DraftGraph,
  GoalIn,
  SampleInspected,
  Step,
} from "../../api/types";
import type { components } from "../../api/schema";
import { ArtifactView } from "../ArtifactView";
import { Browse } from "../Browse";
import { ArtifactPreview } from "./ArtifactPreview";
import type { AuthoringState, MotionEvent } from "./authoringReducer";
import { CurrentFacts, type CorrectFact } from "./CurrentFacts";
import type { FactValue } from "./FactEditor";
import { Composer } from "./Composer";
import { DecisionLog } from "./DecisionLog";
import { Drawer } from "./Drawer";
import { authorOf, type Author } from "./format";
import { LivingCanvas } from "./LivingCanvas";
import { LivingHeader } from "./LivingHeader";
import type { ReviewState } from "./LivingNode";
import type { Positions } from "../geometry";
import { useAlternativePreview, type PreviewSelection, type ReadPreview } from "./useAlternativePreview";

/** The living builder's composition: **wires state and callbacks, draws nothing itself.**
 *
 * Two surfaces — the canvas and the conversation — in a grid whose breakpoints are the artboards'
 * (`.living` in `main.css`): a 420px rail, 360px under 1180px, and stacked under 1000px with the
 * conversation first *visually* while the canvas stays first in the document for a screen reader.
 * The rail stacks; it never overlays, because an overlay hides the graph the conversation is about.
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
  onUpload,
  onAddStep,
  onDismiss,
  vocabulary = null,
  declarations, onCorrect, onRelease, onDisagreement, correcting = false,
  onSetParam,
  onApplyChange,
  onEdit,
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
    proposal: AuthoringProposal, option?: string, goal?: GoalIn, value?: string | number,
  ) => void;
  onReject: (proposal: AuthoringProposal) => void;
  onPreviewOption: (option: string | null) => void;
  onSelect: (node: string | null) => void;
  onCompose: (text: string) => void;
  onSay: (text: string) => void;
  onRetry: () => void;
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
  onSetParam: (node: string, setting: string, value: string) => void;
  onApplyChange: (block: Extract<AuthoringBlock, { kind: "change_set" }>) => void;
  /** A direct change to a step already drawn — swap, settings, remove — as the whole next graph,
   *  for the session's edit verb to save, stamp as the person's and write a receipt for. */
  onEdit: (graph: DraftGraph) => void;
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
  const [artifactTab, setArtifactTab] = useState<"preview" | "kept">("preview");
  const [browsing, setBrowsing] = useState(false);

  const pending = session.pending_proposal;
  const ghost = pending?.block.kind === "step_proposal" ? pending.block.node : null;
  // **The server's frame, whole**: the visible graph with the step on offer, each step's recorded
  // metadata, and the channels that really enter. Nothing here re-derives or guesses any of it.
  const frame = session.canvas ?? null;
  const steps: Record<string, Step> =
    Object.fromEntries((frame?.steps ?? []).map((step) => [step.id, step]));
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
  const closePreview = () => {
    setPicked(null);
    trigger.current?.focus();
  };
  const previewOpen = live !== null;
  useEffect(() => {
    if (!previewOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      setPicked(null);
      trigger.current?.focus();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [previewOpen]);

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
      />
      <div className="living min-h-0" style={{ borderTop: "1px solid var(--line)" }}>
        <section aria-label="pipeline canvas" className="living-canvas relative flex flex-col min-h-0">
          {(alternative.loading || alternative.error) && (
            <div role="status" data-testid={alternative.error ? "preview-error" : "preview-loading"}
                 className="mx-5 mt-3 flex items-baseline gap-3 text-[12px] text-ink-2">
              {alternative.error
                ? <>This preview could not be read. {alternative.error.message}
                    <button type="button" data-testid="preview-retry" onClick={() => void alternative.retry()}
                            className="bg-transparent border-0 p-0 text-link underline cursor-pointer">
                      Retry
                    </button></>
                : "Reading the saved preview…"}
            </div>
          )}
          {showing && (
            <div data-testid="alternative-preview" className="relative flex-1 min-h-0 flex flex-col">
              <div role="status" className="mx-5 mt-3 px-3 py-2 border flex items-baseline gap-3"
                   style={{ borderColor: "var(--link-line)", background: "var(--paper-2)" }}>
                <span className="text-[12.5px] text-ink flex-1">
                  Previewing {showing.contract}: the whole pipeline this choice gives. Nothing
                  changes until you choose it.
                </span>
                <button type="button" data-testid="preview-close" onClick={closePreview}
                        className="bg-transparent border-0 text-link cursor-pointer text-[11px]">
                  Close
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
               inert={showing ? true : undefined} data-testid="build-canvas">
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
            ghostEdges={pending?.edges ?? []}
            channels={frame?.channels ?? []}
            events={state.events}
            onPlayed={onPlayed}
            reveal={reveal}
            positions={{ ...session.placement, ...(frame?.placement as Positions | undefined) }}
            steps={steps}
            authors={authors}
            selected={state.selected}
            onSelect={onSelect}
            footer={
              <div className="absolute left-5 bottom-5 flex gap-2">
                <button type="button" data-testid="add-step" onClick={() => setBrowsing(true)}
                        className="font-data text-[11px] px-3 py-[6px] bg-transparent text-link border
                                   cursor-pointer focus-visible:shadow-[var(--ring)]"
                        style={{ borderColor: "var(--link-line)" }}>
                  + Add step
                </button>
              </div>
            }
          />
          </div>
          {view === "artifact" && (
            <Drawer title="pipeline.yml" onClose={() => setView("canvas")}>
              <div className="flex gap-2 mb-4" role="tablist" aria-label="which pipeline.yml">
                {(["preview", "kept"] as const).map((tab) => (
                  <button key={tab} type="button" role="tab" aria-selected={artifactTab === tab}
                          data-testid={`artifact-tab-${tab}`}
                          disabled={tab === "kept" && !run?.kept}
                          onClick={() => setArtifactTab(tab)}
                          className={`font-data text-[10px] uppercase tracking-[.1em] px-3 py-[5px] border cursor-pointer
                                      disabled:opacity-40 disabled:cursor-not-allowed
                                      ${artifactTab === tab ? "text-link" : "text-ink-3 bg-transparent"}`}
                          style={{ borderColor: artifactTab === tab ? "var(--link-line)" : "var(--line)" }}>
                    {tab === "preview" ? "as it would read" : "as kept"}
                  </button>
                ))}
              </div>
              {artifactTab === "kept" && run?.kept
                ? <ArtifactView draftId={session.draft_id} />
                : <ArtifactPreview preview={preview} />}
            </Drawer>
          )}
          {run?.sheet}
          {browsing && (
            <Browse onAdd={(contract) => { onAddStep(contract); setBrowsing(false); }}
                    onClose={() => setBrowsing(false)} />
          )}
        </section>

        <section aria-label="conversation" className="living-rail flex flex-col min-h-0"
                 style={{ borderLeft: "1px solid var(--line)" }}>
          {state.notice && (
            <div role="alert" data-testid="living-notice"
                 className="mx-5 mt-4 px-3 py-2 border flex items-baseline gap-3"
                 style={{ borderColor: "var(--undecided)", background: "var(--undecided-soft)" }}>
              <span className="text-[12.5px] text-ink flex-1">{state.notice.text}</span>
              {state.notice.code && <span className="font-data text-[10px] text-ink-2">{state.notice.code}</span>}
              <button type="button" onClick={onDismiss}
                      className="bg-transparent border-0 text-ink-2 cursor-pointer text-[11px]">
                Dismiss
              </button>
            </div>
          )}
          {session.retired && <p className="mx-5 mt-4 text-[12px] text-ink-2">
            This archived conversation is read-only. <a href="/build" className="text-link underline">Start a new analysis</a>.
          </p>}
          {!session.model_configured && (
            <div data-testid="no-model" className="mx-5 mt-4">
              <p className="m-0 text-[13px] text-ink">No model is configured here</p>
              <p className="m-0 mt-1 text-[12.5px] text-ink-2">
                The builder needs one to read what you describe. Everything else works: draw the
                pipeline yourself, and the engine settles every step it can prove.
              </p>
            </div>
          )}
          <div className="flex-1 min-h-0 overflow-auto px-5 pt-6 pb-4">
            {session.projection_current === false && <p role="status" className="mb-3 text-[12px] text-ink-2">
              Pipeline outdated. Your answers are saved; follow the chat to provide missing inputs or release a tool choice.
            </p>}
            {session.forked_from_session && <a className="text-[12px] text-link underline"
              href={`/build/living?session=${encodeURIComponent(session.forked_from_session)}`}>Open preserved manual work</a>}
            <CurrentFacts session={session} declarations={declarations} onCorrect={onCorrect} onRelease={onRelease} openRequest={factsRequest}
              disabled={correcting || session.retired || pendingTurn || session.phase === "resolving" ||
                (pending?.block.kind === "question" && pending.block.reading?.state === "pending")} />
            <DecisionLog
              session={session}
              selected={state.selected}
              busy={busy}
              onAccept={onAccept}
              onReject={onReject}
              onPreview={onPreview}
              pinnedPreview={live?.pinned ? live.option : null}
              onSelect={onSelect}
              onRetry={onRetry}
              onUpload={onUpload}
              onSay={onSay}
              saying={state.saying}
              vocabulary={vocabulary}
              declarations={declarations}
              onDisagreement={onDisagreement}
              correcting={correcting}
              onCorrectAnswers={onCorrect ? () => setFactsRequest(n => n + 1) : undefined}
              onSetParam={onSetParam}
              onApplyChange={onApplyChange}
              graph={graph}
              steps={steps}
              onEdit={onEdit}
            />
          </div>
          <div className="px-5 py-4" style={{ borderTop: "1px solid var(--line)" }}>
            <Composer
              value={state.composer}
              onChange={onCompose}
              onSend={onSay}
              disabled={session.retired || pendingTurn || session.phase === "stopped"}
              placeholder={
                session.phase === "stopped"
                  ? "Correct your current answers to continue"
                  : pendingTurn
                  ? "Waiting for the answer…"
                  : session.phase === "understanding"
                    ? "Say what you have and what you want"
                    : session.phase === "goal_review"
                      ? "Say what is wrong with the goal, or confirm it above"
                      : session.phase === "gathering"
                        ? "Answer the question above, or say it in your own words"
                        : undefined
              }
            />
          </div>
        </section>
      </div>
    </div>
  );
}
