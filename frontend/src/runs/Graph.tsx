import { useQuery } from "@tanstack/react-query";
import { useRef, useState } from "react";

import { Menu, copy, useContextMenu } from "./Menu";

import { Canvas } from "../build/Canvas";
import { useView } from "../build/useView";

import { Failed, Loading } from "../ui/States";
import { get } from "../wiener/api/client";

type Placed = {
  id: string; process: string;
  x: number; y: number; width: number; height: number; tier: number;
  done: number; failed: number; running: number; total: number; attempts: number;
};
type Wire = {
  from_node: string; to_node: string; points: { x: number; y: number }[];
  active: boolean; bytes_moved: number | null;
};
type RunGraph = { nodes: Placed[]; wires: Wire[]; width: number; height: number };

/** What a node's fill says. **The run's own vocabulary, not a fifth palette** — `--pea` is
 *  settled, `--measured` is working, `--undecided` needs a person, and a step that has not
 *  started is drawn as the surface it sits on rather than as a colour meaning "nothing". */
function fillOf(node: Placed): string {
  // **The STROKE carries the state; the fill stays the surface.** Tinting the body as well
  // made every node a coloured slab and the graph a bag of sweets — `Graph.dc.html` fills
  // every reached node with `--surface` and lets the outline say what happened. A step that
  // has not started is the deeper surface, so "nothing here yet" is a recess, not a colour.
  if (!node.total) return "var(--surface-2)";
  return "var(--surface)";
}

function strokeOf(node: Placed): string {
  if (node.failed) return "var(--undecided)";
  if (node.running) return "var(--measured)";
  if (node.total && node.done === node.total) return "var(--pea)";
  if (!node.total) return "var(--line)";
  return "var(--line-2)";
}

/** What the node says under its name, and it says only what happened.
 *
 * `waiting` rather than `0 / 0`: a step with no tasks has not been reached, and a pair of zeros
 * reads as a step that ran nothing successfully. */
function tally(node: Placed): string {
  // **The artboard's words, which are the overview's words** — `12 done · 1 retried`,
  // `3 done · 9 more seen`, `not started`. A bare `3 / 12` claims a denominator nobody can
  // source while a run is live, which is the same reason the process table says `done` and
  // `more seen` rather than a fraction. One vocabulary across three screens.
  if (!node.total) return "not started";
  const parts = [`${node.done} done`];
  const outstanding = node.total - node.done - node.failed;
  if (outstanding > 0) parts.push(`${outstanding} more seen`);
  if (node.failed) parts.push(`${node.failed} failed`);
  if (node.attempts > 1) parts.push(`${node.attempts - 1} retried`);
  return parts.join(" · ");
}


/** `dag-core` ranks the DAG; **this decides which way the ranks run.**
 *
 * The layout arithmetic stays in Python — one implementation for both canvases, which is the
 * whole reason `dag-core` exists. What the server does not decide is orientation, and the two
 * artboards genuinely differ: the builder stacks downward because you assemble a pipeline top
 * to bottom, and `Graph.dc.html` runs a *finished* graph left to right, the way a run reads.
 * So rank becomes x here and order becomes y, and the server's own x/y are read only for the
 * grouping they already encode.
 */
const NODE_W = 178;
const NODE_H = 50;
const RANK_X = 290;
const ROW_Y = 150;
const PAD = 24;

function laidOut(nodes: Placed[]): Placed[] {
  const ranks = [...new Set(nodes.map((n) => n.y))].sort((a, b) => a - b);
  const seen = new Map<number, number>();
  return nodes.map((node) => {
    const rank = ranks.indexOf(node.y);
    const order = seen.get(rank) ?? 0;
    seen.set(rank, order + 1);
    return { ...node, width: NODE_W, height: NODE_H,
             x: PAD + rank * RANK_X, y: PAD + order * ROW_Y };
  });
}

/** The artboard's elbow: out of the right edge, across to the midpoint, over, and in. */
function elbow(from: Placed, to: Placed): string {
  const y1 = from.y + NODE_H / 2;
  const y2 = to.y + NODE_H / 2;
  const x1 = from.x + NODE_W;
  const mid = Math.round((x1 + to.x) / 2);
  return y1 === y2
    ? `M${x1} ${y1} L${to.x} ${y2}`
    : `M${x1} ${y1} L${mid} ${y1} L${mid} ${y2} L${to.x} ${y2}`;
}

