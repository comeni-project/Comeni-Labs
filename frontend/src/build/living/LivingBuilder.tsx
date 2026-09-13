import { useQuery } from "@tanstack/react-query";
import { useEffect, useReducer, useRef, useState } from "react";
import { useSearchParams } from "react-router";

import { post } from "../../api/client";
import type { AuthoringBlock, AuthoringSession, Built, DraftGraph, Step } from "../../api/types";
import { withNode, withoutNode, withParam } from "../graphOps";
import { authoringReducer, initialAuthoring, visibleGraph } from "./authoringReducer";
import { COLLECT_CHANNELS, COLLECT_SESSION, COLLECT_STEPS, FAKE_CHANNELS, FAKE_SESSION, FAKE_STEPS, FAKE_VOCABULARY } from "./fake";
import { guidedDecide, guidedStart } from "./guided";
import { LivingSurface } from "./LivingSurface";
import { lastSeen, markSeen, revealPlan } from "./replay";
import { useAuthoringSession } from "./useAuthoringSession";

type ChangeBlock = Extract<AuthoringBlock, { kind: "change_set" }>;

/** `/build/living` — a secondary route while `/build` stays exactly as it is.
 *
 * `?session=<id>` restores a live authoring session. `?fake=1` opens a static session carrying
 * every block state (Task 9's checkpoint, and what the artboard comparison renders); `?fake=guided`
 * opens one that answers itself, for completing a pipeline by keyboard or by touch (Task 10's).
 * Anything else says what to add rather than opening a default pipeline.
 */
export function LivingBuilder() {
  const [params] = useSearchParams();
  const session = params.get("session");
  const fake = params.get("fake");
  if (fake === "guided") return <GuidedLiving />;
  if (fake === "collect") return <CollectLiving />;
  if (fake) return <FakeLiving />;
  if (session) return <LiveLiving sessionId={session} />;
  return (
    <p className="gutter py-10 text-[13px] text-ink-2" data-testid="living-empty">
      Open a session with <span className="font-data">?session=&lt;id&gt;</span>.
    </p>
  );
}

/** A step id for a module added by hand: the tool's path, like `useGraph` names one. */
function idFor(graph: DraftGraph, contract: string): string {
  const base = contract.split("@")[0].split("/").slice(1).join("_").replace(/\W/g, "_") || "step";
  const taken = new Set(graph.nodes.map((n) => n.id));
  for (let n = 1; ; n += 1) if (!taken.has(`${base}_${n}`)) return `${base}_${n}`;
}

function LiveLiving({ sessionId }: { sessionId: string }) {
  const living = useAuthoringSession(sessionId);
  const drawn = useDrawn(living.graph, living.session);
  const reveal = useFirstArrival(sessionId, living.session);

  if (living.loading) {
    return <p className="gutter py-10 text-[13px] text-ink-3" data-testid="living-loading">Opening…</p>;
  }
  if (!living.session) {
    return (
      <p role="alert" className="gutter py-10 text-[13px] text-ink-2" data-testid="living-error">
        This session could not be opened. {living.error ? String(living.error.message) : ""}
      </p>
    );
  }

  const graph = living.graph;
  return (
    <LivingSurface
      session={living.session}
      graph={graph}
      steps={drawn.steps}
      channels={drawn.channels}
      onPlayed={living.consumed}
      reveal={reveal}
      state={living.state}
      preview={living.preview}
      busy={living.busy}
      vocabulary={living.vocabulary}
      onAccept={living.accept}
      onReject={living.reject}
      onPreviewOption={living.previewOption}
      onSelect={living.select}
      onCompose={living.compose}
      onSay={living.say}
      onRetry={living.retry}
      onDismiss={living.dismiss}
      // **Every direct edit goes through the session's edit verb**, which saves the draft, stamps
      // it as the person's and writes the receipt the server composes. A plain draft `PUT` would
      // change the pipeline and leave the log saying nothing about it.
      onAddStep={(contract) =>
        living.edit(withNode(graph, { id: idFor(graph, contract), contract_id: contract, params: [] }))}
      onSetParam={(node, setting, value) => living.edit(withParam(graph, node, setting, value))}
      onApplyChange={(block: ChangeBlock) =>
        living.edit(block.removes.reduce(withoutNode, graph))}
    />
  );
}

/** Spawn's reveal plan, computed **once** when the session first arrives in this tab.
 *
 * Held in a ref, because the count is written to `sessionStorage` straight away: recomputing on the
 * next render would read the count just written and plan nothing, cutting the reveal off mid-play.
 */
export function useFirstArrival(sessionId: string, session: AuthoringSession | null) {
  const plan = useRef<Record<string, number> | null>(null);
  const accepted = session
    ? session.history.filter((d) => d.kind === "step" && d.state === "accepted")
    : [];

  if (plan.current === null && session !== null) {
    const seen = session.mode === "spawn" ? (lastSeen(sessionId) ?? 0) : accepted.length;
    const fresh = accepted
      .slice(seen)
      .map((d) => (d.block.kind === "step_proposal" ? d.block.node : ""))
      .filter((node) => node && session.placement[node]);
    plan.current = revealPlan(fresh, (node) => session.placement[node]?.x ?? 0);
  }

  useEffect(() => {
    if (session !== null) markSeen(sessionId, accepted.length);
  }, [sessionId, session, accepted.length]);

  return plan.current ?? {};
}

