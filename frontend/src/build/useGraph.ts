import { useCallback, useEffect, useRef, useState } from "react";

import type { components } from "../api/schema";

type DraftGraph = components["schemas"]["DraftGraph"];
type DraftEdge = components["schemas"]["DraftEdge"];

export type Offset = { x: number; y: number };

/** Where a node has been dragged to. **Not part of the graph.**
 *
 * Plan 3C's defect was the other way round — offsets were local to `Node` and the wires drew
 * from the backend's points, so a dragged node left its wires behind. The fix is not to put
 * position *into* the graph: a `pipeline.yml` describing where somebody dropped a box on a
 * screen would be an artifact that changes when nothing about the pipeline has. Offsets live
 * beside the graph, and the wires recompute from the moved ends.
 */
type Offsets = Record<string, Offset>;

const IDLE_MS = 5000;

/** A short, readable node id from a contract id.
 *
 * The id lands in a `pipeline.yml` a person reads and in every `DecisionRecord` keyed on it, so
 * `star_align_1` is worth the six lines that `node_1` would not be.
 */
function stem(contractId: string): string {
  const withoutVersion = contractId.split("@")[0];
  return withoutVersion.split("/").slice(1).join("_").replace(/[^a-zA-Z0-9_]/g, "_") || "step";
}

function nextId(existing: Set<string>, contractId: string): string {
  const base = stem(contractId);
  for (let n = 1; ; n += 1) {
    const candidate = `${base}_${n}`;
    if (!existing.has(candidate)) return candidate;
  }
}

const sameEdge = (a: DraftEdge, b: DraftEdge) =>
  a.from_node === b.from_node &&
  a.from_port === b.from_port &&
  a.to_node === b.to_node &&
  a.to_port === b.to_port;

/** The graph you are drawing. **Every edit is local; nothing here touches the network.**
 *
 * Three calls exist in the whole builder — `validate` on drop, `compare` on a button, and the
 * save this hook debounces. Dragging a node, drawing a wire and deleting one are none of them:
 * a request per drag frame is what makes a canvas feel slow, and the compatibility index is
 * what lets a wire colour itself without one.
 */
export function useGraph(
  initial: DraftGraph,
  options: { save?: (graph: DraftGraph) => Promise<unknown>; idleMs?: number } = {},
) {
  const { save, idleMs = IDLE_MS } = options;
  const [graph, setGraph] = useState<DraftGraph>(initial);
  const [offsets, setOffsets] = useState<Offsets>({});
  const [dirty, setDirty] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  const edit = useCallback((next: (g: DraftGraph) => DraftGraph) => {
    setGraph((current) => next(current));
    setDirty(true);
  }, []);

  const addNode = useCallback(
    (contractId: string) =>
      edit((g) => {
        const id = nextId(new Set(g.nodes.map((n) => n.id)), contractId);
        return { ...g, nodes: [...g.nodes, { id, contract_id: contractId, params: [] }] };
      }),
    [edit],
  );

  const removeNode = useCallback(
    (id: string) =>
      edit((g) => ({
        ...g,
        nodes: g.nodes.filter((n) => n.id !== id),
        // A wire to a node that is gone is not a wire; leaving it would make `validate`
        // report MD0509 for something the person already deleted.
        edges: g.edges.filter((e) => e.from_node !== id && e.to_node !== id),
      })),
    [edit],
  );

  const connect = useCallback(
    (fromNode: string, fromPort: string, toNode: string, toPort: string) =>
      edit((g) => {
        const wire = {
          from_node: fromNode,
          from_port: fromPort,
          to_node: toNode,
          to_port: toPort,
        };
        // Drawn twice is drawn once. MD0505 counts wires into a port, so a duplicate would
        // report an arity error for a graph that has one wire in it.
        if (g.edges.some((e) => sameEdge(e, wire))) return g;
        return { ...g, edges: [...g.edges, wire] };
      }),
    [edit],
  );

  const disconnect = useCallback(
    (fromNode: string, fromPort: string, toNode: string, toPort: string) =>
      edit((g) => ({
        ...g,
        edges: g.edges.filter(
          (e) =>
            !sameEdge(e, {
              from_node: fromNode,
              from_port: fromPort,
              to_node: toNode,
              to_port: toPort,
            }),
        ),
      })),
    [edit],
  );

  /** Position only. **Does not mark the graph dirty** — where a box sits is not a change to
   * the pipeline, and saving on every drag frame is exactly what this hook exists to avoid. */
  const moveNode = useCallback(
    (id: string, to: Offset) => setOffsets((current) => ({ ...current, [id]: to })),
    [],
  );

  useEffect(() => {
    if (!dirty || !save) return;
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => {
      // `dirty` clears only on success. A failed save that cleared it would lose the work
      // silently, which is the one failure mode a draft must not have.
      void Promise.resolve(save(graph))
        .then(() => setDirty(false))
        .catch(() => undefined);
    }, idleMs);
    return () => {
      if (timer.current) clearTimeout(timer.current);
    };
  }, [graph, dirty, save, idleMs]);

  return { graph, offsets, dirty, addNode, removeNode, connect, disconnect, moveNode };
}
