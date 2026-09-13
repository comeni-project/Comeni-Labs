import { useState } from "react";

import type {
  AuthoringBlock,
  AuthoringProposal,
  AuthoringSession,
  DraftGraph,
  GoalIn,
  Step,
} from "../../api/types";
import type { components } from "../../api/schema";
import { Browse } from "../Browse";
import type { AuthoringState, MotionEvent } from "./authoringReducer";
import { Composer } from "./Composer";
import { DecisionLog } from "./DecisionLog";
import { Drawer } from "./Drawer";
import { authorOf, type Author } from "./format";
import { LivingCanvas } from "./LivingCanvas";
import { LivingHeader } from "./LivingHeader";

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
  steps,
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
  onAddStep,
  onDismiss,
  vocabulary = null,
  onSetParam,
  onApplyChange,
  channels = [],
  onPlayed = () => undefined,
  reveal = {},
}: {
  session: AuthoringSession;
  graph: DraftGraph;
  steps: Record<string, Step>;
  state: AuthoringState;
  preview: { revision: number; text: string } | null;
  busy: (proposalId: string) => boolean;
  onAccept: (proposal: AuthoringProposal, option?: string, goal?: GoalIn) => void;
  onReject: (proposal: AuthoringProposal) => void;
  onPreviewOption: (option: string | null) => void;
  onSelect: (node: string | null) => void;
  onCompose: (text: string) => void;
  onSay: (text: string) => void;
  onRetry: () => void;
  onAddStep: (contractId: string) => void;
  onDismiss: () => void;
  vocabulary?: Record<string, string[]> | null;
  onSetParam: (node: string, setting: string, value: string) => void;
  onApplyChange: (block: Extract<AuthoringBlock, { kind: "change_set" }>) => void;
  /** Where data enters and how often — the drawn view's channels, from the server. */
  channels?: components["schemas"]["ChannelView"][];
  onPlayed?: (event: MotionEvent) => void;
  reveal?: Record<string, number>;
}) {
  const [view, setView] = useState<"canvas" | "artifact">("canvas");
  const [browsing, setBrowsing] = useState(false);

  const pending = session.pending_proposal;
  const ghost = pending?.block.kind === "step_proposal" ? pending.block.node : null;

  const authors: Record<string, Author> = {};
  for (const decision of session.history) {
    if (decision.block.kind === "step_proposal" && decision.state === "accepted") {
      authors[decision.block.node] = authorOf(decision);
    }
  }

  const pendingTurn = session.turns.some((turn) => turn.state === "pending");

  return (
    <div className="grid grid-rows-[auto_1fr] h-full overflow-hidden" data-testid="living">
      <LivingHeader
        session={session}
        view={view}
        onView={setView}
        onRun={() => setView("artifact")}
        running={false}
      />
      <div className="living min-h-0" style={{ borderTop: "1px solid var(--line)" }}>
        <section aria-label="pipeline canvas" className="living-canvas relative flex flex-col min-h-0">
          <LivingCanvas
            graph={graph}
            ghost={ghost}
            ghostProposal={pending?.kind === "step" ? pending.id : null}
            ghostEdges={pending?.edges ?? []}
            channels={channels}
            events={state.events}
            onPlayed={onPlayed}
            reveal={reveal}
            positions={session.placement}
            steps={steps}
            authors={authors}
            selected={state.selected}
            onSelect={onSelect}
            instead={
              state.previewed && pending?.block.kind === "step_proposal"
                ? (pending.block.alternatives.find((o) => o.id === state.previewed)?.label ?? null)
                : null
            }
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
          {view === "artifact" && (
            <Drawer title="pipeline.yml — as it would read now" onClose={() => setView("canvas")}>
              {preview?.text ? (
                <pre data-testid="artifact-text"
                     className="m-0 font-data text-[11px] leading-[1.6] text-ink-2 whitespace-pre">
                  {preview.text}
                </pre>
              ) : (
                <p className="m-0 text-[12.5px] text-ink-3">
                  Nothing has been added yet, so there is no pipeline to show.
                </p>
              )}
            </Drawer>
          )}
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
          {!session.model_configured && (
            <div data-testid="no-model" className="mx-5 mt-4">
              <p className="m-0 text-[13px] text-ink">No model is configured here</p>
              <p className="m-0 mt-1 text-[12.5px] text-ink-2">
                Build and Spawn need one. Everything else works: draw the pipeline yourself, and the
                engine settles every step it can prove.
              </p>
            </div>
          )}
          <div className="flex-1 min-h-0 overflow-auto px-5 pt-6 pb-4">
            <DecisionLog
              session={session}
              selected={state.selected}
              busy={busy}
              onAccept={onAccept}
              onReject={onReject}
              onPreview={onPreviewOption}
              onSelect={onSelect}
              onRetry={onRetry}
              onSay={onSay}
              saying={state.saying}
              vocabulary={vocabulary}
              onSetParam={onSetParam}
              onApplyChange={onApplyChange}
            />
          </div>
          <div className="px-5 py-4" style={{ borderTop: "1px solid var(--line)" }}>
            <Composer
              value={state.composer}
              onChange={onCompose}
              onSend={onSay}
              disabled={pendingTurn}
              placeholder={pendingTurn ? "Waiting for the answer…" : undefined}
            />
          </div>
        </section>
      </div>
    </div>
  );
}
