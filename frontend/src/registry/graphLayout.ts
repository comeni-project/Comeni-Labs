import type { components } from "../api/schema";

type Tool = components["schemas"]["ToolChoice"];
export type GraphNode = { id: string; path: string; job: string; column: number; row: number };
export type GraphEdge = { from: string; to: string };

/** The registry's tools in columns, each after what feeds it. `feeds` comes from the server, so
 *  nothing here decides what connects. A cycle stops at the depth it reached. */
export function graphLayout(tools: Tool[]): { nodes: GraphNode[]; edges: GraphEdge[] } {
  const steps = tools.filter((t) => !t.roles.includes("profiling"));
  const ids = new Set(steps.map((t) => t.id));
  const edges = steps.flatMap((t) => t.feeds.filter((to) => ids.has(to)).map((to) => ({ from: t.id, to })));
  const depth = new Map(steps.map((t) => [t.id, 0]));
  for (let pass = 0; pass < steps.length; pass += 1) {
    for (const { from, to } of edges) {
      depth.set(to, Math.max(depth.get(to) ?? 0, Math.min((depth.get(from) ?? 0) + 1, steps.length - 1)));
    }
  }
  const taken = new Map<number, number>();
  const nodes = steps.map((t) => {
    const column = depth.get(t.id) ?? 0;
    const row = taken.get(column) ?? 0;
    taken.set(column, row + 1);
    return { id: t.id, path: t.id.replace(/^[^/]+\//, "").replace(/@.*$/, ""),
             job: t.roles[0] ?? "", column, row };
  });
  return { nodes, edges };
}