function RunNode({ node, bind }: { node: Placed; bind?: object }) {
  return (
    <g data-testid={`node-${node.id}`} {...bind} data-state={
      node.failed ? "failed" : node.running ? "running"
        : node.total && node.done === node.total ? "done" : "waiting"
    }>
      <rect
        x={node.x} y={node.y} width={node.width} height={node.height} rx={3}
        fill={fillOf(node)} stroke={strokeOf(node)} strokeWidth={1.5}
      />
      {/* **A second ring means something retried** — §9.1. One ring is not an absence of
          information, so a task that ran once draws nothing extra. */}
      {node.attempts > 1 && (
        <rect
          x={node.x - 5} y={node.y - 5} width={node.width + 10} height={node.height + 10} rx={3}
          fill="none" stroke="var(--measured)" strokeWidth={1}
          strokeDasharray="3 3" opacity={0.9}
        />
      )}
      {/* 12 / 10.5 at y+21 / y+38 — the artboard's, and not arbitrary: at 13px
          `SUBREAD_FEATURECOUNTS` is wider than the 178px box and runs out through its own
          right edge. */}
      <text x={node.x + 12} y={node.y + 21} className="fill-ink font-data" fontSize={12}>
        {node.process}
      </text>
      <text x={node.x + 12} y={node.y + 38} className="fill-ink-3 font-data" fontSize={10.5}>
        {tally(node)}
      </text>
    </g>
  );
}

/** The figure, as a file that opens outside this app.
 *
 * **Honest to offer only because `dag-core`'s layout is deterministic** — §12.3. The same run
 * draws the same figure twice, which is the whole reason that layout lives in Python rather
 * than in the browser, and it is what makes this a figure for a methods section rather than a
 * screenshot of a moment.
 *
 * The token values are resolved into the copy: `var(--pea)` means nothing in a file opened in
 * Inkscape, so the SVG would arrive with every stroke unset.
 */
function svgOf(svg: SVGSVGElement | null): string {
  if (!svg) return "";
  const clone = svg.cloneNode(true) as SVGSVGElement;
  const root = getComputedStyle(document.documentElement);
  const resolve = (value: string) =>
    value.replace(/var\((--[a-z0-9-]+)\)/g, (_, name: string) =>
      root.getPropertyValue(name).trim() || "currentColor");

  for (const node of Array.from(clone.querySelectorAll<SVGElement>("*"))) {
    for (const name of ["fill", "stroke"]) {
      const value = node.getAttribute(name);
      if (value?.includes("var(")) node.setAttribute(name, resolve(value));
    }
  }
  clone.setAttribute("xmlns", "http://www.w3.org/2000/svg");
  clone.style.background = root.getPropertyValue("--paper").trim();
  return new XMLSerializer().serializeToString(clone);
}

