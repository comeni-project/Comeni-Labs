import { useQuery } from "@tanstack/react-query";
import { useReducer } from "react";
import { useSearchParams } from "react-router";

import { post, put } from "../../api/client";
import type { AuthoringSession, Built, DraftGraph, Step } from "../../api/types";
import { withNode } from "../graphOps";
import { authoringReducer, initialAuthoring, visibleGraph } from "./authoringReducer";
import { FAKE_SESSION, FAKE_STEPS } from "./fake";
import { LivingSurface } from "./LivingSurface";
import { useAuthoringSession } from "./useAuthoringSession";

/** `/build/living` — a secondary route while `/build` stays exactly as it is.
 *
 * `?session=<id>` restores a live authoring session; `?fake=1` opens a static session carrying
 * every block state, which is Task 9's checkpoint and what the artboard comparison is rendered
 * against. Anything else says what to add rather than opening a default pipeline.
 */
export function LivingBuilder() {
  const [params] = useSearchParams();
  const session = params.get("session");
  if (params.get("fake")) return <FakeLiving />;
  if (session) return <LiveLiving sessionId={session} />;
  return (
    <p className="gutter py-10 text-[13px] text-ink-2" data-testid="living-empty">
      Open a session with <span className="font-data">?session=&lt;id&gt;</span>.
    </p>
  );
}

function LiveLiving({ sessionId }: { sessionId: string }) {
  const living = useAuthoringSession(sessionId);
  const steps = useDrawnSteps(living.graph, living.session);

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

  const session = living.session;
  return (
    <LivingSurface
      session={session}
      graph={living.graph}
      steps={steps}
      state={living.state}
      preview={living.preview}
      busy={living.busy}
      onAccept={living.accept}
      onReject={living.reject}
      onPreviewOption={living.previewOption}
      onSelect={living.select}
      onCompose={living.compose}
      onSay={living.say}
      onRetry={living.retry}
      onDismiss={living.dismiss}
      onAddStep={(contract) => {
        // A direct edit goes through the draft's own save, where the server stamps it as the
        // person's. The session re-reads and the receipt arrives with it.
        const id = contract.split("@")[0].split("/").slice(1).join("_").replace(/\W/g, "_");
        const graph = withNode(living.graph, { id: `${id}_1`, contract_id: contract, params: [] });
        void put(`/pipeline/drafts/${session.draft_id}`, { name: session.name, graph });
      }}
    />
  );
}

/** Ports and tiers for what is on the canvas, from the server's drawn view of it.
 *
 * **Asked once per revision, never per frame.** The ghost is included so the step on offer shows
 * its real ports before it is accepted.
 */
function useDrawnSteps(graph: DraftGraph, session: AuthoringSession | null): Record<string, Step> {
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
  return Object.fromEntries((drawn.data?.steps ?? []).map((step) => [step.id, step]));
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
      state={state}
      preview={{ revision: session.revision, text: "version: 6\ngoal:\n  want: [counts.matrix]\n" }}
      busy={(id) => state.inFlight === id}
      onAccept={(proposal, option = "keep") =>
        dispatch({ type: "accept", proposal, option, expectedRevision: session.revision })}
      onReject={(proposal) => dispatch({ type: "reject", proposalId: proposal.id })}
      onPreviewOption={(option) => dispatch({ type: "preview", option })}
      onSelect={(node) => dispatch({ type: "select", node })}
      onCompose={(text) => dispatch({ type: "compose", text })}
      onSay={() => dispatch({ type: "sent" })}
      onRetry={() => undefined}
      onAddStep={() => undefined}
      onDismiss={() => dispatch({ type: "dismiss" })}
    />
  );
}
