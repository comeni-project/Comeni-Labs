import { useQuery } from "@tanstack/react-query";
import { useRef, useState } from "react";

import { Menu, copy, useContextMenu } from "./Menu";

import { Canvas } from "../build/Canvas";
import { path } from "../build/geometry";
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
  if (node.failed) return "var(--undecided-soft)";
  if (node.running) return "var(--measured-soft)";
  if (node.total && node.done === node.total) return "var(--pea-soft)";
  return "var(--surface)";
}

function strokeOf(node: Placed): string {
  if (node.failed) return "var(--undecided)";
  if (node.running) return "var(--measured)";
  if (node.total && node.done === node.total) return "var(--pea)";
  return "var(--line-2)";
}

/** What the node says under its name, and it says only what happened.
 *
 * `waiting` rather than `0 / 0`: a step with no tasks has not been reached, and a pair of zeros
 * reads as a step that ran nothing successfully. */
function tally(node: Placed): string {
  if (!node.total) return "waiting";
  const parts = [`${node.done} / ${node.total}`];
  if (node.failed) parts.push(`${node.failed} failed`);
  if (node.running) parts.push(`${node.running} running`);
  if (node.attempts > 1) parts.push(`attempt ${node.attempts}`);
  return parts.join(" · ");
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
          x={node.x - 3} y={node.y - 3} width={node.width + 6} height={node.height + 6} rx={5}
          fill="none" stroke={strokeOf(node)} strokeWidth={1} strokeOpacity={0.5}
        />
      )}
      <text x={node.x + 12} y={node.y + 22} className="fill-ink font-data" fontSize={13}>
        {node.process}
      </text>
      <text x={node.x + 12} y={node.y + 40} className="fill-ink-3 font-data" fontSize={11}>
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
  const menu = useContextMenu();
  const [node, setNode] = useState<string | null>(null);
  const { view, onWheel, onPointerDown } = useView();
  const graph = useQuery({
    queryKey: ["run-graph", runId],
    queryFn: () => get<RunGraph>(`/api/runs/${runId}/graph`),
    refetchInterval: 5_000,
  });

  if (graph.isPending) return <Loading what="the graph" />;
  if (graph.isError) return <Failed error={graph.error} />;

  return (
    <Canvas
      view={view}
      onWheel={onWheel}
      onPointerDown={onPointerDown}
      footer={
        <span className="flex items-center gap-4 text-label text-ink-3">
          <Swatch colour="var(--pea)" label="done" />
          <Swatch colour="var(--measured)" label="running" />
          <Swatch colour="var(--undecided)" label="failed" />
          <span className="ml-2">the builder&rsquo;s own layout, coloured</span>
        </span>
      }
    >
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
                { label: "Fit to the window", w4: true },
                { label: "Zoom to 100%", w4: true },
                { label: "Copy the graph as SVG",
                  onPick: () => void copy(svgOf(canvas.current)), separated: true },
                { label: "Save as PNG", w4: true },
                { label: "Show the pipeline it came from", w4: true, separated: true },
              ]}
        />
      )}

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
        width={graph.data.width + 40}
        height={graph.data.height + 40}
        className="overflow-visible"
      >
        {graph.data.wires.map((wire, index) => (
          <path
            key={`${wire.from_node}-${wire.to_node}-${index}`}
            data-testid={`wire-${wire.from_node}-${wire.to_node}`}
            data-active={wire.active}
            d={path(wire.points)}
            fill="none"
            stroke={wire.active ? "var(--measured)" : "var(--line-2)"}
            strokeWidth={wire.active ? 2 : 1.5}
            // **A dash that moves, and never faster for more data** — §9.2. The duration is a
            // constant: a pulse whose speed implied MB/s would be a number nobody measured.
            strokeDasharray={wire.active ? "6 6" : undefined}
          >
            {wire.active && (
              <animate
                attributeName="stroke-dashoffset"
                from="12" to="0" dur="0.9s" repeatCount="indefinite"
              />
            )}
          </path>
        ))}
        {graph.data.nodes.map((node) => <RunNode key={node.id} node={node} />)}
      </svg>
    </Canvas>
  );
}

function Swatch({ colour, label }: { colour: string; label: string }) {
  return (
    <span className="flex items-center gap-1.5">
      <span aria-hidden className="inline-block w-2.5 h-2.5 rounded-[2px]"
            style={{ background: colour }} />
      {label}
    </span>
  );
}
