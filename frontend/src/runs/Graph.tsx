import { useQuery } from "@tanstack/react-query";

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

function RunNode({ node }: { node: Placed }) {
  return (
    <g data-testid={`node-${node.id}`} data-state={
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

export function Graph({ runId }: { runId: string }) {
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
      <svg
        data-testid="run-graph"
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
