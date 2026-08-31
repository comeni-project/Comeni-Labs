import { useEffect, useMemo, useRef, useState } from "react";

import type { components } from "../api/schema";
import { useTitle } from "../app/useTitle";
import { Failed, Loading } from "../ui/States";
import { Canvas } from "./Canvas";
import { Node } from "./Node";
import { Settings } from "./Settings";
import { Grip, RAIL, useWidth } from "./Panels";
import { ArtifactView } from "./ArtifactView";
import { Browse } from "./Browse";
import { Picker } from "./Picker";
import { entryChannels, Sources } from "./Sources";
import { Status } from "./Status";
import { Swap } from "./Swap";
import { useRun } from "./useRun";
import { usePipelineDraft } from "./usePipelineDraft";
import { Findings } from "./Findings";
import { bounds, Minimap } from "./Minimap";
import { useGate } from "./useGate";
import { useKeep } from "./useKeep";
import { NODE_W, portOffset } from "./geometry";
import { Assistant, StepChoice } from "./Rail";
import { RunSheet } from "./RunSheet";
import { Wires } from "./Wires";
import type { AnsweredStep } from "./useBuilder";
import { graphOf, unanswered, useBuilder, useExample, withTypedValues } from "./useBuilder";
import { accepts, useCompatibility } from "./useCompatibility";
import { useView } from "./useView";

type Built = components["schemas"]["BuiltPipeline"];

const label = "text-label uppercase tracking-[.13em] font-semibold text-ink-3";

/** A panel that collapses to a 42px stub with a vertical label — and keeps its count. */
function Side({
  side,
  title,
  width,
  collapsed,
  onExpand,
  badge,
  header = true,
  children,
}: {
  side: "left" | "right";
  title: string;
  width: number;
  collapsed: boolean;
  onExpand: () => void;
  badge?: number;
  /** Draw the panel's own title bar. **False for the right column**, whose tab strip is its
   *  top edge — a header above the tabs was one more band of chrome saying a word the tabs
   *  already say. The collapsed stub still uses `title`, which is the only place it earns
   *  its keep. */
  header?: boolean;
  children?: React.ReactNode;
}) {
  const testid = side === "left" ? "modules" : "rail";
  if (collapsed) {
    return (
      <button
        data-testid={testid}
        data-collapsed="true"
        onClick={onExpand}
        style={{ width: RAIL }}
        className="side shrink-0 flex flex-col items-center gap-3 py-4 bg-surface cursor-pointer
                   border-0 border-l border-line text-ink-3 hover:text-ink"
      >
        <span className="[writing-mode:vertical-rl] text-label uppercase tracking-[.13em]">
          {title}
        </span>
        {/* **The count survives the collapse.** `dashboard.md` §4: hiding the panel must never
            hide what is blocking your run. */}
        {badge !== undefined && badge > 0 && (
          <span className="font-data text-secondary text-[var(--undecided)]">{badge}</span>
        )}
      </button>
    );
  }
  return (
    <div
      data-testid={testid}
      data-collapsed="false"
      style={{ width }}
      className="side shrink-0 flex flex-col bg-surface overflow-hidden"
    >
      {header && (
        <div className="flex items-baseline gap-3 px-4 py-3 border-b border-line">
          <span className={label}>{title}</span>
          {badge !== undefined && badge > 0 && (
            <span className="ml-auto font-data text-secondary text-[var(--undecided)]">
              {badge}
            </span>
          )}
        </div>
      )}
      {/* **Not a scroller.** `Rail` owns a `flex-1 min-h-0 overflow-auto` of its own,
          so this made two nested scroll containers around one list — which is a well-known way
          to lose a scroll position: the outer one scrolls, the inner content changes height, and
          the outer clamps back to zero. The 2026-08-29 walk lost a half-filled parameter form to
          exactly that.

          `min-h-0` is load-bearing beside `flex-1`: without it a flex child refuses to shrink
          below its content and the child's own scroller never engages. */}
      <div className="flex-1 min-h-0 overflow-hidden">{children}</div>
    </div>
  );
}

/** Mendel — the pipeline builder.
 *
 * **Phase 3 is the shell and nothing in it**, deliberately: three columns that resize and
 * collapse, and a canvas that pans and zooms over an empty surface. Getting the frame wrong and
 * then building five phases on top of it is the failure this plan's checkpoints exist to stop.
 *
 * Every measurement here is `docs/design/dashboard.md` §4's — 190–430 left, 280–560 right, a
 * 42px collapsed rail, a 22px grid, zoom clamped 0.3–2.2 — and the pan/zoom maths is ported from
 * `dashboard.html` rather than reinvented.
 */
