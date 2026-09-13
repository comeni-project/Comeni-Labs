import type { AuthoringSession, DraftEdge } from "../../api/types";
import { withEdge, withNode } from "../graphOps";
import { FAKE_SESSION } from "./fake";

/** A guided session that answers itself — the server's step loop, simulated in the browser.
 *
 * **For the checkpoint, and for looking at the page, and nothing else.** Task 10 asks for a fake
 * guided pipeline completed with only the keyboard and with a touch-like pointer; that needs a
 * session that moves when a proposal is decided, without a database behind it. The rules here are
 * deliberately the small subset the page observes — accept adds the step and its wires, skip adds
 * nothing, and the next step is offered — so a test driving it is testing the page, not this.
 */

const STEPS = FAKE_SESSION.history
  .filter((decision) => decision.kind === "step")
  .map((decision) => decision.block)
  .concat(FAKE_SESSION.pending_proposal ? [FAKE_SESSION.pending_proposal.block] : []);

const WIRES: Record<string, DraftEdge[]> = {
  star_align: [
    { from_node: "trimgalore", from_port: "reads", to_node: "star_align", to_port: "reads" },
    { from_node: "star_genomegenerate", from_port: "index", to_node: "star_align", to_port: "index" },
  ],
  samtools_sort: [
    { from_node: "star_align", from_port: "bam", to_node: "samtools_sort", to_port: "bam" },
  ],
};

const at = (n: number) => `2026-09-13T11:${String(n).padStart(2, "0")}:00+00:00`;

export function guidedStart(): AuthoringSession {
  const goal = FAKE_SESSION.turns[1].blocks[0];
  return {
    ...FAKE_SESSION,
    phase: "goal_review",
    revision: 0,
    graph: { nodes: [], edges: [] },
    turns: [FAKE_SESSION.turns[0], { ...FAKE_SESSION.turns[1], blocks: [goal] }],
    history: [],
    pending_proposal: {
      id: "g-1", kind: "goal", draft_revision: 0, options: ["accept"], edges: [], block: goal,
    },
  } as AuthoringSession;
}

export function guidedDecide(
  session: AuthoringSession,
  proposalId: string,
  decision: "accepted" | "rejected",
  option = "keep",
): AuthoringSession {
  const pending = session.pending_proposal;
  if (!pending || pending.id !== proposalId) return session;

  const history = [
    ...session.history,
    {
      id: pending.id, kind: pending.kind, state: decision, block: pending.block, by: "person",
      chosen_option: pending.kind === "step" ? option : null,
      chosen_contract: pending.block.kind === "step_proposal" ? pending.block.contract : null,
      at: at(session.history.length + 1),
    },
  ] as AuthoringSession["history"];

  let graph = session.graph;
  let revision = session.revision;
  let index = 0;
  if (pending.block.kind === "step_proposal") {
    const node = pending.block.node;
    index = STEPS.findIndex((step) => step.kind === "step_proposal" && step.node === node) + 1;
    if (decision === "accepted") {
      const present = new Set([...graph.nodes.map((n) => n.id), node]);
      graph = withNode(graph, { id: node, contract_id: pending.block.contract, params: [] });
      for (const wire of WIRES[node] ?? []) {
        if (present.has(wire.from_node) && present.has(wire.to_node)) graph = withEdge(graph, wire);
      }
      revision += 1;
    }
  } else if (decision === "accepted") {
    revision += 1;
  }

  const next = STEPS[index];
  if (!next || next.kind !== "step_proposal") {
    return { ...session, phase: "complete", graph, revision, history, pending_proposal: null };
  }
  const present = new Set([...graph.nodes.map((n) => n.id), next.node]);
  return {
    ...session,
    phase: "building",
    graph,
    revision,
    history,
    pending_proposal: {
      id: `p-${next.node}`, kind: "step", draft_revision: revision,
      options: ["keep", ...next.alternatives.map((option) => option.id)],
      edges: (WIRES[next.node] ?? []).filter((w) => present.has(w.from_node) && present.has(w.to_node)),
      block: next,
    },
  } as AuthoringSession;
}
