import { Fragment, useEffect, useRef, useState } from "react";

import type { components } from "../../api/schema";
import type { DraftEdge, DraftGraph, PortView, Step } from "../../api/types";
import { Canvas } from "../Canvas";
import { elbow, MEASURE_W, NODE_W, path, portOffset, type Point, type Positions } from "../geometry";
import { idFor, withEdge, withNode, withoutEdge, withoutNode } from "../graphOps";
import { Minimap } from "../Minimap";
import { Picker } from "../Picker";
import { Port } from "../Port";
import { place } from "../Sources";
import { accepts, useCompatibility } from "../useCompatibility";
import { useView } from "../useView";
import { chipName, Flowline, flowLabel, ResultNode, SOURCE_H, SOURCE_W, SourceNode, type Flow } from "./CollectionChannel";
import { useTypeNames } from "./useTypeNames";
import { valuesOf } from "./values";
import type { Author } from "./format";
import { anchorOf, cardHeight, foldedInputs, LivingNode, OUT_W, shownPorts, type ReviewState, type StepProgress } from "./LivingNode";
import { StepMenu } from "./StepMenu";

type Channel = components["schemas"]["ChannelView"];
type Rule = components["schemas"]["InputRule"];

/** The pipeline as it stands, and how its data moves.
 *
 * **Draws; decides nothing.** Positions are the blueprint's `dag-core` layout, so a step appears
 * where it will stay; a hand-added step takes the drawn layout's. How many times each part runs is
 * the server's (`ChannelView.grain`, `PortView.gathers`, `StepView.runs`) — this only chooses a
 * stroke for it. Inputs are placed by `Sources.place`, the rule the existing canvas uses.
 *
 * **The client owns a position once somebody drags it**, and **Tidy** gives the server's layout
 * back — the escape hatch the manual builder has always had.
 *
 * **The manual builder's hands, when `onEdit` is given** (one builder, #395): Delete removes the
 * selected step, an output drags a wire to an input, a wire detaches on a click, and a port asks
 * what could go there (`Picker`). Each sends the whole next graph, which the server reads as
 * intent and the chat confirms; nothing here saves anything.
 */
const CONTROL = "px-[14px] py-[6px] rounded-button border border-line-2 bg-surface text-[13px] font-semibold "
  + "text-ink cursor-pointer hover:bg-[var(--hover)] focus-visible:shadow-[var(--ring)]";

/** What the canvas's colours mean, as the boards' legend says it. */
const LEGEND: [string, string][] = [
  ["settled", "var(--line-2)"], ["measured", "var(--measured)"], ["needs you", "var(--needs-you)"],
];
/** On Run, what a step's colour says about how far it has got. */
const RUN_LEGEND: [string, string][] = [
  ["done", "var(--done)"], ["running", "var(--now)"], ["waiting", "var(--line-2)"], ["failed", "var(--needs-you)"],
];

/** How far a shared input runs as one line before its branches split off. */
const TRUNK = 72;

