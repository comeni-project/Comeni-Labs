import type { DraftEdge, DraftGraph, DraftNode } from "../api/types";

/** The graph's mutation rules, as pure functions over a `DraftGraph`.
 *
 * **One set of rules for every way a graph changes.** `useGraph` applies these to what a person
 * drags; the living session's reducer applies the same functions to a proposal it has just
 * accepted. Two implementations would be two answers to *what does adding a wire twice do* — and
 * the chat-built pipeline and the hand-drawn one would drift the first time either was fixed.
 * Task 8 of the living-pipeline plan says so in as many words.
 *
 * Every function returns the graph it was given, unchanged, when there is nothing to do — so a
 * caller comparing by reference can tell a no-op from an edit.
 */

export const sameEdge = (a: DraftEdge, b: DraftEdge) =>
  a.from_node === b.from_node &&
  a.from_port === b.from_port &&
  a.to_node === b.to_node &&
  a.to_port === b.to_port;

/** Add a node, or replace the one with its id.
 *
 * Replacing rather than duplicating, because an accepted proposal re-delivered by a poll must not
 * put the same step on the canvas twice.
 */
export function withNode(g: DraftGraph, node: DraftNode): DraftGraph {
  const at = g.nodes.findIndex((n) => n.id === node.id);
  if (at === -1) return { ...g, nodes: [...g.nodes, node] };
  const nodes = [...g.nodes];
  nodes[at] = node;
  return { ...g, nodes };
}

/** Remove a node and every wire touching it — a wire to a node that is gone is not a wire, and
 *  leaving it would make `validate` report MD0509 for something already deleted. */
export function withoutNode(g: DraftGraph, id: string): DraftGraph {
  return {
    ...g,
    nodes: g.nodes.filter((n) => n.id !== id),
    edges: g.edges.filter((e) => e.from_node !== id && e.to_node !== id),
  };
}

/** Drawn twice is drawn once. MD0505 counts wires into a port, so a duplicate would report an
 *  arity error for a graph that has one wire in it. */
export function withEdge(g: DraftGraph, wire: DraftEdge): DraftGraph {
  if (g.edges.some((e) => sameEdge(e, wire))) return g;
  return { ...g, edges: [...g.edges, wire] };
}

export function withoutEdge(g: DraftGraph, wire: DraftEdge): DraftGraph {
  return { ...g, edges: g.edges.filter((e) => !sameEdge(e, wire)) };
}

/** Set one parameter's value; `null` clears it and hands it back to the resolver's ladder. */
export function withParam(
  g: DraftGraph,
  id: string,
  name: string,
  value: string | number | boolean | null,
): DraftGraph {
  return {
    ...g,
    nodes: g.nodes.map((n) => {
      if (n.id !== id) return n;
      const rest = (n.params ?? []).filter((p) => p.name !== name);
      return value === null
        ? { ...n, params: rest }
        : { ...n, params: [...rest, { name, value, why: "" }] };
    }),
  };
}

/** Swap one node's contract, keeping its id and therefore its wires. */
export function withContract(g: DraftGraph, id: string, contractId: string): DraftGraph {
  return {
    ...g,
    nodes: g.nodes.map((n) => (n.id === id ? { ...n, contract_id: contractId } : n)),
  };
}

/** Name one socket; an empty label removes the entry rather than storing `""`. */
export function withLabel(g: DraftGraph, key: string, label: string): DraftGraph {
  const rest = (g.labels ?? []).filter((l) => l.key !== key);
  return { ...g, labels: label ? [...rest, { key, label }] : rest };
}

/** Give one socket a channel of its own. A port already on its own channel is left alone. */
export function withSplit(g: DraftGraph, port: string): DraftGraph {
  const channels = g.channels ?? [];
  if (channels.some((c) => c.ports.includes(port))) return g;
  return { ...g, channels: [...channels, { ports: [port], why: "" }] };
}

/** Put a socket back on its type's shared channel, dropping a group left feeding nothing. */
export function withMerge(g: DraftGraph, port: string): DraftGraph {
  return {
    ...g,
    channels: (g.channels ?? [])
      .map((c) => ({ ...c, ports: c.ports.filter((p) => p !== port) }))
      .filter((c) => c.ports.length > 0),
  };
}
