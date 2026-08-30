import { useEffect, useMemo, useRef, useState } from "react";

import type { components } from "../api/schema";
import { useTitle } from "../app/useTitle";
import { Failed, Loading } from "../ui/States";
import { Canvas } from "./Canvas";
import { Node } from "./Node";
import { LeftPanel } from "./LeftPanel";
import { Settings } from "./Settings";
import { Grip, RAIL, useWidth } from "./Panels";
import { Provenance } from "./Provenance";
import { Compare } from "./Compare";
import { GatePanel } from "./Gate";
import { SubmitPanel } from "./Submit";
import { Findings } from "./Findings";
import { useGate } from "./useGate";
import { useKeep } from "./useKeep";
import { Walk } from "./Walk";
import { heightFor, portX } from "./geometry";
import { MODULE_DND } from "./Modules";
import { Rail } from "./Rail";
import { Wires } from "./Wires";
import { graphOf, useBuilder, useExample, withTypedValues } from "./useBuilder";
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
  children,
}: {
  side: "left" | "right";
  title: string;
  width: number;
  collapsed: boolean;
  onExpand: () => void;
  badge?: number;
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
        className="shrink-0 flex flex-col items-center gap-3 py-4 bg-surface cursor-pointer
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
      className="shrink-0 flex flex-col bg-surface overflow-hidden"
    >
      <div className="flex items-baseline gap-3 px-4 py-3 border-b border-line">
        <span className={label}>{title}</span>
        {badge !== undefined && badge > 0 && (
          <span className="ml-auto font-data text-secondary text-[var(--undecided)]">{badge}</span>
        )}
      </div>
      <div className="flex-1 overflow-auto">{children}</div>
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
  const left = useWidth(232, 190, 430);
  const right = useWidth(320, 280, 560);
  const { view, onWheel, onPointerDown, reset, nudge, fit } = useView();
  const box = useRef<HTMLDivElement>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [isolated, setIsolated] = useState<string | null>(null);
  const [carded, setCarded] = useState<string | null>(null);
  /** Which output port a wire is being dragged from. `null` most of the time. */
  const [dragging, setDragging] = useState<{ node: string; port: string } | null>(null);

  const example = useExample();
  return example.data ? (
    <Editing built={example.data} view={view} onWheel={onWheel} onPointerDown={onPointerDown}
      reset={reset} nudge={nudge} fit={fit} box={box} left={left} right={right}
      selected={selected} setSelected={setSelected} isolated={isolated} setIsolated={setIsolated}
      carded={carded} setCarded={setCarded} dragging={dragging} setDragging={setDragging} />
  ) : (
    <div className="grid place-items-center h-full">
      {example.isLoading && <Loading what="the pipeline" />}
      {example.error && <Failed error={example.error} />}
    </div>
  );
}

/* eslint-disable @typescript-eslint/no-explicit-any */
/** The screen, once there is something to edit.
 *
 * Split from `Builder` because `useBuilder` needs a starting graph and hooks cannot wait for a
 * query. The alternative — a hook that tolerates `undefined` — would put "is there a pipeline
 * yet" into every line below.
 */
const GOAL = {
  have: [
    { type_id: "fastq.reads", states: [] },
    { type_id: "annotation.gtf", states: [] },
    { type_id: "genome.fasta", states: [] },
  ],
  want: ["counts.matrix"],
};

