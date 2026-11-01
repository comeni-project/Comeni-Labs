import { expect, it } from "vitest";

import { graphLayout } from "./graphLayout";

const tool = (id: string, feeds: string[], roles = ["x"]) => ({ id, feeds, roles, reads: [], makes: [] });

it("places each tool after everything that feeds it", () => {
  const { nodes } = graphLayout([tool("a", ["b"]), tool("b", ["c"]), tool("c", [])]);
  const at = Object.fromEntries(nodes.map((n) => [n.id, n.column]));
  expect([at.a, at.b, at.c]).toEqual([0, 1, 2]);
});

it("a tool fed by a long and a short path sits after the long one", () => {
  const { nodes } = graphLayout([tool("a", ["b", "c"]), tool("b", ["c"]), tool("c", [])]);
  expect(nodes.find((n) => n.id === "c")?.column).toBe(2);
});

it("survives a cycle", () => {
  const { nodes } = graphLayout([tool("a", ["b"]), tool("b", ["a"])]);
  expect(nodes).toHaveLength(2);
});

it("leaves profiling out: it measures data, it is not a step of an analysis", () => {
  const { nodes } = graphLayout([tool("p", [], ["profiling"]), tool("a", [])]);
  expect(nodes.map((n) => n.id)).toEqual(["a"]);
});

it("draws an edge for each link between tools on show", () => {
  const { edges } = graphLayout([tool("a", ["b", "gone"]), tool("b", [])]);
  expect(edges).toHaveLength(1);
});
