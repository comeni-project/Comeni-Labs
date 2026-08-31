import { act, renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { graphOf } from "./useBuilder";
import { useGraph } from "./useGraph";

const STAR = "nf-core/star/align@1.11.0";
const HISAT2 = "nf-core/hisat2/align@2.2.2";
const SORT = "nf-core/samtools/sort@1.21.0";

describe("recovering the graph from a built view", () => {
  it("takes the nodes from the steps and the edges from the wires", () => {
    // `/pipeline/example` returns a laid-out view because that is what 3C's canvas renders.
    // The graph under it is recoverable, so the example needs no second endpoint.
    const built = {
      steps: [
        { id: "align", contract_id: STAR, process: "STAR_ALIGN", tier: 2, reason: "",
          ports: [], settings: [] },
        { id: "sort", contract_id: SORT, process: "SAMTOOLS_SORT", tier: 2, reason: "",
          ports: [], settings: [] },
      ],
      channels: [],
      layout: {
        nodes: [], width: 0, height: 0,
        wires: [
          { from_node: "align", from_port: "bam", to_node: "sort", to_port: "bam",
            type_id: "alignment.bam", points: [], label_at: { x: 0, y: 0 } },
        ],
      },
      provenance: {}, settled_share: 1, needs_review: [],
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    } as any;

    const graph = graphOf(built);
    expect(graph.nodes.map((n) => n.id)).toEqual(["align", "sort"]);
    expect(graph.edges).toHaveLength(1);
    expect(graph.edges[0].from_node).toBe("align");
  });
});

describe("adopting the resolver's choice", () => {
  it("swaps the contract in place and keeps the wires", () => {
    // The whole point of "adopt Mendel's choice FOR THIS STEP". Remove-and-add would drop
    // every wire the step had.
    const { result } = renderHook(() => useGraph({ nodes: [], edges: [] }));
    act(() => {
      result.current.addNode(HISAT2);
      result.current.addNode(SORT);
    });
    const [align, sort] = result.current.graph.nodes.map((n) => n.id);
    act(() => result.current.connect(align, "bam", sort, "bam"));
    expect(result.current.graph.edges).toHaveLength(1);

    act(() => result.current.replaceContract(align, STAR));
    expect(result.current.graph.nodes[0].contract_id).toBe(STAR);
    expect(result.current.graph.nodes[0].id).toBe(align);
    expect(result.current.graph.edges).toHaveLength(1);
  });

  it("marks the graph dirty so the swap is saved", () => {
    const { result } = renderHook(() => useGraph({ nodes: [], edges: [] }));
    act(() => result.current.addNode(HISAT2));
    const id = result.current.graph.nodes[0].id;
    act(() => result.current.replaceContract(id, STAR));
    expect(result.current.dirty).toBe(true);
  });
});