function Editing({ built, view, onWheel, onPointerDown, reset, nudge, fit, box, left, right,
  selected, setSelected, isolated, setIsolated, carded, setCarded, dragging, setDragging }: any) {
  // **Node offsets live in `useGraph`, not in each node.** They were local state, which meant a
  // dragged node left its wires behind — the graph broke the moment you touched it.
  const builder = useBuilder(graphOf(built));
  const index = useCompatibility();
  const data: Built | null = builder.drawn;
  const offsets = builder.offsets;
  const isLoading = data === null;
  const error = builder.drawnError;
  const [panel, setPanel] = useState<"review" | "problems" | "compare" | "gate" | "run">(
    "review",
  );
  // **The draft lifecycle, finally connected.** 3E built create/save/keep on the server and
  // wired none of it; a gate needs an artifact on disk, which is what surfaced that.
  const keeper = useKeep(builder.graph);
  // **Read here, not inside the panel.** `useGate` shares its state through the query cache,
  // so this is the same gate the toolbar button and the gate tab are looking at — which is
  // what makes "a gate passed" mean the one a person just watched.
  const gate = useGate(keeper.draftId);
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
  const [kept, setKept] = useState<{ row: any; reason: string }[]>([]);
  void kept;

  const blocking = data?.needs_review.length ?? 0;

  return (
    <div className="grid grid-rows-[38px_1fr] h-full overflow-hidden">
      <div className="flex items-center gap-4 px-6 border-b border-line bg-surface">
        <span className="text-label uppercase tracking-[.13em] font-semibold text-ink-3">
          RNA-seq spine
        </span>
        {/* **Keep, Gate and Run left this toolbar for `Walk`** — W2 §13. They were three
            controls in three places for one sequence, and the rail is that sequence said
            once. `execution-boundary.md` §3's rule that a gate and a run must never share a
            label is kept there rather than here. */}
        {blocking > 0 && (
          <span data-testid="blocking" className="text-secondary text-[var(--undecided)]">
            <b className="font-data">{blocking}</b> to decide
          </span>
        )}
      </div>
      <div
        ref={box}
        data-testid="builder"
        className="grid grid-cols-[auto_5px_1fr_5px_auto] overflow-hidden"
      >
      <Side
        side="left"
        title="Modules"
        width={left.width}
        collapsed={left.collapsed}
        onExpand={() => left.setCollapsed(false)}
      >
        {data && (
          <LeftPanel
            data={data}
            selected={selected}
            onSelect={setSelected}
            onAdd={builder.addNode}
          />
        )}
      </Side>
      <Grip
        side="left"
        onPointerDown={(e) => left.onPointerDown(e, "left")}
        onCollapse={() => left.setCollapsed(true)}
        onNudge={() => {}}
      />

      <div className="flex flex-col overflow-hidden">
        {data && (
          <Provenance data={data} isolated={isolated} onIsolate={setIsolated} />
        )}
        <Canvas
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
        onDragOver={(e: React.DragEvent) => {
          if (e.dataTransfer.types.includes(MODULE_DND)) e.preventDefault();
        }}
        onDrop={(e: React.DragEvent) => {
          const contractId = e.dataTransfer.getData(MODULE_DND);
          if (contractId) {
            e.preventDefault();
            builder.addNode(contractId);
          }
        }}
        footer={
          <div
            data-zoomer
            className="absolute right-4 bottom-4 flex items-center gap-1 rounded-r
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
            <button
              aria-label="fit the pipeline"
              className={zoomBtn}
              onClick={() => {
                const r = box.current?.getBoundingClientRect();
                if (data && r) fit(data.layout.width, data.layout.height, r.width, r.height);
              }}
            >
              fit
            </button>
          </div>
        }
      >
        {isLoading && <Loading what="the pipeline" />}
        {error && <Failed error={error} />}
        {data && (
          <>
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
              tierOf={(id) => data.layout.nodes.find((n) => n.id === id)?.tier ?? 2}
              at={offsets}
              ports={portIndex}
              width={data.layout.width}
              height={data.layout.height}
              pending={
                dragging && cursor && portIndex[dragging.node]
                  ? {
                      from: {
                        x:
                          (offsets[dragging.node]?.x ?? 0) +
                          portX(
                            portIndex[dragging.node].width,
                            portIndex[dragging.node].outs.length,
                            Math.max(0, portIndex[dragging.node].outs.indexOf(dragging.port)),
                          ),
                        y:
                          (offsets[dragging.node]?.y ?? 0) +
                          heightFor(
                            portIndex[dragging.node].ins.length,
                            portIndex[dragging.node].outs.length,
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
                step={data.steps.find((s) => s.id === placed.id)}
                zoom={view.k}
                dim={isolated !== null && String(placed.tier) !== isolated}
                selected={selected === placed.id}
                onSelect={() => setSelected(placed.id)}
                onContextMenu={(e: React.MouseEvent) => {
                  e.preventDefault();
                  setSelected(placed.id);
                  setMenu({ node: placed.id, x: e.clientX, y: e.clientY });
                }}
                onOpenSettings={() => setCarded(placed.id)}
                offset={offsets[placed.id] ?? { x: 0, y: 0 }}
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
      >
        {/* **Three tabs, and the order is the order you need them in.** What is wrong with
            what you drew comes before what Mendel would have done differently, because a graph
            that cannot be emitted is not yet worth diffing. */}
        {/* Draw → Keep → Gate → Run, above the tabs, because it is the sequence and they are
            the detail. **The only place that leaves Mendel** is its last step — A179,
            `wiener.md` §12 — and it stays a distinct step rather than a second gate button,
            because `execution-boundary.md` §3 keeps those two words apart everywhere else. */}
        <div className="p-2">
          <Walk
            draw={{ steps: builder.graph.nodes?.length ?? 0,
                    problems: builder.findings.length }}
            keep={{
              // `keptAt` is a **time**, and the rail prints `kept ${keptAt}` — the literal
              // "kept" here rendered `kept kept` on screen. A draft id also is not the same
              // fact: a draft is *saved* from the first edit and only `keep` certifies it.
              keptAt: keeper.keptAt,
              stale: keeper.blocked,
              busy: keeper.keeping,
              onKeep: () => keeper.keep(),
              // **THE SILENT 500.** On 2026-08-29 this call sent `keep` and dropped its error:
              // the API answered 500, the rail sat there still offering *Keep*, and `docker
              // logs` was the only way to find out. `useKeep` had returned `error` all along,
              // documented as "Shown, not swallowed" — nothing read it. Keep has no panel, so
              // this step is the surface.
              error: keeper.error,
            }}
            gate={{
              passed: gate.passed && !keeper.blocked,
              blocked: keeper.blocked ? "A gate has to pass on the version you kept." : null,
              // **Reported by the panel, not here** — `GatePanel` renders `gate.error` under
              // its own `gate-error`, with the tool output beside it. Filling the slot too
              // would print the same refusal twice, one line apart, which is the duplicated
              // control the same walk found on *Send to Wiener* wearing different clothes.
              error: null,
              panel: <GatePanel draftId={keeper.draftId} blocked={keeper.blocked} />,
            }}
            run={{
              sent: false,
              blocked: gate.passed ? null : "A gate has to pass on the version you kept.",
              // Reported by the panel, as above: `SubmitPanel` renders `submit.error`, and
              // hands an `Unauthorized` to `TokenPrompt` rather than printing it — which is a
              // better answer than any message, and one this step could not give.
              error: null,
              panel: <SubmitPanel draftId={keeper.draftId}
                                  gated={gate.passed && !keeper.blocked} />,
            }}
          />
        </div>

        <div className="flex gap-1 border-b border-line px-2 pt-2">
          {(["review", "problems", "compare"] as const).map((t) => (
            <button
              key={t}
              data-testid={`tab-${t}`}
              data-active={panel === t}
              onClick={() => setPanel(t)}
              className={`px-2 py-1 text-label uppercase tracking-[.1em] font-semibold rounded-t
                          ${panel === t ? "text-ink border-b-2 border-pea" : "text-ink-3"}`}
            >
              {t}
              {t === "problems" && builder.findings.length > 0 && (
                <span className="ml-1 font-data text-[var(--undecided)]">
                  {builder.findings.length}
                </span>
              )}
            </button>
          ))}
        </div>

        {panel === "problems" && (
          <Findings findings={builder.findings} onSelect={setSelected} />
        )}


        {panel === "compare" && (
          <>
            <div className="p-3 pb-0">
              <button
                data-testid="run-compare"
                disabled={builder.comparing}
                onClick={() => void builder.compare(GOAL)}
                className="px-3 py-1 rounded-r border-0 bg-pea text-[var(--on-pea)] text-body
                           font-semibold disabled:opacity-40"
              >
                {builder.comparing ? "Resolving…" : "Compare with Mendel"}
              </button>
            </div>
            <Compare
              alignment={builder.alignment}
              onAdopt={builder.adopt}
              onKeep={(row, reason) => {
                // **Keeping yours is an override and needs a reason** — the defect A77 was.
                // Recording it against the artifact waits on the keep/override endpoint;
                // until then the reason is held with the row rather than silently dropped.
                setKept((all) => [...all, { row, reason }]);
              }}
            />
          </>
        )}
        {panel === "review" && data && (
          <Rail
            data={data}
            selected={selected}
            onSelect={setSelected}
            onCollapse={() => right.setCollapsed(true)}
          />
        )}
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

      {carded && data && (
        <div
          className="fixed inset-0 z-40 flex items-start justify-center pt-[10vh] px-6
                     bg-[color-mix(in_srgb,var(--ink)_35%,transparent)]"
          onClick={() => setCarded(null)}
        >
          <div
            role="dialog"
            aria-modal="true"
            onClick={(e) => e.stopPropagation()}
            className="w-full max-w-[560px] max-h-[70vh] overflow-auto rounded-r border
                       border-line bg-surface shadow-e3"
          >
            <Settings
              step={withTypedValues(data.steps.find((s) => s.id === carded)!, builder.graph)}
              onClose={() => setCarded(null)}
              onSet={(name, value) => builder.setParam(carded, name, value)}
            />
          </div>
        </div>
      )}
    </div>
  );
}

const zoomBtn =
  "px-2 py-1 rounded-r bg-transparent border-0 cursor-pointer text-secondary text-ink-2 " +
  "hover:text-ink hover:bg-surface-2";
