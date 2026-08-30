import { act, renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { useGraph } from "./useGraph";

const STAR = "nf-core/star/align@1.11.0";
const SORT = "nf-core/samtools/sort@1.21.0";

const empty = { nodes: [], edges: [] };

describe("the working graph", () => {
  it("adds a node without touching the network", () => {
    const { result } = renderHook(() => useGraph(empty));
    act(() => result.current.addNode(STAR));
    expect(result.current.graph.nodes).toHaveLength(1);
    expect(result.current.dirty).toBe(true);
  });

  it("gives every node a distinct id when the same tool is added twice", () => {
    const { result } = renderHook(() => useGraph(empty));
    act(() => {
      result.current.addNode(STAR);
      result.current.addNode(STAR);
    });
    const [a, b] = result.current.graph.nodes.map((n) => n.id);
    expect(a).not.toEqual(b);
  });

  it("names a node after its tool, not after a counter alone", () => {
    // The id lands in a pipeline.yml a person reads. `star_align_1` beats `node_1`.
    const { result } = renderHook(() => useGraph(empty));
    act(() => result.current.addNode(STAR));
    expect(result.current.graph.nodes[0].id).toMatch(/star/);
  });

  it("removes a node's wires with it", () => {
    const { result } = renderHook(() => useGraph(empty));
    act(() => {
      result.current.addNode(STAR);
      result.current.addNode(SORT);
    });
    const [a, b] = result.current.graph.nodes.map((n) => n.id);
    act(() => result.current.connect(a, "bam", b, "bam"));
    expect(result.current.graph.edges).toHaveLength(1);
    act(() => result.current.removeNode(a));
    expect(result.current.graph.edges).toHaveLength(0);
  });

  it("refuses to draw the same wire twice", () => {
    const { result } = renderHook(() => useGraph(empty));
    act(() => {
      result.current.addNode(STAR);
      result.current.addNode(SORT);
    });
    const [a, b] = result.current.graph.nodes.map((n) => n.id);
    act(() => {
      result.current.connect(a, "bam", b, "bam");
      result.current.connect(a, "bam", b, "bam");
    });
    expect(result.current.graph.edges).toHaveLength(1);
  });

  it("keeps wires attached when a node moves", () => {
    // The 3C defect: offsets were local state and wires drew from the backend's points, so
    // the graph broke the moment you touched it. Position is not part of the graph.
    const { result } = renderHook(() => useGraph(empty));
    act(() => {
      result.current.addNode(STAR);
      result.current.addNode(SORT);
    });
    const [a, b] = result.current.graph.nodes.map((n) => n.id);
    act(() => result.current.connect(a, "bam", b, "bam"));
    const before = result.current.graph.edges;
    act(() => result.current.moveNode(a, { x: 120, y: 40 }));
    expect(result.current.graph.edges).toEqual(before);
    expect(result.current.offsets[a]).toEqual({ x: 120, y: 40 });
  });

  it("disconnects one wire without touching the others", () => {
    const { result } = renderHook(() => useGraph(empty));
    act(() => {
      result.current.addNode(STAR);
      result.current.addNode(SORT);
      result.current.addNode(SORT);
    });
    const [a, b, c] = result.current.graph.nodes.map((n) => n.id);
    act(() => {
      result.current.connect(a, "bam", b, "bam");
      result.current.connect(a, "bam", c, "bam");
    });
    act(() => result.current.disconnect(a, "bam", b, "bam"));
    expect(result.current.graph.edges).toHaveLength(1);
    expect(result.current.graph.edges[0].to_node).toBe(c);
  });

  it("does not save while you are still drawing", () => {
    vi.useFakeTimers();
    const save = vi.fn().mockResolvedValue(undefined);
    const { result } = renderHook(() => useGraph(empty, { save, idleMs: 5000 }));
    act(() => {
      result.current.addNode(STAR);
    });
    act(() => vi.advanceTimersByTime(4000));
    act(() => {
      result.current.addNode(SORT);
    });
    act(() => vi.advanceTimersByTime(4000));
    expect(save).not.toHaveBeenCalled(); // the second edit restarted the clock
    act(() => vi.advanceTimersByTime(1500));
    expect(save).toHaveBeenCalledTimes(1); // one write, not two
    vi.useRealTimers();
  });

  it("clears dirty only when the save reports success", async () => {
    const save = vi.fn().mockRejectedValue(new Error("offline"));
    const { result } = renderHook(() => useGraph(empty, { save, idleMs: 0 }));
    await act(async () => {
      result.current.addNode(STAR);
    });
    await act(async () => {
      await Promise.resolve();
    });
    expect(result.current.dirty).toBe(true); // a failed save is not a save
  });
});

describe("what the server may rearrange", () => {
  it("re-seeds a node nobody has moved when the layout changes", () => {
    // **The defect the operator's walk found, arriving through a different door.**
    //
    // `seed` placed a node once per node, EVER. So adding a step re-ranked the graph on the
    // server and the untouched nodes refused to move: `samtools/index` became a sibling of
    // `subread/featurecounts`, the new node took the new layout, the old one stayed where it
    // had been when it was alone in its rank, and the two drew on top of each other. The graph
    // appeared to lose a step while the saved draft was correct throughout — which is the worst
    // way for it to be wrong, because nothing but looking would catch it.
    const { result } = renderHook(() => useGraph({ nodes: [], edges: [] }));

    act(() => result.current.seed({ a: { x: 0, y: 0 }, b: { x: 224, y: 0 } }));
    expect(result.current.offsets.b).toEqual({ x: 224, y: 0 });

    // The server re-ranks: `b` now shares a rank with something and moves across the flow.
    act(() => result.current.seed({ a: { x: 0, y: 0 }, b: { x: 224, y: 170 } }));
    expect(result.current.offsets.b).toEqual({ x: 224, y: 170 });
  });

  it("never moves a box a person put somewhere", () => {
    // The property the seed-once rule was written for, and it survives: being DRAWN somewhere
    // is not being PUT there, and only the second one wins against a re-layout.
    const { result } = renderHook(() => useGraph({ nodes: [], edges: [] }));

    act(() => result.current.seed({ a: { x: 0, y: 0 } }));
    act(() => result.current.moveNode("a", { x: 900, y: 500 }));
    act(() => result.current.seed({ a: { x: 0, y: 170 } }));

    expect(result.current.offsets.a).toEqual({ x: 900, y: 500 });
  });

  it("gives a tidied node back to the server", () => {
    const { result } = renderHook(() => useGraph({ nodes: [], edges: [] }));

    act(() => result.current.moveNode("a", { x: 900, y: 500 }));
    act(() => result.current.tidy());
    act(() => result.current.seed({ a: { x: 0, y: 170 } }));

    expect(result.current.offsets.a).toEqual({ x: 0, y: 170 });
  });
});
