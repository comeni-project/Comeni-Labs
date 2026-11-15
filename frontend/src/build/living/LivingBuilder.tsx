import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useSearchParams } from "react-router";

import { post } from "../../api/client";
import type { AuthoringSession, Built, DraftGraph } from "../../api/types";
import { idFor, withNode, withParam } from "../graphOps";
import { COLLECT_CHANNELS, COLLECT_SESSION, COLLECT_STEPS, FAKE_CHANNELS, FAKE_FILE, FAKE_SESSION, FAKE_STEPS, PORTS_SESSION, PORTS_STEPS } from "./fake";
import { RunSheet } from "../RunSheet";
import { entryChannels } from "../Sources";
import { withTypedValues } from "../useBuilder";
import { useGate } from "../useGate";
import { useKeep } from "../useKeep";
import { useRun } from "../useRun";
import { framed } from "./frame";
import { LivingSurface } from "./LivingSurface";
import { useAuthoringSession } from "./useAuthoringSession";

const EMPTY_GRAPH: DraftGraph = { nodes: [], edges: [] };

/** The one builder at `/build` (#395; `BuildRoute` opens every pipeline here).
 *
 * `?session=<id>` restores a live session. `?fake=1` opens a static session carrying every state
 * the agent's thread can be in, for looking at the page without a server; `?fake=collect`,
 * `?fake=sheet` and `?fake=question` open the collection shapes, the run sheet and a step with an
 * open value. Anything else says what to add rather than opening a default pipeline.
 */
export function LivingBuilder() {
  const [params] = useSearchParams();
  const session = params.get("session");
  const fake = params.get("fake");
  if (fake === "collect") return <FakeLiving session={COLLECT_SESSION} steps={COLLECT_STEPS} channels={COLLECT_CHANNELS} />;
  if (fake === "ports") return <FakeLiving session={PORTS_SESSION} steps={PORTS_STEPS} channels={[]} />;
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

function LiveLiving({ sessionId }: { sessionId: string }) {
  const living = useAuthoringSession(sessionId);
  const [sheet, setSheet] = useState(false);
  // **The run sheet reads the saved draft**, never the frame's preview metadata, and is asked
  // only when it opens: the canvas itself never calls the draw endpoint.
  const saved = living.session?.graph ?? EMPTY_GRAPH;
  const sheetView = useQuery({
    queryKey: ["living-run-sheet", living.session?.id, living.session?.revision],
    queryFn: () => post<Built>("/pipeline/draw", saved),
    enabled: sheet && saved.nodes.length > 0,
  });
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
      preview={living.preview}
      selected={living.selected}
      onSelect={living.select}
      composer={living.composer}
      onCompose={living.compose}
      sending={living.sending}
      onSay={living.say}
      onAnswer={living.answer}
      onRetry={living.retry}
      onUpload={living.upload}
      onReviewed={living.review}
      notice={living.notice}
      onDismiss={living.dismiss}
      // **Every direct edit goes through the session's edit verb**, which reads it as the person's
      // changes and builds again. A plain draft `PUT` would change the pipeline unrecorded.
      onAddStep={(contract) =>
        living.edit(withNode(graph, { id: idFor(graph, contract), contract_id: contract, params: [] }))}
      onSetParam={(node, setting, value, why) => living.edit(withParam(graph, node, setting, value, why))}
      onSwitchInput={living.switchInput}
      onWhole={living.keepWhole}
      onEdit={living.edit}
      onRename={living.rename}
    />
  );
}

/** `?fake=question`: STAR_ALIGN opened with one value nobody has settled — what the *Question*
 *  board is compared against. */
const QUESTION_STEPS = { ...FAKE_STEPS, star_align: { ...FAKE_STEPS.star_align, settings: [
  ...FAKE_STEPS.star_align.settings,
  { name: "outSAMstrandField", value: null, via: "ext", tier: 4, because: "", axis_reason: "", optional: false, premise: [],
    reason: "No rule settles it: your description does not say which tools read the alignments next, "
      + "and nothing measured it.",
    domain: { kind: "enum", values: ["None", "intronMotif"] } },
] } };

/** A static session: what is said is drawn as sending, and nothing else moves. `?fake=sheet` opens
 *  the run sheet over it, since a fake never keeps or lints. */
function FakeLiving({ session: given = FAKE_SESSION, sheet = false, steps = FAKE_STEPS,
  channels = FAKE_CHANNELS, selected: first = null }: {
  session?: AuthoringSession; sheet?: boolean; steps?: typeof FAKE_STEPS;
  channels?: typeof FAKE_CHANNELS; selected?: string | null;
}) {
  const session = framed(given, steps, channels);
  const [selected, setSelected] = useState<string | null>(first);
  const [composer, setComposer] = useState("");
  const [sending, setSending] = useState<string[]>([]);
  const nothing = () => undefined;
  return (
    <LivingSurface
      session={session}
      graph={session.graph}
      preview={{ revision: session.revision, state: "ready", findings: [],
        text: FAKE_FILE }}
      selected={selected}
      onSelect={setSelected}
      composer={composer}
      onCompose={setComposer}
      sending={sending}
      onSay={(text) => { setSending([...sending, text]); setComposer(""); }}
      onAnswer={nothing}
      onRetry={nothing}
      onReviewed={nothing}
      onDismiss={nothing}
      onAddStep={nothing}
      onSetParam={nothing}
      onEdit={nothing}
      run={sheet ? {
        onRun: nothing, busy: false, stage: null, error: null, kept: false,
        sheet: <RunSheet inline name={session.name} steps={Object.values(FAKE_STEPS)}
                         sources={entryChannels({ channels: FAKE_CHANNELS } as unknown as Built)}
                         draftId={null} gated={false} onClose={nothing} />,
      } : null}
    />
  );
}
