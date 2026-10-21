import { useQuery } from "@tanstack/react-query";
import { useEffect, useReducer, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router";

import { post } from "../../api/client";
import type { AuthoringBlock, AuthoringSession, Built, DraftGraph } from "../../api/types";
import { withNode, withoutNode, withParam } from "../graphOps";
import { authoringReducer, initialAuthoring } from "./authoringReducer";
import { CONFLICT_SESSION, COLLECT_CHANNELS, COLLECT_SESSION, COLLECT_STEPS, FAKE_CHANNELS, FAKE_SESSION, FAKE_STEPS, FAKE_VOCABULARY, readFakePreview } from "./fake";
import { guidedDecide, guidedStart } from "./guided";
import { RunSheet } from "../RunSheet";
import { entryChannels } from "../Sources";
import { withTypedValues } from "../useBuilder";
import { useGate } from "../useGate";
import { useKeep } from "../useKeep";
import { useRun } from "../useRun";
import { framed } from "./frame";
import { LivingSurface } from "./LivingSurface";
import { lastSeen, markSeen, revealPlan } from "./replay";
import { useAuthoringSession } from "./useAuthoringSession";

type ChangeBlock = Extract<AuthoringBlock, { kind: "change_set" }>;

const EMPTY_GRAPH: DraftGraph = { nodes: [], edges: [] };

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
  if (fake === "conflict") return <FakeLiving session={CONFLICT_SESSION} />;
  if (fake === "sheet") return <FakeLiving sheet />;
  if (fake === "question") return <FakeLiving steps={QUESTION_STEPS} selected="star_align" />;
  if (fake) return <FakeLiving />;
  if (session) return <LiveLiving key={session} sessionId={session} />;
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
  const navigate = useNavigate();
  const living = useAuthoringSession(sessionId, {
    onFork: id => navigate(`/build/living?session=${encodeURIComponent(id)}`),
  });
  const [sheet, setSheet] = useState(false);
  // **The run sheet reads the saved draft**, never the frame's preview metadata, and is asked
  // only when it opens: the canvas itself never calls the draw endpoint.
  const saved = living.session?.graph ?? EMPTY_GRAPH;
  const sheetView = useQuery({
    queryKey: ["living-run-sheet", living.session?.id, living.session?.revision],
    queryFn: () => post<Built>("/pipeline/draw", saved),
    enabled: sheet && saved.nodes.length > 0,
  });
  const reveal = useFirstArrival(sessionId, living.session);
  // **The session's own draft**, so Keep neither creates a second one nor re-saves the graph.
  const keeper = useKeep(saved, living.session ? { draftId: living.session.draft_id } : null);
  const gate = useGate(living.session?.draft_id ?? null);
  const runner = useRun({
    keep: keeper.keepAsync,
    lint: () => gate.start("lint"),
    gatePassed: gate.passed,
    openSheet: () => setSheet(true),
  });

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

  const graph = saved;
  return (
    <LivingSurface
      session={living.session}
      graph={graph}
      onPlayed={living.consumed}
      reveal={reveal}
      run={{
        onRun: () => void runner.run(),
        busy: runner.busy,
        stage: runner.stage,
        error: runner.error ?? keeper.error,
        kept: keeper.keptAt !== null,
        sheet: sheet && sheetView.data ? (
          <RunSheet inline
            name={living.session.name || "this pipeline"}
            // **Open human decisions come first on the sheet** — it counts what nobody answered
            // before it asks where the data is, which is the order Build's Run has always had.
            steps={sheetView.data.steps.map((step) => withTypedValues(step, graph))}
            sources={entryChannels(sheetView.data)}
            draftId={living.session.draft_id}
            blocked={keeper.blocked}
            gated={gate.passed}
            onClose={() => setSheet(false)}
          />
        ) : null,
      }}
      state={living.state}
      preview={living.preview}
      busy={living.busy}
      vocabulary={living.vocabulary}
      declarations={living.measurements}
      onCorrect={living.correct}
      onRelease={living.releaseTool}
      onDisagreement={living.answerDisagreement}
      correcting={living.correcting}
      onAccept={living.accept}
      onReject={living.reject}
      onPreviewOption={living.previewOption}
      onSelect={living.select}
      onCompose={living.compose}
      onSay={living.say}
      onRetry={living.retry}
      onApplySuggestion={living.applySuggestion}
      onDismissSuggestion={living.dismissSuggestion}
      suggesting={living.suggesting}
      onUpload={living.upload}
      onDismiss={living.dismiss}
      // **Every direct edit goes through the session's edit verb**, which saves the draft, stamps
      // it as the person's and writes the receipt the server composes. A plain draft `PUT` would
      // change the pipeline and leave the log saying nothing about it.
      onAddStep={(contract) =>
        living.edit(withNode(graph, { id: idFor(graph, contract), contract_id: contract, params: [] }))}
      onSetParam={(node, setting, value, why) => living.edit(withParam(graph, node, setting, value, why))}
      onApplyChange={(block: ChangeBlock) =>
        living.edit(block.removes.reduce(withoutNode, graph))}
      onEdit={living.edit}
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
    const seen = lastSeen(sessionId) ?? 0;
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

/** `?fake=question`: STAR_ALIGN opened with one value nobody has settled — what the *Question*
 *  board is compared against. */
const QUESTION_STEPS = { ...FAKE_STEPS, star_align: { ...FAKE_STEPS.star_align, settings: [
  ...FAKE_STEPS.star_align.settings,
  { name: "outSAMstrandField", value: null, via: "ext", tier: 4, because: "", axis_reason: "", premise: [],
    reason: "No rule settles it: your description does not say which tools read the alignments next, "
      + "and nothing measured it.",
    domain: { kind: "enum", values: ["None", "intronMotif"] } },
] } };

/** `?fake=sheet` opens the run sheet over the static session — what the *Run sheet* board is
 *  compared against, since a fake never keeps or lints. */
function FakeLiving({ session: given = FAKE_SESSION, sheet = false, steps = FAKE_STEPS, selected = null }: {
  session?: AuthoringSession; sheet?: boolean; steps?: typeof FAKE_STEPS; selected?: string | null;
}) {
  const session = framed(given, steps, FAKE_CHANNELS);
  const [state, dispatch] = useReducer(authoringReducer, {
    ...initialAuthoring,
    snapshot: session,
    selected,
  });
  return (
    <LivingSurface
      session={session}
      graph={session.graph}
      readPreview={readFakePreview(session)}
      onPlayed={(event) => dispatch({ type: "consumed", seq: event.seq })}
      state={state}
      preview={{ revision: session.revision, state: "ready", findings: [],
        text: "version: 6\ngoal:\n  want: [counts.matrix]\n" }}
      busy={(id) => state.inFlight === id}
      onAccept={(proposal, option = "keep") =>
        dispatch({ type: "accept", proposal, option, expectedRevision: session.revision })}
      onDisagreement={async () => undefined}
      onReject={(proposal) => dispatch({ type: "reject", proposalId: proposal.id })}
      onPreviewOption={(option) => dispatch({ type: "preview", option })}
      onSelect={(node) => dispatch({ type: "select", node })}
      onCompose={(text) => dispatch({ type: "compose", text })}
      onSay={(text) => dispatch({ type: "sent", text })}
      onRetry={() => undefined}
      onAddStep={() => undefined}
      onSetParam={() => undefined}
      onApplyChange={() => undefined}
      onEdit={() => undefined}
      onDismiss={() => dispatch({ type: "dismiss" })}
      run={sheet ? {
        onRun: () => undefined, busy: false, stage: null, error: null, kept: false,
        sheet: <RunSheet inline name={session.name} steps={Object.values(FAKE_STEPS)}
                         sources={entryChannels({ channels: FAKE_CHANNELS } as unknown as Built)}
                         draftId={null} gated={false} onClose={() => undefined} />,
      } : null}
    />
  );
}

/** The guided fake — a session that moves when a proposal is decided. Exported for its tests. */
export function GuidedLiving() {
  const [session, setSession] = useState<AuthoringSession>(guidedStart);
  const [state, dispatch] = useReducer(authoringReducer, { ...initialAuthoring, snapshot: session });

  const guided = framed(session, FAKE_STEPS, FAKE_CHANNELS);
  const advance = (next: AuthoringSession) => {
    setSession(next);
    dispatch({ type: "snapshot", session: next });
  };

  return (
    <LivingSurface
      session={guided}
      graph={session.graph}
      readPreview={readFakePreview(guided)}
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
      onEdit={() => undefined}
      onDismiss={() => dispatch({ type: "dismiss" })}
    />
  );
}

/** 1→1, N→N and N→1 on one canvas — Task 11's browser checkpoint, beside `LivingCollect`. */
function CollectLiving() {
  const [state, dispatch] = useReducer(authoringReducer, { ...initialAuthoring, snapshot: COLLECT_SESSION });
  return (
    <LivingSurface
      session={framed(COLLECT_SESSION, COLLECT_STEPS, COLLECT_CHANNELS)}
      graph={COLLECT_SESSION.graph}
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
      onEdit={() => undefined}
      onDismiss={() => dispatch({ type: "dismiss" })}
    />
  );
}