export function Builder() {
  useTitle("Builder");
  const right = useWidth(320, 280, 560);
  const { view, onWheel, onPointerDown, reset, nudge, fit } = useView();
  const box = useRef<HTMLDivElement>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [carded, setCarded] = useState<string | null>(null);
  /** Which output port a wire is being dragged from. `null` most of the time. */
  const [dragging, setDragging] = useState<{ node: string; port: string } | null>(null);

  // **`/build?draft=<id>` opens THAT pipeline.** It always opened the example before Plan 4
  // phase 3a, which meant every link on the front door — one per row of the *by pipeline*
  // table — went to the canonical spine instead of the thing you clicked.
  const draft = usePipelineDraft();
  const example = useExample();

  // A named draft that cannot be read is an ERROR, never a quiet fallback to the example. The
  // failure mode being avoided is the worst kind: you edit for an hour, and you were editing a
  // different pipeline the whole time.
  if (draft.openError) {
    return (
      <div className="grid place-items-center h-full">
        <Failed error={draft.openError} />
      </div>
    );
  }
  if (draft.loading) {
    return (
      <div className="grid place-items-center h-full">
        <Loading what="the pipeline" />
      </div>
    );
  }

  return example.data ? (
    <Editing built={example.data} opened={draft.opened} draft={draft}
      view={view} onWheel={onWheel} onPointerDown={onPointerDown}
      reset={reset} nudge={nudge} fit={fit} box={box} right={right}
      selected={selected} setSelected={setSelected}
      carded={carded} setCarded={setCarded} dragging={dragging} setDragging={setDragging} />
  ) : (
    <div className="grid place-items-center h-full">
      {example.isLoading && <Loading what="the pipeline" />}
      {example.error && <Failed error={example.error} />}
    </div>
  );
}

/** Canvas coordinates → screen coordinates, for the two popovers that mount outside the stage.
 *
 * **Two corrections, and leaving either out is visible immediately.** The port picker and the
 * settings card are rendered at the builder's root rather than inside the transformed stage,
 * because the canvas clips its own overflow and a card that vanished at the edge of the frame
 * would be unreachable. So a canvas coordinate needs:
 *
 * 1. **the view transform, applied forward** — `translate(view.x, view.y)` then `scale(view.k)`.
 *    Without it the popover opens in the page's top-left corner at any zoom but 1:1, which is
 *    what the picker did until phase 6 task 3.
 * 2. **the canvas's own offset in the page.** Without it every card sits exactly the height of
 *    the header and the provenance bar too high — which is what the settings card did the first
 *    time it was anchored, and it is why this is a function rather than the same two lines
 *    written twice.
 *
 * `useView`'s pointer handler undoes the same transform to put the cursor into canvas space.
 * Three places, one transform, written the same way round each time.
 */
function onScreen(at: { x: number; y: number }, view: { x: number; y: number; k: number }) {
  const r = document.querySelector('[data-testid="canvas"]')?.getBoundingClientRect();
  return {
    x: (r?.left ?? 0) + at.x * view.k + view.x,
    y: (r?.top ?? 0) + at.y * view.k + view.y,
  };
}

/* eslint-disable @typescript-eslint/no-explicit-any */
/** The screen, once there is something to edit.
 *
 * Split from `Builder` because `useBuilder` needs a starting graph and hooks cannot wait for a
 * query. The alternative — a hook that tolerates `undefined` — would put "is there a pipeline
 * yet" into every line below.
 */
