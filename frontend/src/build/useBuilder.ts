import { useQuery } from "@tanstack/react-query";
import { useCallback, useEffect, useRef, useState } from "react";

import { freeSpot } from "./geometry";

import { get, post } from "../api/client";
import { useGraph } from "./useGraph";
import type { AlignedStep, Built, Comparison, DraftGraph, Verdict } from "../api/types";


/** What the canvas draws before anything is on it. Not a loading state and not an error. */
const EMPTY_VIEW: Built = {
  steps: [],
  layout: { nodes: [], wires: [], width: 0, height: 0 },
  provenance: {},
  settled_share: 1,
  needs_review: [],
};

/** The pipeline the canvas opens on, as a graph you can edit.
 *
 * `/pipeline/example` returns a laid-out `BuiltPipeline` because that is what 3C's canvas
 * renders. A builder needs the *graph* under it, and the graph is recoverable from the view —
 * the steps are the nodes and the wires are the edges. Deriving it here rather than adding an
 * endpoint keeps one definition of what the example is.
 */
export function graphOf(built: Built): DraftGraph {
  return {
    nodes: built.steps.map((step) => ({
      id: step.id,
      contract_id: step.contract_id,
      params: [],
    })),
    edges: built.layout.wires.map((wire) => ({
      from_node: wire.from_node,
      from_port: wire.from_port,
      to_node: wire.to_node,
      to_port: wire.to_port,
    })),
  };
}

/** Everything the builder screen does, minus how it looks.
 *
 * **Three network calls and no more.** `draw` lays the graph out — layout stays in Python so the
 * canvas is as deterministic as the emitted `.nf` — `validate` says what is wrong, and `compare`
 * is a button. Dragging, wiring and deleting are local, which is `useGraph`'s job.
 *
 * `validate` and `draw` are keyed on the graph itself, so they refetch when it changes and not
 * while a mouse is moving. `compare` is deliberately *not* a query: it runs a full resolve and
 * must happen when somebody asks, not when something changed.
 */
export function useBuilder(initial: DraftGraph, save?: (g: DraftGraph) => Promise<unknown>) {
  const graphState = useGraph(initial, { save });
  const { graph, seed } = graphState;

  // **Debounced, so a burst of edits is one round trip.** Typing in a settings field fires an
  // edit per keystroke; without this each one is a `draw` and a `validate`.
  const key = useSettled(JSON.stringify(graph), 180);
  const settled = useSettledValue(graph, key);
  const empty = graph.nodes.length === 0;

  const drawn = useQuery({
    queryKey: ["draw", key],
    queryFn: () => post<Built>("/pipeline/draw", settled),
    // An empty graph needs no server round trip — but it is not an error and not a loading
    // state either. **A blank canvas is where a builder starts.**
    enabled: !empty,
    // **The canvas never blanks.** A new query key makes `data` undefined until it resolves, so
    // every edit unmounted the whole graph and remounted it — which is what the flicker was.
    // Keeping the last good view means an edit changes the picture rather than replacing it.
    placeholderData: (previous) => previous,
  });

  const verdict = useQuery({
    queryKey: ["validate", key],
    queryFn: () => post<Verdict>("/pipeline/validate", settled),
    enabled: !empty,
    placeholderData: (previous) => previous,
  });

  // The server's arrangement seeds any node the client has not placed — once each. After that
  // the client's position wins, so a re-layout cannot move a box under somebody's hand.
  useEffect(() => {
    if (!drawn.data) return;
    const from: Record<string, { x: number; y: number }> = {};
    for (const node of drawn.data.layout.nodes) from[node.id] = { x: node.x, y: node.y };
    seed(from);
  }, [drawn.data, seed]);

  const [alignment, setAlignment] = useState<AlignedStep[] | null>(null);
  const [comparing, setComparing] = useState(false);

  const compare = useCallback(
    async (goal: unknown) => {
      setComparing(true);
      try {
        const result = await post<Comparison>("/pipeline/compare", { graph, goal });
        setAlignment(result.alignment);
        return result;
      } finally {
        setComparing(false);
      }
    },
    [graph],
  );

  /** Take the resolver's half of a row.
   *
   * Local: adopting rewrites the graph in the browser and the next `draw`/`validate` follows
   * from it. Nothing is sent — a round trip per click would make the diff feel like a form.
   */
  /** Add a node and give it a position immediately, so it appears under the cursor rather
   *  than after a round trip. */
  const addAt = useCallback(
    (contractId: string, near?: { x: number; y: number }) => {
      const id = graphState.addNode(contractId);
      if (id) graphState.moveNode(id, freeSpot(graphState.offsets, near));
      return id;
    },
    [graphState],
  );

  const adopt = useCallback(
    (row: AlignedStep) => {
      if (row.state === "yours-only" && row.yours_node) {
        graphState.removeNode(row.yours_node);
        return;
      }
      if (row.state === "mendel-only" && row.mendel_contract) {
        graphState.addNode(row.mendel_contract);
        return;
      }
      if (row.state === "differs" && row.yours_node && row.mendel_contract) {
        // **Swap in place.** Removing and adding would drop every wire the step had, which is
        // the opposite of what "adopt Mendel's choice for this step" means.
        graphState.replaceContract(row.yours_node, row.mendel_contract);
      }
    },
    [graphState],
  );

  return {
    ...graphState,
    drawn: empty ? EMPTY_VIEW : (drawn.data ?? null),
    addAt,
    /** True while the server is catching up. **Not a loading state** — the canvas keeps showing
     *  the last good view; this is only for a quiet indicator. */
    settling: drawn.isFetching || verdict.isFetching,
    drawnError: drawn.error,
    findings: verdict.data?.findings ?? [],
    alignment,
    comparing,
    compare,
    adopt,
    clearComparison: () => setAlignment(null),
  };
}

/** The example, as a graph. Fetched once; the builder edits a copy. */
export function useExample() {
  return useQuery({
    queryKey: ["pipeline", "example"],
    queryFn: () => get<Built>("/pipeline/example"),
  });
}


/** A value that only changes once it has stopped changing for `ms`.
 *
 * Used for the query key rather than the payload, so React Query sees one key per burst of
 * edits instead of one per keystroke.
 */
function useSettled(value: string, ms: number): string {
  const [settled, setSettled] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setSettled(value), ms);
    return () => clearTimeout(timer);
  }, [value, ms]);
  return settled;
}

/** The graph as it was when `key` last settled.
 *
 * The query key is debounced and the payload must match it, or a request goes out carrying a
 * graph newer than the key it is cached under — and the answer is then filed against the wrong
 * question.
 */
function useSettledValue(graph: DraftGraph, key: string): DraftGraph {
  const held = useRef(graph);
  if (JSON.stringify(held.current) !== key) {
    try {
      held.current = JSON.parse(key) as DraftGraph;
    } catch {
      /* the first render, before anything has settled */
    }
  }
  return held.current;
}