export function LivingCanvas({
  graph,
  positions,
  steps,
  channels = [],
  authors,
  selected,
  onSelect,
  footer,
  readOnly = false,
  stale = false,
  reviews = {},
  aiChosen = [],
  working = false,
  focus = null,
  onEdit,
  shown,
  onMenu,
  beside = null,
  samples,
  onAddHere,
  connect = null,
  onConnected,
  progress,
  fitOnOpen = false,
  given = {},
  showTool = true,
  showPorts = true,
  onTidy,
  lit = null,
}: {
  graph: DraftGraph;
  positions: Positions;
  steps: Record<string, Step>;
  channels?: Channel[];
  authors: Record<string, Author>;
  selected: string | null;
  onSelect: (node: string | null) => void;
  footer?: React.ReactNode;
  /** A complete preview: nothing here can be moved, selected or changed. */
  readOnly?: boolean;
  /** The frame is the last pipeline built, and answers have changed since: said, never hidden. */
  stale?: boolean;
  /** Whether each drawn step's review still holds — said in words, never by repainting its tier. */
  reviews?: Record<string, ReviewState>;
  /** Steps where the AI chose something nobody has reviewed yet (#463). */
  aiChosen?: string[];
  /** A decision is on its way: the last complete frame stays, marked as being updated. */
  working?: boolean;
  /** The step the engine or the person is looking at — brought on screen when it changes. */
  focus?: string | null;
  /** A hand edit, as the whole next graph. Absent where the canvas is a preview. */
  onEdit?: (next: DraftGraph) => void;
  /** Changes when the page shows the canvas again (a phone's tab); the canvas fits itself then. */
  shown?: string;
  /** Open a step's menu (#499): a right-click, a long press, `⋯`, or the keyboard. */
  onMenu?: (node: string) => void;
  /** What opens beside a step — its menu or its card (#499) — placed next to it on screen, so it
   *  moves with pan and zoom without scaling; on a phone a sheet from the bottom (`.step-beside`). */
  beside?: { node: string; content: React.ReactNode } | null;
  /** The analysis's kept samples, for ×N and *all N*. */
  samples?: number;
  /** Right-click on the empty canvas: *Add step here*, with where on the drawing it goes. */
  onAddHere?: (at: Point) => void;
  /** Open the port picker on this step's input (Connect, from the Step tab). */
  connect?: { node: string; port: string } | null;
  onConnected?: () => void;
  /** **On Run**: each step's progress in the run, drawn on its node in place of its values. */
  progress?: Record<string, StepProgress>;
  /** Fit the drawing to the frame when it first has steps (Run's panels, which open small). */
  fitOnOpen?: boolean;
  /** What Data answers each input type with (a reference's file name), for its chip. */
  given?: Record<string, string>;
  /** The rail's *On the steps*: each step's tool and version, and its port names. */
  showTool?: boolean;
  showPorts?: boolean;
  /** **Tidy**: the server lays the drawing out again with the current geometry. */
  onTidy?: () => void;
  /** **A path lit** (Run → Outputs): these steps, and the wires between them, stay as drawn; the
   *  rest fade, so a file's way through the pipeline reads at a glance. `null` lights everything. */
  lit?: string[] | null;
}) {
  const [here, setHere] = useState<{ x: number; y: number } | null>(null);
  /** The step under the pointer, whose details show beside it. */
  const [hovered, setHovered] = useState<string | null>(null);
  const hoverTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const hover = (id: string, on: boolean) => {
    if (hoverTimer.current) clearTimeout(hoverTimer.current);
    hoverTimer.current = setTimeout(() => setHovered(on ? id : null), on ? 250 : 80);
  };
  const view = useView();
  const probe = useRef<HTMLSpanElement>(null);
  const [moved, setMoved] = useState<Positions>({});
  const drag = useRef<{ id: string; from: Point; origin: Point; travelled: boolean } | null>(null);
  const press = useRef<ReturnType<typeof setTimeout> | null>(null);
  /** Which output a wire is being dragged from. */
  const [wiring, setWiring] = useState<{ node: string; port: string } | null>(null);
  /** The port whose candidates are open, and where on screen. */
  const [picking, setPicking] = useState<{ node: string; port: PortView; at: Point } | null>(null);
  const index = useCompatibility();
  const editable = onEdit !== undefined && !readOnly;
  useEffect(() => {
    if (!connect) return;
    const port = steps[connect.node]?.ports.find((p) => p.side === "in" && p.name === connect.port);
    const where = positions[connect.node];
    if (port && where) setPicking({ node: connect.node, port, at: onScreen({ x: where.x - 356, y: where.y }) });
    onConnected?.();
  }, [connect, steps, positions, onConnected]); // eslint-disable-line react-hooks/exhaustive-deps

  /** **Delete removes the selected step**, not while a field has focus — typing a value into a
   *  setting would delete the step being configured. */
  useEffect(() => {
    if (!editable || !selected) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Delete" && e.key !== "Backspace") return;
      const target = e.target as HTMLElement | null;
      if (target && (["INPUT", "SELECT", "TEXTAREA"].includes(target.tagName) || target.isContentEditable)) {
        return;
      }
      e.preventDefault();
      onEdit(withoutNode(graph, selected));
      onSelect(null);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [editable, selected, graph, onEdit, onSelect]);

  /** **A wire drag ends wherever the pointer is let go**, or the next click on an input would
   *  finish a wire abandoned a minute ago. */
  useEffect(() => {
    if (!wiring) return;
    const done = () => setWiring(null);
    window.addEventListener("pointerup", done);
    return () => window.removeEventListener("pointerup", done);
  }, [wiring]);

  const at: Positions = { ...positions, ...moved };
  const typeName = useTypeNames();
  const measuring = (id: string) => !!(steps[id] as { measures?: boolean } | undefined)?.measures;
  /** The value a measurement set at this step, for its card's row: `sa_index_nbases 8`, or
   *  *in the run* when the run measures it. */
  const setRowOf = (id: string): string | undefined => {
    const settings = steps[id]?.settings ?? [];
    const measured = settings.find((x) => x.tier === 3 && x.evidence === "measured" && x.value != null);
    if (measured) return `${measured.name} ${String(measured.value)}`;
    const atRun = settings.find((x) => x.at_run);
    return atRun ? `${atRun.name} · set in the run` : undefined;
  };
  /** A step's drawn height: its ports (#494), its measured value's row, Run's progress row. */
  const tall = (id: string) => cardHeight(steps[id]?.ports ?? [],
    { measures: measuring(id), setRow: !!setRowOf(id), progress: !!progress?.[id],
      more: foldedInputs(steps[id]?.ports ?? []) > 0 });
  /** The tool's rules this step breaks, in a few words for its card's tags. */
  const brokenOf = (id: string): string[] => ((steps[id] as { rules?: Rule[] } | undefined)?.rules ?? [])
    .filter((r) => r.broken)
    .map((r) => r.kind === "requires" ? `needs ${r.names.join(", ")}`
      : r.kind === "forbids" ? `not with ${r.names.join(", ")}`
      : r.kind === "one_of" ? "pick one input" : r.kind === "any_of" ? "needs one input" : "both or neither");
  const widthOf = (id: string) => (measuring(id) ? MEASURE_W : NODE_W);

  // **The canvas follows the engine**: when the step in focus changes, or the server places it,
  // it is brought on screen. Read from the server's placement, not a drag's, so moving a step by
  // hand never pans the canvas under the pointer.
  const target = focus ? positions[focus] : undefined;
  const bringIntoView = view.reveal;
  useEffect(() => {
    const frame = probe.current?.closest<HTMLElement>("[data-testid='canvas']");
    if (!target || !frame) return;
    const rect = frame.getBoundingClientRect();
    bringIntoView({ x: target.x, y: target.y, w: NODE_W, h: tall(focus!) }, { w: rect.width, h: rect.height });
    // eslint-disable-next-line react-hooks/exhaustive-deps -- a step moves by its coordinates, not its object
  }, [focus, target?.x, target?.y, bringIntoView]);
  const ids = [...new Set(graph.nodes.map((n) => n.id))];
  const visible = new Set(ids);
  /** A measuring pill hung under the step it reads (#517) needs no wire: being under it says so. */
  const hung = (e: DraftEdge) => !!(steps[e.to_node] as { measures?: boolean } | undefined)?.measures
    && at[e.to_node] !== undefined && at[e.to_node]?.x === at[e.from_node]?.x;
  /** Each hung pill and the step it hangs under, joined by a short connector instead of a wire. */
  const hangers = graph.edges.filter((e) => hung(e));
  const solid = graph.edges.filter((e) => !hung(e));
  /** **A fact one step measures for another** (walk 2026-11-15): genome length, measured in the
   *  run, sets STAR's index size. It travels on the samples' metadata, not a port, so no wire
   *  shows it; a dotted line does, labelled with the fact and the setting it decides. */
  const byContract = new Map(ids.map((id) => [steps[id]?.contract_id, id] as const));
  const factLinks = ids.flatMap((to) => (steps[to]?.settings ?? []).flatMap((setting) =>
    (setting.at_run?.facts ?? []).flatMap((fact) => {
      const from = fact.measured_by ? byContract.get(fact.measured_by) : undefined;
      return from && from !== to ? [{ from, to, label: `${fact.fact} → ${setting.name}` }] : [];
    })));

  const count = channels.find((c) => c.grain === "sample")?.count ?? null;
  /** The ports a card draws — the ones its wires reach — in the card's own order. */
  const portsOf = (node: string, side: "in" | "out") =>
    shownPorts(steps[node]?.ports ?? []).filter((p) => p.side === side);
  const tipIn = (node: string, port: string): Point | null => {
    const box = at[node];
    if (!box) return null;
    const index = portsOf(node, "in").findIndex((p) => p.name === port);
    return { x: box.x, y: box.y + anchorOf(measuring(node), Math.max(0, index)) };
  };
  const tipOut = (node: string, port: string): Point | null => {
    const box = at[node];
    if (!box) return null;
    const index = portsOf(node, "out").findIndex((p) => p.name === port);
    // From the output triangle's tip (`OUT_W - 1` past the edge), where the arrow points.
    return { x: box.x + widthOf(node) + OUT_W - 1, y: box.y + anchorOf(measuring(node), Math.max(0, index)) };
  };
  const gathers = (node: string, port: string) =>
    portsOf(node, "in").some((p) => p.name === port && p.gathers);

  /** One stroke, a ribbon, or a converging ribbon — from server facts, never from a type name. */
  const flowOf = (edge: DraftEdge): Flow =>
    gathers(edge.to_node, edge.to_port) ? "gather"
      : steps[edge.from_node]?.runs === "per_item" ? "many" : "one";

  // ── inputs, placed where they enter ────────────────────────────────────────────────────
  /** Whether the gutter to the left of a node is empty — `place`'s own reason for a left-hand
   *  socket is that *it overlaps nothing*, so that is what is asked. **Not "is this the leftmost
   *  column"**: the first render put both sources of the collection board below their consumers
   *  and on top of the next node, because their column was not the leftmost although its gutter
   *  was empty. */
  const gutterClear = (anchor: Point, index: number) => {
    const box = place("Input", anchor, index, true, { w: SOURCE_W, h: SOURCE_H }).box;
    return ids.every((id) => {
      const other = at[id];
      if (!other || other === anchor) return true;
      return (
        box.x + SOURCE_W <= other.x || other.x + NODE_W <= box.x ||
        box.y + SOURCE_H <= other.y || other.y + tall(id) <= box.y
      );
    });
  };
  const perNode = new Map<string, number>();
  const sources = channels.flatMap((channel) => {
    const feeds = channel.ports.map((key) => key.split(".")).filter(([node]) => visible.has(node));
    if (feeds.length === 0 || !at[feeds[0][0]]) return [];
    const anchor = at[feeds[0][0]];
    const index = perNode.get(feeds[0][0]) ?? 0;
    perNode.set(feeds[0][0], index + 1);
    const geometry = place("Input", anchor, index, gutterClear(anchor, index), { w: SOURCE_W, h: SOURCE_H },
                           tall(feeds[0][0]));
    return [{ channel, box: geometry.box, edge: geometry.edge, feeds }];
  });

  /** **Results**: a chip after each step nothing else reads (not a measuring step), named for what
   *  it makes, with how many — or, on Run, how far it has got. */
  const read = new Set(graph.edges.map((e) => e.from_node));
  const results = ids.filter((id) => at[id] && !read.has(id) && !measuring(id) && portsOf(id, "out").length > 0)
    .map((id) => {
      const out = portsOf(id, "out")[0];
      const perItem = steps[id]?.runs === "per_item";
      return {
        id,
        at: { x: at[id].x + NODE_W + 48, y: at[id].y + portOffset(0) - SOURCE_H / 2 },
        name: chipName(typeName(out.type_id)),
        detail: progress?.[id]?.label ?? (perItem && samples ? `${samples} files` : "1 file"),
      };
    });

  const drawn = ids.length;
  /** Fit the whole drawing, inputs included, in the frame the probe sits in. */
  const fitView = () => {
    const frame = probe.current?.closest<HTMLElement>("[data-testid='canvas']");
    if (!frame) return;
    const xs = [...ids.map((id) => at[id]?.x ?? 0), ...sources.map((s) => s.box.x)];
    const ys = [...ids.map((id) => at[id]?.y ?? 0), ...sources.map((s) => s.box.y)];
    const left = Math.min(...xs), top = Math.min(...ys);
    const right = Math.max(...ids.map((id) => (at[id]?.x ?? 0) + NODE_W), ...results.map((r) => r.at.x + SOURCE_W));
    const bottom = Math.max(...ids.map((id) => (at[id]?.y ?? 0) + tall(id)), ...sources.map((s) => s.box.y + SOURCE_H));
    const rect = frame.getBoundingClientRect();
    view.fit(right - left, bottom - top, rect.width, rect.height - 96, { x: left, y: top - 40 });
  };
  // **Fitted again when it is shown again** (issue 496): on a phone the canvas is a tab, laid out
  // while hidden, and opened cut off. The page says when it is shown (`shown`); a person who has
  // panned or zoomed keeps their view. Following the engine still only pans.
  const touched = useRef(false);
  const fitLatest = useRef(fitView);
  fitLatest.current = fitView;
  const firstShown = useRef(shown);
  useEffect(() => {
    if (shown === firstShown.current || touched.current) return;
    fitLatest.current();
  }, [shown]);
  // **Fitted as the agent builds** (walk 2026-11-16): a pipeline that grows on a canvas nobody
  // has moved is fitted each time its step count changes; a person's own view is kept.
  const lastDrawn = useRef(drawn);
  useEffect(() => {
    if (drawn === lastDrawn.current) return;
    lastDrawn.current = drawn;
    if (drawn === 0 || touched.current) return;
    requestAnimationFrame(() => fitLatest.current());
  }, [drawn]);
  const opened = useRef(false);
  useEffect(() => {
    if (!fitOnOpen || opened.current || drawn === 0) return;
    opened.current = true;
    requestAnimationFrame(() => fitLatest.current());
  }, [fitOnOpen, drawn]);
  // **Tidy fits the drawing** once the server's new layout is drawn.
  const placedKey = JSON.stringify(positions);
  const fitWhenPlaced = useRef(false);
  useEffect(() => {
    if (!fitWhenPlaced.current) return;
    fitWhenPlaced.current = false;
    requestAnimationFrame(() => fitLatest.current());
  }, [placedKey]);
  // **Tidy fits the drawing** once the server's layout is back, the next frame.
  const tidied = useRef(false);
  useEffect(() => {
    if (!tidied.current || Object.keys(moved).length > 0) return;
    tidied.current = false;
    fitLatest.current();
  }, [moved]);
  const moving = (e: React.SyntheticEvent) => {
    if (!(e.target as HTMLElement).closest("[data-node]")) touched.current = true;
  };
  const width = Math.max(0, ...ids.map((id) => (at[id]?.x ?? 0) + NODE_W + 80), ...results.map((r) => r.at.x + SOURCE_W + 20));
  const height = Math.max(
    0,
    ...ids.map((id) => (at[id]?.y ?? 0) + tall(id) + 88),
    ...sources.map((s) => s.box.y + SOURCE_H + 20),
  );

  /** How an input looks while a wire is dragged: **a lookup, not a decision** — the server
   *  computed what satisfies what, and reads the edit when it lands. */
  const verdictFor = (node: string, port: string) => {
    if (!wiring || !index.data) return undefined;
    const from = graph.nodes.find((n) => n.id === wiring.node)?.contract_id;
    const to = graph.nodes.find((n) => n.id === node)?.contract_id;
    return from && to ? accepts(index.data, `${from}#${wiring.port}`, `${to}#${port}`) : undefined;
  };
  /** Canvas coordinates on the screen, for the picker, which is drawn fixed. */
  const onScreen = (p: Point): Point => {
    const r = probe.current?.closest<HTMLElement>("[data-testid='canvas']")?.getBoundingClientRect();
    return { x: (r?.left ?? 0) + p.x * view.view.k + view.view.x, y: (r?.top ?? 0) + p.y * view.view.k + view.view.y };
  };

  // **After every hook**: the canvas starts empty and fills while mounted, so returning early
  // above a hook changed their order on the first step (#463).
  if (ids.length === 0) {
    return (
      <div className="relative flex-1 min-h-0 flex flex-col items-center justify-center" data-testid="canvas-empty">
        {footer}
      </div>
    );
  }

  return (
    <Canvas
      view={view.view}
      onWheel={(e) => {
        // A wheel over a step's menu or card scrolls it; it never zooms the canvas under it.
        if ((e.target as HTMLElement).closest(".step-beside")) return;
        touched.current = true; view.onWheel(e);
      }}
      onPointerDown={(e) => {
        // A pointer inside the step's menu or card is not a pan of the canvas.
        if ((e.target as HTMLElement).closest(".step-beside")) return;
        moving(e); view.onPointerDown(e);
      }}
      dots
      onContextMenu={onAddHere && !readOnly ? (e) => {
        if ((e.target as HTMLElement).closest("[data-node], .step-beside")) return;
        e.preventDefault();
        const box = (e.currentTarget as HTMLElement).getBoundingClientRect();
        setHere({ x: e.clientX - box.left, y: e.clientY - box.top });
      } : undefined}
      onClick={(e) => {
        // A click on the empty canvas lets go of the step; one inside its menu or card does not.
        const target = e.target as HTMLElement;
        if (!target.closest("[data-node]") && !target.closest(".step-beside")) onSelect(null);
      }}
      footer={
        <>
          <span ref={probe} hidden />
          {here && onAddHere && (
            <div className="step-beside absolute z-20" style={{ left: here.x, top: here.y }}>
              <StepMenu label="canvas menu" items={[{ id: "add", label: "Add step here" }]}
                        onChoose={() => {
                          setHere(null);
                          // The click, from the screen into the drawing's own coordinates.
                          onAddHere({ x: (here.x - view.view.x) / view.view.k, y: (here.y - view.view.y) / view.view.k });
                        }} onClose={() => setHere(null)} />
            </div>
          )}
          {beside && at[beside.node] && (
            // Beside the step on screen, kept inside the frame by CSS alone (no measuring).
            <div className="step-beside absolute z-10 overflow-auto select-text cursor-auto"
                 // Where the step is on screen; `.step-beside` (main.css) keeps the card inside
                 // the frame on every side, and no taller than the room below its top.
                 style={{
                   ["--card-x" as string]: `${Math.round(view.view.x + (at[beside.node].x + NODE_W + 36) * view.view.k)}px`,
                   ["--card-y" as string]: `${Math.round(view.view.y + at[beside.node].y * view.view.k)}px`,
                 }}>
              {beside.content}
            </div>
          )}
          {/* **The boards' frame**: what is drawn and over how many samples, along the top; the
              view's controls bottom-left, what the colours mean bottom-right. */}
          <div className="absolute left-4 right-4 top-3 flex items-baseline gap-3 pointer-events-none">
            <span data-testid="canvas-caption" className="text-[13px] text-ink-2">
              {drawn} {drawn === 1 ? "step" : "steps"} · {sources.length} {sources.length === 1 ? "input" : "inputs"}
            </span>
            {(stale || working) && (
              <span role="status" data-testid={stale ? "canvas-stale" : "canvas-working"}
                    className="text-[12.5px] text-ink-2">
                {stale ? "Outdated — the last pipeline built" : "Updating…"}
              </span>
            )}
            {count !== null && (
              <span data-testid="canvas-samples" className="ml-auto text-[13px] text-ink-2">
                {count} samples, one task each
              </span>
            )}
          </div>
          {/* **The minimap, above the legend** (issue 389): the whole graph, each step marked in the
              colour of what it needs, so where the open value is reads without panning. */}
          {!progress && <Minimap place="right-4 bottom-[64px]" offsets={{}}
                   nodes={ids.map((id) => {
                     const counted = steps[id] ? valuesOf([steps[id]]) : null;
                     return { id, x: at[id]?.x ?? 0, y: at[id]?.y ?? 0,
                              tier: counted?.open ? 4 : counted?.measured ? 3 : 1 };
                   })} />}
          {/* One wrapping row: where the legend cannot sit beside the controls it goes above them. */}
          <div className="absolute left-4 right-4 bottom-4 flex flex-wrap-reverse items-end gap-2 pointer-events-none
                          [&>*]:pointer-events-auto">
            <button type="button" onClick={() => { touched.current = false; fitView(); }} className={CONTROL}>Fit</button>
            <button type="button" aria-label="zoom out" onClick={() => { touched.current = true; view.nudge(-0.1); }} className={CONTROL}>−</button>
            <button type="button" aria-label="zoom in" onClick={() => { touched.current = true; view.nudge(0.1); }} className={CONTROL}>+</button>
            <button type="button" aria-label="reset the view" onClick={() => { touched.current = true; view.reset(); }} className={CONTROL}>1:1</button>
            {footer}
            {(onTidy || Object.keys(moved).length > 0) && (
              <button type="button" data-testid="tidy" title="Lay the steps out again, tidily"
                      onClick={() => { setMoved({}); touched.current = false; tidied.current = true; fitWhenPlaced.current = !!onTidy; onTidy?.(); }}
                      className={CONTROL}>
                Tidy
              </button>
            )}
            <ul aria-label="legend" className="ml-auto m-0 flex items-center gap-3 px-3 py-[6px]
                                               rounded-button border border-line bg-surface text-[12.5px] text-ink-2">
              {(progress ? RUN_LEGEND : LEGEND).map(([word, colour]) => (
                <li key={word} className="list-none flex items-center gap-[6px]">
                  <span aria-hidden className="w-[10px] h-[5px] rounded-full" style={{ background: colour }} />
                  {word}
                </li>
              ))}
            </ul>
          </div>
        </>
      }
    >
      <svg aria-hidden width={width} height={height}
           className="absolute left-0 top-0 overflow-visible pointer-events-none">
        {sources.flatMap(({ channel, edge, feeds }) => {
          // **One trunk for an input several steps read** (#517): a single run out of the input,
          // named, and each step's wire branching off its end.
          const shared = feeds.length > 1;
          const branch = shared ? { x: edge.x + TRUNK, y: edge.y } : edge;
          return [
            shared && (
              <g key={`trunk-${channel.name}`} data-testid={`trunk-${channel.name}`}>
                <line x1={edge.x} y1={edge.y} x2={branch.x} y2={branch.y} stroke="var(--port-line)" strokeWidth={2} />
                <text x={edge.x + 4} y={edge.y - 6} className="font-data" fontSize={10} fill="var(--now-ink)">
                  {channel.name} · shared
                </text>
              </g>
            ),
            ...feeds.map(([node, port]) => {
              const tip = tipIn(node, port);
              if (!tip) return null;
              const flow: Flow =
                gathers(node, port) ? "gather" : channel.grain === "sample" ? "many" : "one";
              return (
                <Flowline key={`src-${channel.name}-${node}-${port}`} testId={`flow-${channel.name}-${node}`}
                          from={branch} to={tip} flow={flow}
                          label={selected === node ? flowLabel(flow, channel.count ?? null) : undefined} />
              );
            }),
          ];
        })}
        {results.map((r) => {
          const from = tipOut(r.id, portsOf(r.id, "out")[0].name);
          if (!from) return null;
          return (
            <Flowline key={`result-wire-${r.id}`} testId={`result-wire-${r.id}`} from={from}
                      to={{ x: r.at.x, y: r.at.y + SOURCE_H / 2 }}
                      flow={steps[r.id]?.runs === "per_item" ? "many" : "one"} />
          );
        })}
        {solid.map((edge) => {
          const from = tipOut(edge.from_node, edge.from_port);
          const to = tipIn(edge.to_node, edge.to_port);
          if (!from || !to) return null;
          const flow = flowOf(edge);
          const faded = lit !== null && !(lit.includes(edge.from_node) && lit.includes(edge.to_node));
          return (
            <g key={`${edge.from_node}.${edge.from_port}-${edge.to_node}.${edge.to_port}`}
               data-lit={lit === null ? undefined : String(!faded)} opacity={faded ? 0.3 : 1}>
            <Flowline
                      testId={`wire-${edge.from_node}-${edge.to_node}`} from={from} to={to} flow={flow}
                      label={
                        selected === edge.from_node || selected === edge.to_node
                          ? flowLabel(flow, count)
                          : undefined
                      } />
            </g>
          );
        })}
        {/* **A wide invisible path under each wire** to detach it: a 1.5px stroke is not a thing
            a hand can hit. */}
        {/* The fact links: out of the measuring step's side, down the gap between columns, along
            the gap above the decided step's row, and into its top — so the line runs between
            steps, never through them, and its label sits on the run along the row gap. */}
        {factLinks.map(({ from, to, label }) => {
          const a = at[from], b = at[to];
          if (!a || !b) return null;
          // **Out of the measuring step's output**, always: from its triangle's tip, a short run
          // along the flow, then down (or up) to the gap above the decided step, along it, and in.
          const out = portsOf(from, "out")[0];
          // A measuring step with no declared output still says its fact from its right edge.
          const start = out ? tipOut(from, out.name)
            : { x: a.x + widthOf(from), y: a.y + anchorOf(measuring(from), 0) };
          if (!start) return null;
          const gx = start.x + 14;
          const leftward = b.x + NODE_W / 2 < gx;
          const tx = b.x + NODE_W / 2;
          const ly = b.y - 16;
          const d = `M ${start.x} ${start.y} H ${gx} V ${ly} H ${tx} V ${b.y}`;
          return (
            <g key={`fact-${from}-${to}-${label}`} data-testid={`fact-link-${from}-${to}`}>
              <path d={d} fill="none" stroke="var(--measured)" strokeWidth={1.25} strokeDasharray="4 4" />
              <text x={leftward ? gx - 6 : gx + 6} y={ly - 5} textAnchor={leftward ? "end" : "start"}
                    className="font-data"
                    style={{ fontSize: 10.5, fill: "var(--measured-ink)" }}>
                {label}
              </text>
            </g>
          );
        })}
        {hangers.map((e) => {
          const above = at[e.from_node], pill = at[e.to_node];
          if (!above || !pill) return null;
          const x = pill.x + MEASURE_W / 2;
          return (
            <line key={`hang-${e.from_node}-${e.to_node}`} data-testid={`hang-${e.from_node}-${e.to_node}`}
                  x1={x} y1={above.y + tall(e.from_node)} x2={x} y2={pill.y}
                  stroke="var(--measured)" strokeWidth={1.25} />
          );
        })}
        {editable && solid.map((edge) => {
          const from = tipOut(edge.from_node, edge.from_port);
          const to = tipIn(edge.to_node, edge.to_port);
          if (!from || !to) return null;
          return (
            <path key={`hit-${edge.from_node}.${edge.from_port}-${edge.to_node}.${edge.to_port}`}
                  data-testid={`wire-hit-${edge.from_node}-${edge.to_node}`}
                  d={path(elbow(from, to))} fill="none" stroke="transparent" strokeWidth={14}
                  className="pointer-events-auto cursor-pointer"
                  onClick={() => onEdit(withoutEdge(graph, edge))}>
              <title>{`${edge.from_node}.${edge.from_port} → ${edge.to_node}.${edge.to_port} — click to detach`}</title>
            </path>
          );
        })}
      </svg>

      {sources.map(({ channel, box }) => (
        <SourceNode key={channel.name} at={box} name={channel.name} typeId={channel.type_id}
                    states={channel.states} grain={channel.grain} count={channel.count ?? samples ?? null}
                    given={given[channel.type_id]} />
      ))}
      {results.map((r) => (
        <ResultNode key={`result-${r.id}`} testId={`living-result-${r.id}`} at={r.at} name={r.name} detail={r.detail} />
      ))}

      {ids.map((id) => {
        if (!at[id]) return null;
        return (
          <Fragment key={id}>
          <LivingNode
            id={id}
            at={at[id]}
            author={authors[id] ?? "resolver"}
            ports={steps[id]?.ports ?? []}
            counts={steps[id] ? valuesOf([steps[id]]) : undefined}
            reviewState={reviews[id] ?? "unknown"}
            aiChoice={aiChosen.includes(id)}
            perItem={steps[id]?.runs === "per_item"}
            takes={steps[id]?.takes_samples?.samples}
            samples={samples}
            version={steps[id]?.contract_id.split("@")[1]}
            tool={steps[id]?.contract_id.split("@")[0].replace(/^[^/]+\//, "").replaceAll("/", " ")}
            does={(steps[id] as { does?: string | null } | undefined)?.does}
            measures={measuring(id)}
            setRow={setRowOf(id)}
            showTool={showTool}
            showPorts={showPorts}
            progress={progress?.[id]}
            onHover={(on) => hover(id, on)}
            broken={brokenOf(id)}
            selected={selected === id}
            className={lit !== null && !lit.includes(id) ? "opacity-40" : undefined}
            onSelect={() => {
              if (!readOnly && !drag.current?.travelled) onSelect(id);
            }}
            onMenu={onMenu && !readOnly ? () => onMenu(id) : undefined}
            onPointerDown={(e) => {
              if (readOnly) return;
              // **A long press is a right-click** on a touch screen (#499).
              if (e.pointerType === "touch" && onMenu) {
                press.current = setTimeout(() => { press.current = null; drag.current = null; onMenu(id); }, 550);
              }
              drag.current = { id, from: { x: e.clientX, y: e.clientY }, origin: at[id], travelled: false };
              (e.target as Element).setPointerCapture?.(e.pointerId);
            }}
            onPointerMove={(e) => {
              const d = drag.current;
              if (!d || d.id !== id) return;
              const dx = (e.clientX - d.from.x) / view.view.k;
              const dy = (e.clientY - d.from.y) / view.view.k;
              if (!d.travelled && Math.abs(dx) + Math.abs(dy) < 3) return;
              d.travelled = true;
              if (press.current) { clearTimeout(press.current); press.current = null; }
              setMoved((m) => ({ ...m, [id]: { x: Math.round(d.origin.x + dx), y: Math.round(d.origin.y + dy) } }));
            }}
            onPointerUp={() => {
              if (press.current) { clearTimeout(press.current); press.current = null; }
              // **A macrotask, not a microtask.** The click that ends a drag is dispatched after this
              // handler returns, and a microtask would clear the drag before it — so dragging a
              // node would also select it.
              setTimeout(() => {
                drag.current = null;
              }, 0);
            }}
          />
          {/* **`⋯` opens the menu** on the step that is selected — the way in on a phone, where
              there is no right-click (#499). */}
          {onMenu && !readOnly && selected === id && (
            <button type="button" aria-label={`menu for ${id.toUpperCase()}`} onClick={() => onMenu(id)}
                    className="absolute w-[24px] h-[24px] grid place-items-center p-0 rounded-control border
                               border-line-2 bg-surface text-ink-2 text-[14px] leading-none cursor-pointer
                               hover:text-ink focus-visible:shadow-[var(--ring)]"
                    style={{ left: at[id].x + NODE_W + 6, top: at[id].y }}>
              ⋯
            </button>
          )}
          {editable && (
            <div data-testid={`ports-${id}`} className="absolute pointer-events-none"
                 style={{ left: at[id].x, top: at[id].y, width: widthOf(id), height: tall(id) }}>
              {(["in", "out"] as const).flatMap((side) =>
                portsOf(id, side).map((port, i) => (
                  <span key={`${side}.${port.name}`} className="pointer-events-auto">
                    <Port port={port} side={side} y={anchorOf(measuring(id), i)}
                          verdict={side === "in" ? verdictFor(id, port.name) : undefined}
                          onStartWire={() => setWiring({ node: id, port: port.name })}
                          onFinishWire={() => {
                            if (wiring) {
                              onEdit(withEdge(graph, { from_node: wiring.node, from_port: wiring.port,
                                                       to_node: id, to_port: port.name }));
                            }
                            setWiring(null);
                          }}
                          onExplore={() => setPicking({ node: id, port, at: onScreen({
                            x: at[id].x + (side === "out" ? NODE_W + 16 : -356), y: at[id].y }) })} />
                  </span>
                )))}
            </div>
          )}
          </Fragment>
        );
      })}
      {hovered && at[hovered] && steps[hovered] && hovered !== beside?.node && (
        <HoverCard step={steps[hovered]} at={{ x: at[hovered].x + widthOf(hovered) + 14, y: at[hovered].y }}
                   samples={samples} measuring={measuring(hovered)} typeName={typeName} />
      )}
      {picking && editable && (
        <Picker port={picking.port} node={picking.node} at={picking.at}
                onClose={() => setPicking(null)}
                onPick={(contract, theirPort) => {
                  // **Add the step AND draw the wire**, in the clicked port's direction: an output
                  // feeds the new step, an input is fed by it.
                  const added = idFor(graph, contract);
                  const next = withNode(graph, { id: added, contract_id: contract, params: [] });
                  onEdit(withEdge(next, picking.port.side === "out"
                    ? { from_node: picking.node, from_port: picking.port.name, to_node: added, to_port: theirPort }
                    : { from_node: added, from_port: theirPort, to_node: picking.node, to_port: picking.port.name }));
                  setPicking(null);
                }} />
      )}
    </Canvas>
  );
}

/** **A step's details on hover** (#511): the tool and version, how often it runs, and what goes in
 *  and comes out, by type — what the card leaves out to stay small. */
function HoverCard({ step, at, samples, measuring, typeName }: {
  step: Step; at: Point; samples?: number; measuring: boolean; typeName: (id: string) => string;
}) {
  const [tool, version] = step.contract_id.split("@");
  const ins = step.ports.filter((p) => p.side === "in");
  const outs = step.ports.filter((p) => p.side === "out");
  const does = (step as { does?: string | null }).does;
  return (
    <div role="tooltip" data-testid={`hover-${step.id}`}
         className="absolute z-30 w-[240px] pointer-events-none flex flex-col gap-[6px] px-3 py-[10px] rounded-panel border border-line bg-surface shadow-e2"
         style={{ left: at.x, top: at.y }}>
      <span className="text-[13px] font-semibold text-ink">{measuring ? `Measures ${outs[0]?.name.replaceAll("_", " ") ?? "a fact"}` : does ?? step.process}</span>
      <span className="font-data text-[11px] text-ink-2">{tool.replace(/^[^/]+\//, "").replaceAll("/", " ")} {version}</span>
      <span className="text-[12px] text-ink-2">
        {step.runs === "per_item" ? `Runs once per sample${samples ? `, ×${samples}` : ""}` : "Runs once"}
        {measuring && " · in the run, from the data"}
      </span>
      {ins.length > 0 && (
        <span className="flex flex-col gap-[2px] text-[11.5px]">
          <span className="font-semibold text-ink-3">In</span>
          {ins.map((p) => (
            <span key={p.name} className="text-ink-2"><span className="font-data">{p.name}</span> · {typeName(p.type_id)}{p.optional ? " · optional" : ""}</span>
          ))}
        </span>
      )}
      {outs.length > 0 && (
        <span className="flex flex-col gap-[2px] text-[11.5px]">
          <span className="font-semibold text-ink-3">Out</span>
          {outs.map((p) => (
            <span key={p.name} className="text-ink-2"><span className="font-data">{p.name}</span> · {typeName(p.type_id)}</span>
          ))}
        </span>
      )}
    </div>
  );
}