function Editing({ built, opened, draft, view, onWheel, onPointerDown, reset, nudge, fit, box,
  right,
  selected, setSelected, carded, setCarded, dragging, setDragging }: any) {
  // **Node offsets live in `useGraph`, not in each node.** They were local state, which meant a
  // dragged node left its wires behind — the graph broke the moment you touched it.
  //
  // **`draft.save` is passed, and until Plan 4 phase 3a nothing ever was.** `useGraph` has taken
  // an optional `save` and debounced it at 5s since 3E, and no caller supplied one — so the
  // autosave had never fired in production. That is not a missing feature so much as a missing
  // premise: the argument for collapsing four buttons into one *Run* is that drafts already
  // save themselves.
  const builder = useBuilder(opened ?? graphOf(built), draft.save);
  const index = useCompatibility();
  const data: Built | null = builder.drawn;
  const offsets = builder.offsets;
  /** The draft's labels, by socket key. A list on the wire because order is a list's to keep
   *  and a `dict[str, str]` in a Pydantic model is a `Mark.ANY_KEY` the egress guard would have
   *  to reason about; a record here because the canvas looks one up per socket. */
  const labels = useMemo(
    () => Object.fromEntries((builder.graph.labels ?? []).map((l) => [l.key, l.label])),
    [builder.graph.labels],
  );
  /** Every socket a person has given its own channel. The server says what the grouping IS;
   *  this says which of it was somebody's decision — the difference between offering *split*
   *  and offering *merge*. */
  const declaredChannels = useMemo(
    () => (builder.graph.channels ?? []).flatMap((c) => c.ports),
    [builder.graph.channels],
  );
  const isLoading = data === null;
  const error = builder.drawnError;
  const [panel, setPanel] = useState<"step" | "ask" | "problems">("step");
  /** Whether the run sheet is open. **It was `panel: "run"` and nothing rendered it** — so the
   *  fourth verb of `Run` set a tab that did not exist and the rail went blank. A sheet is not
   *  a tab: it is the modal step where a person says where their data is, and `n-brun` draws it
   *  over the canvas. */
  const [sheet, setSheet] = useState(false);
  // **The draft lifecycle, finally connected.** 3E built create/save/keep on the server and
  // wired none of it; a gate needs an artifact on disk, which is what surfaced that.
  const keeper = useKeep(builder.graph);
  // **Read here, not inside the panel.** `useGate` shares its state through the query cache,
  // so this is the same gate the toolbar button and the gate tab are looking at — which is
  // what makes "a gate passed" mean the one a person just watched.
  const gate = useGate(keeper.draftId);
  // **One control, four verbs** — `impl-walk`. The rail is gone; this is what it did.
  const runner = useRun({
    keep: keeper.keepAsync,
    lint: () => gate.start("lint"),
    gatePassed: gate.passed,
    openSheet: () => setSheet(true),
  });

  /** Canvas or artifact. **`pipeline.yml` IS the pipeline**, so the second view of the canvas
   *  is the artifact itself rather than a list (`n-bartifact`). */
  const [view2, setView2] = useState<"canvas" | "artifact">("canvas");

  /** Which step is being swapped, if any. **Shown, then asked** — nothing is applied while
   *  this is open (`n-bswap`). */
  const [swapping, setSwapping] = useState<string | null>(null);

  /** Whether the browse overlay is open. It replaced the permanent left palette — creation is
   *  monthly, checking a run is daily, so a third column was rent paid every day for a thing
   *  used monthly (`impl-settled`). */
  const [browsing, setBrowsing] = useState(false);

  /** Which port's picker is open, and where to draw it. `null` most of the time. */
  const [picking, setPicking] = useState<
    { node: string; port: any; at: { x: number; y: number } } | null
  >(null);

  /** Whether a node is being dragged. **The grid exists only while it is.**
   *
   * `impl-geom`: *a permanent grid is the loudest hobby-editor signal there is.* `Canvas` had
   * it on by default with an argument for it — *a grid is an invitation; it says things can be
   * placed here* — and that argument is answered rather than ignored: the invitation is real
   * and it belongs to the gesture, not to the resting screen. Galaxy's idea, scoped.
   */
  const [moving, setMoving] = useState(false);

  /** Where the cursor is while a wire is being dragged, in canvas coordinates. */
  const [cursor, setCursor] = useState<{ x: number; y: number } | null>(null);
  /** Where a right-click opened a menu, and on what. */
  const [menu, setMenu] = useState<{ node: string; x: number; y: number } | null>(null);

  /** What each node declares, so the wires land on the chevrons the canvas drew.
   *
   * From `steps[].ports`, which is the contract's own list — the same source `Port.tsx` renders
   * from. Deriving it anywhere else is how the wire and the chevron came to disagree by 39px.
   */
  const portIndex = useMemo(() => {
    const index: Record<string, { ins: string[]; outs: string[]; width: number }> = {};
    for (const step of data?.steps ?? []) {
      index[step.id] = {
        ins: step.ports.filter((p) => p.side === "in").map((p) => p.name),
        outs: step.ports.filter((p) => p.side === "out").map((p) => p.name),
        width: data?.layout.nodes.find((n) => n.id === step.id)?.width ?? 232,
      };
    }
    return index;
  }, [data]);

  /** **A wire drag ends wherever the pointer is let go**, not only on a port.
   *
   * Releasing over empty canvas has to cancel, or the next click on any input silently
   * completes a wire you abandoned a minute ago — a gesture with no end is worse than one that
   * fails.
   */
  useEffect(() => {
    if (!dragging) return;
    const done = () => {
      setDragging(null);
      setCursor(null);
    };
    window.addEventListener("pointerup", done);
    return () => window.removeEventListener("pointerup", done);
  }, [dragging, setDragging]);

  /** **Delete removes the selected step.** Not while a field has focus, or typing a value into
   *  the settings card would delete the step you are configuring. */
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Delete" && e.key !== "Backspace") return;
      const target = e.target as HTMLElement | null;
      const typing =
        target &&
        (target.tagName === "INPUT" ||
          target.tagName === "SELECT" ||
          target.tagName === "TEXTAREA" ||
          target.isContentEditable);
      if (typing || !selected) return;
      e.preventDefault();
      builder.removeNode(selected);
      setSelected(null);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [selected, builder, setSelected]);

  /** Every step with **what this person answered** laid over it — computed once, because three
   *  things read it: the status line's count, the rail's sentence, and the settings card. */
  const answered: AnsweredStep[] = (data?.steps ?? []).map((step: any) =>
    withTypedValues(step, builder.graph),
  );

  /** **Values, not steps.** `Status.open` is documented as *how many values nobody has
   *  answered*, and it was handed `data.needs_review.length` — which is a list of STEP ids. On
   *  the spine that is 5 either way, so the two lines agreed by coincidence and the provenance
   *  bar beside it already said `5 steps need your decision` off the same number: two sentences,
   *  one fact, one of them mislabelled. It also never moved when you answered something, because
   *  a step with one open value has a step id whatever you do to the value. */
  const blocking = unanswered(answered);

  return (
    <div className="grid grid-rows-[auto_1fr] h-full overflow-hidden">
      {/* **A title row, not a toolbar.** It was a 38px strip with the name set at 15px beside
          three controls, which reads as a browser chrome bar; every artboard opens with the
          pipeline's name at 26px and the status line beside it, and the toggle and Run at the
          far right. The name is the largest thing on the screen because it is what the screen
          is about. */}
      <div className="flex items-baseline gap-4 px-6 pt-5 pb-4">
        {/* **The name is the draft's own.** It was the literal string `RNA-seq spine`, which is
            why the 2026-08-29 walk deleted every step, replaced them, and still had the old
            name on screen. `PipelineDraft.name` had existed since 3E with nothing setting it. */}
        <input
          data-testid="pipeline-name"
          aria-label="pipeline name"
          value={draft.name}
          placeholder={draft.draftId ? draft.draftId.slice(0, 8) : "untitled pipeline"}
          onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
            draft.rename(e.target.value, builder.graph)}
          className="bg-transparent border-0 outline-none text-ink min-w-[8ch] w-[16ch]
                     text-title font-semibold tracking-[-.03em]
                     focus-visible:shadow-[var(--ring)] rounded-r px-1 -mx-1
                     [field-sizing:content]"
        />
        <Status
          savedAt={draft.savedAt}
          saving={draft.saving}
          dirty={builder.dirty}
          error={draft.error}
          valid={builder.findings.length === 0}
          open={blocking}
          stale={builder.stale}
        />

        <div className="ml-auto flex border border-line-2">
          {(["canvas", "artifact"] as const).map((which) => (
            <button
              key={which}
              type="button"
              data-testid={`view-${which}`}
              onClick={() => setView2(which)}
              aria-pressed={view2 === which}
              className={`font-data px-[15px] py-[7px] text-label uppercase tracking-[.09em]
                          border-0 cursor-pointer transition-colors
                          ${view2 === which
                            ? "bg-[var(--link-soft)] text-link"
                            : "bg-transparent text-ink-3 hover:text-ink"}`}
            >
              {which}
            </button>
          ))}
        </div>

        {/* **The one action, and it does the whole sequence.** Keep, lint, open the run sheet,
            submit. It is disabled only while it is working — never because a step somebody
            cannot see has not happened yet. */}
        <button
          data-testid="run"
          type="button"
          disabled={runner.busy || builder.graph.nodes.length === 0}
          onClick={() => void runner.run()}
          className="px-[26px] py-[9px] border-0 cursor-pointer lift font-semibold
                     text-[13.5px] bg-[var(--link)] text-paper
                     disabled:cursor-not-allowed disabled:opacity-40"
        >
          {runner.stage === "keeping" ? "Keeping…"
            : runner.stage === "linting" ? "Checking…"
            : "Run"}
        </button>
        {runner.error && (
          <span data-testid="run-error" className="text-secondary">
            <Failed error={runner.error} padded={false} />
          </span>
        )}
        {/* **Keep, Gate and Run left this toolbar for `Walk`, and `Walk` has now left too.**
            W2 §13 moved three controls into one rail; Plan 4 phase 3a removed the rail. One
            **Run** in the header orchestrates all of it, and the status line says what is
            true. `execution-boundary.md` §3's rule — that a gate and a run never share a
            label — is kept in the BACKEND, which is where it was always load-bearing. */}
        {/* **`N to decide` is deleted, because the status line already says it.** It read
            `1 to decide` beside a status line reading `1 value needs you` — one fact, two
            renderings, eighteen characters apart. Found by looking at the built page.

            This is the same discipline as *one control per action*: two places that say the
            same thing are two places that can come to disagree, and the reader has to work out
            which is authoritative. `Status` owns it. */}
      </div>
      <div
        ref={box}
        data-testid="builder"
        className="builder overflow-hidden"
      >
      <div className="stage flex flex-col overflow-hidden">
        {view2 === "artifact" && <ArtifactView draftId={draft.draftId} />}
        <Canvas
        grid={moving}
        view={view}
        onWheel={onWheel}
        onPointerDown={onPointerDown}
        // **The canvas is a drop target.** `preventDefault` on dragover is what makes a drop
        // land at all — without it the browser refuses every drop silently, which is exactly
        // the kind of "control that does nothing" this screen has been fixing.
        // The cursor, in canvas coordinates: the stage is `translate(view.x, view.y)` then
        // `scale(view.k)`, so undoing it is subtract-then-divide. Only tracked mid-drag, so a
        // still canvas costs nothing.
        onPointerMove={(e: React.PointerEvent) => {
          if (!dragging) return;
          const r = e.currentTarget.getBoundingClientRect();
          setCursor({
            x: (e.clientX - r.left - view.x) / view.k,
            y: (e.clientY - r.top - view.y) / view.k,
          });
        }}
        // **Clicking empty canvas deselects.** A selection you cannot clear means the rail keeps
        // showing a step you have stopped caring about, and Delete stays armed on it.
        onClick={(e: React.MouseEvent) => {
          const target = e.target as HTMLElement;
          if (target.closest('[data-testid="node"]')) return;
          if (target.closest("[data-zoomer]")) return;
          setSelected(null);
          setCarded(null);
        }}
        // **The drop handlers are deleted with the palette that dragged onto them.** They were
        // half of a gesture whose other half no longer exists, and a drop target with no drag
        // source is dead code that reads as a feature. The three ways in are now the port
        // picker, the browse overlay, and this canvas's own context menu.
        onContextMenu={(e: React.MouseEvent) => {
          const target = e.target as HTMLElement;
          if (target.closest('[data-testid="node"]')) return;
          e.preventDefault();
          setBrowsing(true);
        }}
        footer={
          <>
            {/* **Bottom left: `Fit` and `+ Add step`** — the artboard's two, in the artboard's
                corner. `+ Add step` is the browse overlay's only visible affordance; before
                this it opened on a right-click and by ⌘K, which the 2026-08-29 walk already
                found unreachable once. A gesture with no visible handle is a gesture nobody
                uses. */}
            <div data-zoomer className="absolute left-[22px] bottom-[18px] flex gap-2">
              <button
                data-testid="fit"
                aria-label="fit the pipeline"
                onClick={() => {
                  const r = box.current?.getBoundingClientRect();
                  if (!data || !r || data.layout.nodes.length === 0) return;
                  const b = bounds(data.layout.nodes, offsets);
                  fit(b.width, b.height, r.width, r.height, { x: b.left, y: b.top });
                }}
                className="font-data text-label text-ink-3 border border-line-2 px-[11px]
                           py-[6px] bg-transparent cursor-pointer lift hover:text-ink"
              >
                Fit
              </button>
              <button
                data-testid="add-step"
                onClick={() => setBrowsing(true)}
                className="font-data text-label text-link border border-[var(--link-line)]
                           px-[11px] py-[6px] bg-transparent cursor-pointer lift"
              >
                + Add step
              </button>
            </div>

            {/* **Bottom right: the minimap, and it is load-bearing.** `impl-settled` deletes
                the left steps list and says *orientation is the minimap's job* — so this is
                what pays for that deletion rather than a decoration. It is drawn from the same
                `offsets` the canvas is, at whatever scale fits the graph, and each mark takes
                its node's tier colour so *where is the thing that needs me* is answerable
                without panning. */}
            {data && data.layout.nodes.length > 0 && (
              <Minimap nodes={data.layout.nodes} offsets={offsets} />
            )}

            <div
              data-zoomer
              className="absolute right-4 bottom-[86px] flex items-center gap-1 rounded-r
                         border border-line bg-surface px-1 py-1 shadow-e1"
            >
              <button onClick={() => nudge(-0.1)} aria-label="zoom out" className={zoomBtn}>
                −
              </button>
              <span
                data-testid="zoom"
                data-k={view.k}
                className="font-data text-secondary text-ink-3 w-11 text-center tabular-nums"
              >
                {Math.round(view.k * 100)}%
              </span>
              <button onClick={() => nudge(0.1)} aria-label="zoom in" className={zoomBtn}>
                +
              </button>
              <button onClick={reset} aria-label="reset the view" className={zoomBtn}>
                reset
              </button>
            </div>
          </>
        }
      >
        {isLoading && <Loading what="the pipeline" />}
        {error && <Failed error={error} />}
        {data && (
          <>
            {/* **What this pipeline needs from you**, before the wires so a node draws over
                both. An entry channel used to draw a stub running off to the left with a
                clipped label and no terminus: the canvas said *something feeds this* and never
                what, so the only way to learn what the pipeline required was to press Run. */}
            <Sources
              data={data}
              offsets={offsets}
              labels={labels}
              onRename={builder.setLabel}
              declared={declaredChannels}
              onSplit={builder.splitChannel}
              onMerge={builder.mergeChannel}
            />

            {/* Wires first, so a node draws over the line that reaches it rather than under. */}
            <Wires
              // The client's edges, not the server's — same reason as the nodes.
              wires={builder.graph.edges.map((e) => ({
                ...e,
                type_id:
                  data.layout.wires.find(
                    (w) =>
                      w.from_node === e.from_node &&
                      w.from_port === e.from_port &&
                      w.to_node === e.to_node &&
                      w.to_port === e.to_port,
                  )?.type_id ?? "",
                points: [],
                label_at: { x: 0, y: 0 },
              }))}
              at={offsets}
              ports={portIndex}
              width={data.layout.width}
              height={data.layout.height}
              pending={
                dragging && cursor && portIndex[dragging.node]
                  ? {
                      // Left to right: a wire in flight leaves the RIGHT edge, at the port's
                      // own offset. Same derivation the settled wires use — `portOffset`.
                      from: {
                        x: (offsets[dragging.node]?.x ?? 0) + NODE_W,
                        y:
                          (offsets[dragging.node]?.y ?? 0) +
                          portOffset(
                            Math.max(0, portIndex[dragging.node].outs.indexOf(dragging.port)),
                          ),
                      },
                      to: cursor,
                    }
                  : null
              }
              onDetach={(w) =>
                builder.disconnect(w.from_node, w.from_port, w.to_node, w.to_port)
              }
            />
            {/* **The client's nodes, decorated with the server's answers.** It iterated
                `data.layout.nodes` — the server's list — so adding or deleting a step did not
                change the picture until a round trip came back. The graph is what you are
                editing; the server tells you about it. */}
            {builder.graph.nodes.map((own) => {
              const placed = data.layout.nodes.find((n) => n.id === own.id) ?? {
                id: own.id,
                rank: 0,
                order: 0,
                x: 0,
                y: 0,
                width: 232,
                height: 56,
                tier: 4,
              };
              return (
              <Node
                key={placed.id}
                placed={placed}
                step={answered.find((s) => s.id === placed.id)}
                zoom={view.k}
                selected={selected === placed.id}
                onSelect={() => setSelected(placed.id)}
                onContextMenu={(e: React.MouseEvent) => {
                  e.preventDefault();
                  setSelected(placed.id);
                  setMenu({ node: placed.id, x: e.clientX, y: e.clientY });
                }}
                onOpenSettings={() => setCarded(placed.id)}
                offset={offsets[placed.id] ?? { x: 0, y: 0 }}
                onMoving={setMoving}
                onExplore={(port: any) =>
                  setPicking({
                    node: placed.id,
                    port,
                    // **In CONTAINER coordinates, not canvas ones.** The popover mounts
                    // outside the transformed stage, so a canvas coordinate handed to it
                    // ignores pan and zoom entirely — it opened in the top-left corner of the
                    // page, over the header, whichever port you clicked.
                    //
                    // The transform is `translate(view.x, view.y)` then `scale(view.k)`, and
                    // this is it applied forward; line ~400 undoes the same one to put the
                    // cursor into canvas space. Two places, one transform, written the same
                    // way round each time.
                    //
                    // Beside the node rather than exactly on the port: at low zoom an exact
                    // anchor puts a 340px panel on top of the thing it is describing.
                    at: onScreen(
                      {
                        x: (offsets[placed.id]?.x ?? 0) + NODE_W + 16,
                        y: offsets[placed.id]?.y ?? 0,
                      },
                      view,
                    ),
                  })}
                onDrag={(by) => builder.moveNode(placed.id, by)}
                dragging={dragging}
                onStartWire={(port: string) => setDragging({ node: placed.id, port })}
                onFinishWire={(port: string) => {
                  if (dragging) builder.connect(dragging.node, dragging.port, placed.id, port);
                  setDragging(null);
                }}
                verdictFor={(port: string) => {
                  // **A lookup, not a decision.** The server computed what satisfies what;
                  // `validate` on drop is still the authority.
                  if (!dragging || !index.data) return undefined;
                  const src = data?.steps.find((s) => s.id === dragging.node);
                  const tgt = data?.steps.find((s) => s.id === placed.id);
                  if (!src || !tgt) return undefined;
                  return accepts(
                    index.data,
                    `${src.contract_id}#${dragging.port}`,
                    `${tgt.contract_id}#${port}`,
                  );
                }}
              />
              );
            })}
          </>
        )}
        </Canvas>
      </div>

      <Grip
        side="right"
        onPointerDown={(e) => right.onPointerDown(e, "right")}
        onCollapse={() => right.setCollapsed(true)}
        onNudge={() => {}}
      />
      <Side
        side="right"
        title="Review"
        width={right.width}
        collapsed={right.collapsed}
        onExpand={() => right.setCollapsed(false)}
        badge={blocking}
        header={false}
      >
        {/* **ONE strip of tabs.** There were four stacked bands of chrome above the first
            sentence anybody wanted to read: the `Side` header, the gate panel, `Builder`'s
            three tabs, and `Rail`'s own three under those.

            **Lint, Preview and Send to Wiener are not in any artboard, and they are gone from
            here.** `impl-walk` says where they went: *Run = keep -> lint -> open the run sheet
            -> submit*. They are steps in one action, not three buttons beside the canvas —
            and the backend split `execution-boundary.md` §3 protects is a split between two
            SERVER verbs, never between two controls a person has to press in order. */}
        <div
          data-testid="rail-tabs"
          className="flex gap-0.5 px-4 pt-3.5 border-b border-line"
        >
          {(["step", "ask", "problems"] as const).map((t) => (
            <button
              key={t}
              data-testid={`tab-${t}`}
              data-active={panel === t || undefined}
              onClick={() => setPanel(t)}
              className="font-data text-label uppercase tracking-[.09em] px-[11px] py-1.5
                         bg-transparent border-0 cursor-pointer text-ink-3 hover:text-ink
                         data-[active]:text-ink
                         data-[active]:shadow-[inset_0_-2px_0_var(--link)]"
            >
              {t === "ask" ? "Assistant" : t}
              {t === "problems" && builder.findings.length > 0 && (
                <span className="ml-1.5 text-[var(--undecided)]">{builder.findings.length}</span>
              )}
            </button>
          ))}
          {/* **A chevron, not the word `collapse`.** Three tabs plus the word overflowed a
              320px rail and clipped it — and a rail with no visible way to collapse is one the
              Grip's double-click is the only route into, which is the palette-with-no-keyboard
              defect wearing different clothes. */}
          <button
            data-testid="collapse-right"
            aria-label="collapse the rail"
            onClick={() => right.setCollapsed(true)}
            className="ml-auto text-body text-ink-3 bg-transparent border-0 cursor-pointer px-1
                       hover:text-ink"
          >
            ›
          </button>
        </div>

        <div className="flex-1 min-h-0 overflow-auto">
          {panel === "ask" && <Assistant />}

          {panel === "problems" && (
            <Findings findings={builder.findings} onSelect={setSelected} />
          )}

          {panel === "step" && data && swapping && (
            <Swap
              step={data.steps.find((one: any) => one.id === swapping)!}
              graph={builder.graph}
              onClose={() => setSwapping(null)}
              onApply={(contractId: string) => {
                builder.replaceContract(swapping, contractId);
                setSwapping(null);
              }}
            />
          )}
          {panel === "step" && data && !swapping && (
            <StepChoice
              step={answered.find((one) => one.id === selected)}
              onSwap={setSwapping}
              onOpenSettings={setCarded}
            />
          )}
        </div>
      </Side>
      </div>

      {/* **A modal, opened from the node's own button** — `dashboard.md` §5. The rail's Step tab
          shows the same card for the selected step; this is the path from the canvas, which is
          where a person is when they wonder what a step is set to. */}
      {menu && (
        <>
          {/* A full-screen catcher, so any click anywhere dismisses — including a right-click
              somewhere else, which would otherwise open a second menu behind the first. */}
          <div
            data-testid="menu-catcher"
            className="fixed inset-0 z-40"
            onClick={() => setMenu(null)}
            onContextMenu={(e) => {
              e.preventDefault();
              setMenu(null);
            }}
          />
          <div
            data-testid="node-menu"
            style={{ left: menu.x, top: menu.y }}
            className="fixed z-50 min-w-[160px] rounded-r border border-line bg-surface py-1
                       shadow-e3"
          >
            <button
              data-testid="menu-settings"
              onClick={() => {
                setCarded(menu.node);
                setMenu(null);
              }}
              className="w-full text-left px-3 py-1.5 text-body bg-transparent border-0
                         cursor-pointer hover:bg-[var(--hover)]"
            >
              Settings…
            </button>
            <button
              data-testid="menu-delete"
              onClick={() => {
                builder.removeNode(menu.node);
                if (selected === menu.node) setSelected(null);
                setMenu(null);
              }}
              className="w-full text-left px-3 py-1.5 text-body bg-transparent border-0
                         cursor-pointer hover:bg-[var(--hover)] text-[var(--undecided)]"
            >
              Delete step
            </button>
          </div>
        </>
      )}

      {sheet && (
        <RunSheet
          name={draft.name || "this pipeline"}
          steps={answered}
          sources={data ? entryChannels(data) : []}
          draftId={keeper.draftId}
          blocked={keeper.blocked}
          gated={gate.passed && !keeper.blocked}
          onClose={() => setSheet(false)}
          onOpenSettings={(id: string) => {
            setSheet(false);
            setSelected(id);
            setCarded(id);
          }}
        />
      )}

      {browsing && (
        <Browse
          onClose={() => setBrowsing(false)}
          onAdd={(contractId: string) => { builder.addAt(contractId); setBrowsing(false); }}
        />
      )}

      {picking && (
        <Picker
          port={picking.port}
          node={picking.node}
          at={picking.at}
          onClose={() => setPicking(null)}
          onPick={(contractId: string, theirPort: string) => {
            // **Add the step AND draw the wire.** Adding from a port is the whole point — and
            // it is also what fixes placement by construction, because the new node has a place
            // to go rather than a guessed grid cell.
            const id = builder.addAt(contractId);
            if (id) {
              // The direction is the CLICKED port's, not the gesture's. An output feeds the new
              // node; an input is fed by it. Getting this backwards would draw an MD0502 wire —
              // which `validate` would report, correctly, about a graph the canvas built wrong.
              if (picking.port.side === "out") {
                builder.connect(picking.node, picking.port.name, id, theirPort);
              } else {
                builder.connect(id, theirPort, picking.node, picking.port.name);
              }
            }
            setPicking(null);
          }}
        />
      )}

      {/* **A card ON the node, not a modal over the page** — `n-bsettings`.
          *SETTINGS — a card on the node, opened from the ... in its header. Not a giant list.*

          It shipped as a centred dialog with a dimming backdrop, which is a different claim:
          a modal says *stop what you are doing*, and a card beside the step says *here is what
          this one is set to*. The whole reason the settings moved off the rail was to put them
          next to the thing they describe, and a backdrop that hides the canvas undoes that.

          The anchor is the **picker's transform, written the same way round** — `translate`
          then `scale`, applied forward from canvas space. Recomputed on render rather than
          frozen on open, so the card travels with its node when you pan.

          **`settle`, not the artboard's `pop`.** `BuilderSettings.dc.html` defines a sixth
          keyframe for this one card; `mo-page-1` says five movements and nothing else moves,
          and `settle` is already opacity plus a 4px rise. A sixth easing for one popover is how
          a house style becomes a collection. */}
      {carded && data && (
        <div
          role="dialog"
          data-testid="settings-anchored"
          aria-label={`settings for ${answered.find((s) => s.id === carded)?.process ?? carded}`}
          style={(() => {
            const a = onScreen(
              { x: (offsets[carded]?.x ?? 0) + NODE_W + 16, y: offsets[carded]?.y ?? 0 },
              view,
            );
            return { left: a.x, top: a.y };
          })()}
          onClick={(e) => e.stopPropagation()}
          className="settle fixed z-40 w-[352px] max-h-[70vh] overflow-auto border border-line-2
                     bg-[var(--paper-2)] shadow-e3"
        >
          <Settings
            step={answered.find((s) => s.id === carded)!}
            onClose={() => setCarded(null)}
            onSet={(name, value) => builder.setParam(carded, name, value)}
          />
        </div>
      )}
    </div>
  );
}

const zoomBtn =
  "px-2 py-1 rounded-r bg-transparent border-0 cursor-pointer text-secondary text-ink-2 " +
  "hover:text-ink hover:bg-surface-2";