/** Ports and tiers for what is on the canvas, from the server's drawn view of it.
 *
 * **Asked once per revision, never per frame.** The ghost is included so the step on offer shows
 * its real ports before it is accepted.
 */
function useDrawn(graph: DraftGraph, session: AuthoringSession | null) {
  const pending = session?.pending_proposal;
  const withGhost =
    pending?.block.kind === "step_proposal"
      ? withNode(graph, { id: pending.block.node, contract_id: pending.block.contract, params: [] })
      : graph;
  const drawn = useQuery({
    queryKey: ["living-draw", session?.id, session?.revision, pending?.id],
    queryFn: () => post<Built>("/pipeline/draw", withGhost),
    enabled: withGhost.nodes.length > 0,
  });
  return {
    steps: Object.fromEntries((drawn.data?.steps ?? []).map((step) => [step.id, step])) as Record<string, Step>,
    channels: drawn.data?.channels ?? [],
  };
}

function FakeLiving() {
  const [state, dispatch] = useReducer(authoringReducer, {
    ...initialAuthoring,
    snapshot: FAKE_SESSION,
  });
  const session = FAKE_SESSION;
  return (
    <LivingSurface
      session={session}
      graph={visibleGraph(state)}
      steps={FAKE_STEPS}
      channels={FAKE_CHANNELS}
      onPlayed={(event) => dispatch({ type: "consumed", seq: event.seq })}
      state={state}
      preview={{ revision: session.revision, text: "version: 6\ngoal:\n  want: [counts.matrix]\n" }}
      busy={(id) => state.inFlight === id}
      onAccept={(proposal, option = "keep") =>
        dispatch({ type: "accept", proposal, option, expectedRevision: session.revision })}
      onReject={(proposal) => dispatch({ type: "reject", proposalId: proposal.id })}
      onPreviewOption={(option) => dispatch({ type: "preview", option })}
      onSelect={(node) => dispatch({ type: "select", node })}
      onCompose={(text) => dispatch({ type: "compose", text })}
      onSay={(text) => dispatch({ type: "sent", text })}
      onRetry={() => undefined}
      onAddStep={() => undefined}
      onSetParam={() => undefined}
      onApplyChange={() => undefined}
      onDismiss={() => dispatch({ type: "dismiss" })}
    />
  );
}

/** The guided fake — a session that moves when a proposal is decided. Exported for its tests. */
export function GuidedLiving() {
  const [session, setSession] = useState<AuthoringSession>(guidedStart);
  const [state, dispatch] = useReducer(authoringReducer, { ...initialAuthoring, snapshot: session });

  const advance = (next: AuthoringSession) => {
    setSession(next);
    dispatch({ type: "snapshot", session: next });
  };

  return (
    <LivingSurface
      session={session}
      graph={session.graph}
      steps={FAKE_STEPS}
      channels={FAKE_CHANNELS}
      onPlayed={(event) => dispatch({ type: "consumed", seq: event.seq })}
      state={state}
      preview={null}
      busy={() => false}
      vocabulary={FAKE_VOCABULARY}
      onAccept={(proposal, option = "keep") =>
        advance(guidedDecide(session, proposal.id, "accepted", option))}
      onReject={(proposal) => advance(guidedDecide(session, proposal.id, "rejected"))}
      onPreviewOption={(option) => dispatch({ type: "preview", option })}
      onSelect={(node) => dispatch({ type: "select", node })}
      onCompose={(text) => dispatch({ type: "compose", text })}
      onSay={(text) => dispatch({ type: "sent", text })}
      onRetry={() => undefined}
      onAddStep={() => undefined}
      onSetParam={() => undefined}
      onApplyChange={() => undefined}
      onDismiss={() => dispatch({ type: "dismiss" })}
    />
  );
}

/** 1→1, N→N and N→1 on one canvas — Task 11's browser checkpoint, beside `LivingCollect`. */
function CollectLiving() {
  const [state, dispatch] = useReducer(authoringReducer, { ...initialAuthoring, snapshot: COLLECT_SESSION });
  return (
    <LivingSurface
      session={COLLECT_SESSION}
      graph={COLLECT_SESSION.graph}
      steps={COLLECT_STEPS}
      channels={COLLECT_CHANNELS}
      onPlayed={(event) => dispatch({ type: "consumed", seq: event.seq })}
      state={state}
      preview={null}
      busy={() => false}
      onAccept={() => undefined}
      onReject={() => undefined}
      onPreviewOption={(option) => dispatch({ type: "preview", option })}
      onSelect={(node) => dispatch({ type: "select", node })}
      onCompose={(text) => dispatch({ type: "compose", text })}
      onSay={(text) => dispatch({ type: "sent", text })}
      onRetry={() => undefined}
      onAddStep={() => undefined}
      onSetParam={() => undefined}
      onApplyChange={() => undefined}
      onDismiss={() => dispatch({ type: "dismiss" })}
    />
  );
}