export function Graph({ runId, onOpenConsole }: {
  runId: string; onOpenConsole?: (process: string) => void;
}) {
  const canvas = useRef<SVGSVGElement>(null);
  const box = useRef<HTMLDivElement>(null);
  const menu = useContextMenu();
  const [node, setNode] = useState<string | null>(null);
  // **Pan and zoom belong here.** Matching the artboard's *look* is not a reason to ship a
  // figure you cannot move: a twelve-process run does not fit, and a graph you can only
  // squint at is worse than the vertical one it replaced. Same `useView` the builder uses,
  // so the two canvases behave identically under the hand.
  const { view, onWheel, onPointerDown, reset, nudge, fit } = useView();
  const graph = useQuery({
    queryKey: ["run-graph", runId],
    queryFn: () => get<RunGraph>(`/api/runs/${runId}/graph`),
    refetchInterval: 5_000,
  });

  if (graph.isPending) return <Loading what="the graph" />;
  if (graph.isError) return <Failed error={graph.error} />;

  const nodes = laidOut(graph.data.nodes);
  const at = new Map(nodes.map((n) => [n.id, n]));
  // **Natural size, drawn at 1:1.** The scaled-viewBox version had to invent a floor to stop
  // a four-node spine blowing up to poster size; a canvas that zooms needs no such trick —
  // the graph is its own size and the viewer decides how close to stand.
  const width = Math.max(...nodes.map((n) => n.x + NODE_W)) + PAD;
  const height = Math.max(...nodes.map((n) => n.y + NODE_H)) + PAD;

  return (
    <div ref={box} className="flex flex-col flex-1 min-h-0">
      {/* **Outside `Canvas`, and that is the whole of this fix.** `Canvas` renders its
          children inside the stage div, which carries `transform: translate(...) scale(...)`
          — and a transformed ancestor becomes the containing block for `position: fixed`.
          The menu was therefore placed relative to the panned, zoomed stage rather than the
          viewport, so it appeared further away the further you had panned. `Builder.tsx`
          renders its own menu as a sibling for the same reason. */}
        {menu.at && (
        <Menu
          at={menu.at}
          onClose={menu.close}
          items={node
            // §12.3's graph-node menu.
            ? [
                { label: "Show its tasks", w4: true },
                { label: "Open in console",
                  onPick: onOpenConsole && (() => onOpenConsole(node)) },
                { label: "Show it in the table", w4: true },
                { label: "Copy process name", onPick: () => void copy(node), separated: true },
                { label: "Copy the container image", w4: true },
                { label: "Retry the failed tasks", w4: true, separated: true },
              ]
            // §12.3's canvas menu.
            : [
                { label: "Fit to the window",
                  onPick: () => {
                    const r = box.current?.getBoundingClientRect();
                    if (r) fit(width, height, r.width, r.height);
                  } },
                { label: "Zoom to 100%", onPick: reset },
                { label: "Copy the graph as SVG",
                  onPick: () => void copy(svgOf(canvas.current)), separated: true },
                { label: "Save as PNG", w4: true },
                { label: "Show the pipeline it came from", w4: true, separated: true },
              ]}
        />
      )}
      {/* `grid={false}` — the dotted surface is the builder's invitation to drop something,
          and this graph is a record. Everything else the canvas gives (pan, wheel-zoom, the
          grab cursor) is exactly what a graph bigger than its panel needs. */}
      <Canvas view={view} onWheel={onWheel} onPointerDown={onPointerDown} grid={false}
        footer={
          <>
            <div data-zoomer
                 className="absolute right-4 bottom-4 flex items-center gap-1 rounded-[var(--r)]
                            border border-line bg-surface px-1 py-1 shadow-e1">
              <button onClick={() => nudge(-0.1)} aria-label="zoom out" className={zoomBtn}>
                −
              </button>
              <span className="px-1 font-data text-secondary text-ink-2 tabular-nums w-11
                               text-center">
                {Math.round(view.k * 100)}%
              </span>
              <button onClick={() => nudge(0.1)} aria-label="zoom in" className={zoomBtn}>+</button>
              <button onClick={reset} className={zoomBtn}>reset</button>
              <button
                className={zoomBtn}
                onClick={() => {
                  const r = box.current?.getBoundingClientRect();
                  if (r) fit(width, height, r.width, r.height);
                }}
              >
                fit
              </button>
            </div>
          </>
        }
      >
        <svg
          ref={canvas}
          data-testid="run-graph"
          onContextMenu={(event) => {
            // The node under the pointer, or the canvas itself — one listener, because an SVG
            // child's own handler would fight the canvas's for the same gesture.
            const hit = (event.target as Element).closest?.("[data-testid^='node-']");
            setNode(hit?.getAttribute("data-testid")?.replace("node-", "") ?? null);
            menu.bind.onContextMenu(event as unknown as React.MouseEvent<HTMLElement>);
          }}
          width={width}
          height={height}
          className="overflow-visible"
        >
          <defs>
            <marker id="run-arrow" viewBox="0 0 10 10" refX="9" refY="5"
                    markerWidth="6" markerHeight="6" orient="auto">
              <path d="M0,0 L10,5 L0,10 z" fill="var(--line-2)" />
            </marker>
          </defs>

          {graph.data.wires.map((wire, index) => {
            const from = at.get(wire.from_node);
            const to = at.get(wire.to_node);
            if (!from || !to) return null;
            // **Three edges, because a run has three kinds.** Data has crossed it, data is
            // crossing it now, or nothing has come this way yet — and the third draws no
            // arrowhead, because an arrow asserts a direction something travelled.
            const waiting = !to.total && !from.total;
            return (
              <path
                key={`${wire.from_node}-${wire.to_node}-${index}`}
                data-testid={`wire-${wire.from_node}-${wire.to_node}`}
                data-active={wire.active}
                d={elbow(from, to)}
                fill="none"
                className={wire.active ? "live" : undefined}
                stroke={wire.active ? "var(--measured)"
                  : waiting ? "var(--line)" : "var(--line-2)"}
                strokeWidth={wire.active ? 2 : 1.5}
                // **A dash that moves, and never faster for more data** — §9.2. `.live` is a
                // constant 1.1s: a pulse whose speed implied MB/s would be a number nobody
                // measured. A waiting edge is dashed and still.
                strokeDasharray={!wire.active && waiting ? "4 4" : undefined}
                markerEnd={waiting ? undefined : "url(#run-arrow)"}
              />
            );
          })}
          {nodes.map((n) => <RunNode key={n.id} node={n} />)}
        </svg>
      </Canvas>

      <span className="shrink-0 flex items-center gap-4 px-6 py-2.5
                       border-t border-line bg-surface-2 text-label text-ink-3">
        <Swatch colour="var(--pea)" label="done" />
        <Swatch colour="var(--measured)" label="running" />
        <Swatch colour="var(--undecided)" label="failed" />
        <span className="ml-2 uppercase tracking-[.08em]">
          dag-core&rsquo;s layout &middot; the same arithmetic the builder draws
        </span>
      </span>
    </div>
  );
}

const zoomBtn =
  "px-2 py-1 rounded-[var(--r)] bg-transparent border-0 cursor-pointer text-secondary " +
  "text-ink-2 hover:text-ink hover:bg-surface-2";

function Swatch({ colour, label }: { colour: string; label: string }) {
  return (
    <span className="flex items-center gap-1.5">
      <span aria-hidden className="inline-block w-2.5 h-2.5 rounded-[2px]"
            style={{ background: colour }} />
      {label}
    </span>
  );
}
