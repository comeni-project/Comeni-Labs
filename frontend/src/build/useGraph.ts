import { useCallback, useEffect, useRef, useState } from "react";
import type { DraftEdge, DraftGraph } from "../api/types";



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
  /** Every id in use, kept in step synchronously so a batch of adds cannot collide. */
  const taken = useRef<Set<string>>(new Set(initial.nodes.map((n) => n.id)));

  const edit = useCallback((next: (g: DraftGraph) => DraftGraph) => {
    setGraph((current) => next(current));
    setDirty(true);
  }, []);

  /** Add a step, and **return the id it was given** so the caller can position it.
   *
   * The id is minted from the current graph rather than inside the reducer, because a caller
   * that cannot name what it just added cannot place it — and a node that cannot be placed has
   * to wait for the server to say where it goes, which is what the flicker was.
   */
  const addNode = useCallback(
    (contractId: string): string => {
      // **Minted from a ref, not from `graph`.** React batches state updates, so two calls in
      // one handler both read the same `graph` and both mint `star_align_1` — which the tests
      // caught the moment `addNode` started returning its id. The ref is updated synchronously,
      // so the second call sees the first.
      const id = nextId(taken.current, contractId);
      taken.current.add(id);
      edit((g) => ({
        ...g,
        nodes: [...g.nodes, { id, contract_id: contractId, params: [] }],
      }));
      return id;
    },
    [edit],
  );

  const removeNode = useCallback(
    (id: string) => (
      taken.current.delete(id),
      edit((g) => ({
        ...g,
        nodes: g.nodes.filter((n) => n.id !== id),
        // A wire to a node that is gone is not a wire; leaving it would make `validate`
        // report MD0509 for something the person already deleted.
        edges: g.edges.filter((e) => e.from_node !== id && e.to_node !== id),
      }))
    ),
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

  /** Set one parameter on one node.
   *
   * **The value only; the tier is the server's to stamp.** A browser claiming `tier: 1` on a
   * value somebody typed would put a lie in `pipeline.yml` that nothing downstream could catch.
   * `materialise` stamps tier 4 and records a `human_override`, because a person who typed a
   * value had a choice and made it.
   *
   * `null` clears it, which hands the parameter back to the resolver's ladder rather than
   * recording an empty answer.
   */
  const setParam = useCallback(
    (id: string, name: string, value: string | null) =>
      edit((g) => ({
        ...g,
        nodes: g.nodes.map((n) => {
          if (n.id !== id) return n;
          const rest = (n.params ?? []).filter((p) => p.name !== name);
          return value === null
            ? { ...n, params: rest }
            : { ...n, params: [...rest, { name, value, why: "" }] };
        }),
      })),
    [edit],
  );

  /** Swap one node's contract, keeping its id and therefore its wires.
   *
   * Adopting the resolver's choice for a step means *this step, that tool* — removing and
   * re-adding would drop every wire the step had, which is the opposite of what was asked.
   * Whether the new contract's ports still fit is `validate`'s answer, not this function's.
   */
  const replaceContract = useCallback(
    (id: string, contractId: string) =>
      edit((g) => ({
        ...g,
        nodes: g.nodes.map((n) => (n.id === id ? { ...n, contract_id: contractId } : n)),
      })),
    [edit],
  );

  /** Put a node somewhere. **Does not mark the graph dirty** — where a box sits is not a change
   * to the pipeline, and a `pipeline.yml` recording where somebody dropped a box on a screen
   * would be an artifact that changes when nothing about the pipeline has.
   *
   * **Absolute, not an offset.** It was an offset from the server's coordinate, which meant a
   * node the server had never laid out had nothing to be offset from — so a node you added
   * could not be positioned until a round trip came back, and the canvas flickered while it
   * did. Positions the client owns outright have no such dependency.
   */
  const moveNode = useCallback(
    (id: string, to: Offset) => setOffsets((current) => ({ ...current, [id]: to })),
    [],
  );

  /** Seed positions for nodes the client has never placed.
   *
   * The server's layout is the canonical arrangement and this is where it lands — **once, per
   * node.** After that the client's position wins, so re-laying-out on the server cannot move a
   * box under somebody's hand. `tidy` is how you ask for the canonical arrangement back.
   */
  const seed = useCallback((from: Record<string, Offset>) => {
    setOffsets((current) => {
      let changed = false;
      const next = { ...current };
      for (const [id, at] of Object.entries(from)) {
        if (next[id] === undefined) {
          next[id] = at;
          changed = true;
        }
      }
      return changed ? next : current;
    });
  }, []);

  /** Throw away the client's positions and take the server's again. */
  const tidy = useCallback(() => setOffsets({}), []);

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

  return {
    graph,
    offsets,
    dirty,
    addNode,
    removeNode,
    replaceContract,
    setParam,
    connect,
    disconnect,
    moveNode,
    seed,
    tidy,
  };
}
