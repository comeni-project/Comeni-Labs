import { useQuery } from "@tanstack/react-query";
import { useCallback, useState } from "react";

import { get, post } from "../api/client";
import type { components } from "../api/schema";
import { useGraph } from "./useGraph";

type Built = components["schemas"]["BuiltPipeline"];
/** **`DraftGraph-Input`, not `DraftGraph`.** FastAPI splits a model that appears in both a
 * request and a response: the input form has the defaulted fields optional, the output form has
 * them required. What this hook holds is what it SENDS, so the input form is the honest one. */
type DraftGraph = components["schemas"]["DraftGraph-Input"];
/** **Namespaced, because three classes are called `Verdict`** — `comeni_core.review.verdict`,
 * `mendel_forge.verify` and `mendel_forge.drift`. FastAPI disambiguates by module path rather
 * than picking one, and renaming a core domain type to dodge a generator artifact would be the
 * tail wagging the dog. */
type Verdict = components["schemas"]["comeni_core__review__verdict__Verdict"];
type Comparison = components["schemas"]["Comparison"];
type AlignedStep = components["schemas"]["AlignedStep"];

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
  const { graph } = graphState;
  const key = JSON.stringify(graph);

  const empty = graph.nodes.length === 0;

  const drawn = useQuery({
    queryKey: ["draw", key],
    queryFn: () => post<Built>("/pipeline/draw", graph),
    // An empty graph needs no server round trip — but it is not an error and not a loading
    // state either. **A blank canvas is where a builder starts.** Returning null here rendered
    // nothing at all, which is the difference between "no pipeline yet" and "something broke".
    enabled: !empty,
  });

  const verdict = useQuery({
    queryKey: ["validate", key],
    queryFn: () => post<Verdict>("/pipeline/validate", graph),
    enabled: graph.nodes.length > 0,
  });

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
