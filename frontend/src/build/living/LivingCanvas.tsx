import { Fragment, useEffect, useRef, useState } from "react";

import type { components } from "../../api/schema";
import type { DraftEdge, DraftGraph, PortView, Step } from "../../api/types";
import { Canvas } from "../Canvas";
import { elbow, heightOf, NODE_W, path, portOffset, RANK_PITCH, SPINE, type Point, type Positions } from "../geometry";
import { idFor, withEdge, withNode, withoutEdge, withoutNode } from "../graphOps";
import { Minimap } from "../Minimap";
import { Picker } from "../Picker";
import { Port } from "../Port";
import { place } from "../Sources";
import { accepts, useCompatibility } from "../useCompatibility";
import { useView } from "../useView";
import { Flowline, flowLabel, SOURCE_H, SOURCE_W, SourceNode, type Flow } from "./CollectionChannel";
import { valuesOf } from "./values";
import type { Author } from "./format";
import { LivingNode, type ReviewState } from "./LivingNode";
import { StepMenu } from "./StepMenu";

type Channel = components["schemas"]["ChannelView"];

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
}) {
  const [here, setHere] = useState<{ x: number; y: number } | null>(null);
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
  /** A step's drawn height: taller for many ports (#494). */
  const tall = (id: string) => heightOf(steps[id]?.ports ?? []);

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
  const solid = graph.edges;
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
  const portsOf = (node: string, side: "in" | "out") =>
    (steps[node]?.ports ?? []).filter((p) => p.side === side);
  const tipIn = (node: string, port: string): Point | null => {
    const box = at[node];
    if (!box) return null;
    const index = portsOf(node, "in").findIndex((p) => p.name === port);
    return { x: box.x, y: box.y + (index < 0 ? SPINE : portOffset(index)) };
  };
  const tipOut = (node: string, port: string): Point | null => {
    const box = at[node];
    if (!box) return null;
    const index = portsOf(node, "out").findIndex((p) => p.name === port);
    return { x: box.x + NODE_W, y: box.y + (index < 0 ? SPINE : portOffset(index)) };
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

  const drawn = ids.length;
  /** Fit the whole drawing, inputs included, in the frame the probe sits in. */
  const fitView = () => {
    const frame = probe.current?.closest<HTMLElement>("[data-testid='canvas']");
    if (!frame) return;
    const xs = [...ids.map((id) => at[id]?.x ?? 0), ...sources.map((s) => s.box.x)];
    const ys = [...ids.map((id) => at[id]?.y ?? 0), ...sources.map((s) => s.box.y)];
    const left = Math.min(...xs), top = Math.min(...ys);
    const right = Math.max(...ids.map((id) => (at[id]?.x ?? 0) + NODE_W));
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
  const width = Math.max(0, ...ids.map((id) => (at[id]?.x ?? 0) + NODE_W + 80));
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
          <Minimap place="right-4 bottom-[64px]" offsets={{}}
                   nodes={ids.map((id) => {
                     const counted = steps[id] ? valuesOf([steps[id]]) : null;
                     return { id, x: at[id]?.x ?? 0, y: at[id]?.y ?? 0,
                              tier: counted?.open ? 4 : counted?.measured ? 3 : 1 };
                   })} />
          {/* One wrapping row: where the legend cannot sit beside the controls it goes above them. */}
          <div className="absolute left-4 right-4 bottom-4 flex flex-wrap-reverse items-end gap-2 pointer-events-none
                          [&>*]:pointer-events-auto">
            <button type="button" onClick={() => { touched.current = false; fitView(); }} className={CONTROL}>Fit</button>
            <button type="button" aria-label="zoom out" onClick={() => { touched.current = true; view.nudge(-0.1); }} className={CONTROL}>−</button>
            <button type="button" aria-label="zoom in" onClick={() => { touched.current = true; view.nudge(0.1); }} className={CONTROL}>+</button>
            <button type="button" aria-label="reset the view" onClick={() => { touched.current = true; view.reset(); }} className={CONTROL}>1:1</button>
            {footer}
            {Object.keys(moved).length > 0 && (
              <button type="button" data-testid="tidy" onClick={() => { setMoved({}); touched.current = false; tidied.current = true; }}
                      className={CONTROL}>
                Tidy
              </button>
            )}
            <ul aria-label="legend" className="ml-auto m-0 flex items-center gap-3 px-3 py-[6px]
                                               rounded-button border border-line bg-surface text-[12.5px] text-ink-2">
              {LEGEND.map(([word, colour]) => (
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
        {solid.map((edge) => {
          const from = tipOut(edge.from_node, edge.from_port);
          const to = tipIn(edge.to_node, edge.to_port);
          if (!from || !to) return null;
          const flow = flowOf(edge);
          return (
            <Flowline key={`${edge.from_node}.${edge.from_port}-${edge.to_node}.${edge.to_port}`}
                      testId={`wire-${edge.from_node}-${edge.to_node}`} from={from} to={to} flow={flow}
                      label={
                        selected === edge.from_node || selected === edge.to_node
                          ? flowLabel(flow, count)
                          : undefined
                      } />
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
          const leftward = b.x + NODE_W / 2 < a.x + NODE_W / 2;
          const sx = leftward ? a.x : a.x + NODE_W;
          const sy = a.y + tall(from) - 11;
          const gx = leftward ? a.x - (RANK_PITCH - NODE_W) / 2 : a.x + NODE_W + (RANK_PITCH - NODE_W) / 2;
          const tx = b.x + NODE_W / 2;
          const ly = b.y - 16;
          const d = `M ${sx} ${sy} H ${gx} V ${ly} H ${tx} V ${b.y}`;
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
                    states={channel.states} grain={channel.grain} count={channel.count ?? null} />
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
            does={(steps[id] as { does?: string | null } | undefined)?.does}
            selected={selected === id}
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
                 style={{ left: at[id].x, top: at[id].y, width: NODE_W, height: tall(id) }}>
              {(["in", "out"] as const).flatMap((side) =>
                portsOf(id, side).map((port, i) => (
                  <span key={`${side}.${port.name}`} className="pointer-events-auto">
                    <Port port={port} side={side} y={portOffset(i)}
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
