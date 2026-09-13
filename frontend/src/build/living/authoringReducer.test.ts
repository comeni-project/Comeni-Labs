import { describe, expect, it } from "vitest";

import type { AuthoringProposal, AuthoringSession, DraftGraph } from "../../api/types";
import {
  authoringReducer,
  initialAuthoring,
  isWaiting,
  noticeFrom,
  visibleGraph,
  type AuthoringAction,
  type AuthoringState,
} from "./authoringReducer";

/** Plain objects in, plain objects out — Task 8 asks for reducer tests before component tests, so
 *  every transition here is checkable without React, a network, or a timer. */

const INDEX = { id: "star_genomegenerate", contract_id: "nf-core/star/genomegenerate@1.11.0" };
const ALIGN = "nf-core/star/align@1.11.0";
const INDEX_WIRE = {
  from_node: "star_genomegenerate",
  from_port: "index",
  to_node: "star_align",
  to_port: "index",
};

function step(id: string, node: string, contract: string, edges = [INDEX_WIRE]): AuthoringProposal {
  return {
    id,
    kind: "step",
    draft_revision: 2,
    options: ["alt_1", "keep"],
    edges,
    block: {
      kind: "step_proposal",
      id: `step-${node}`,
      node,
      contract,
      produces: ["alignment.bam"],
      reason: "the rule for 150bp reads",
      tier: 3,
      alternatives: [{ id: "alt_1", label: "nf-core/hisat2/align@2.2.2", recommended: false }],
    },
  } as AuthoringProposal;
}

function session(overrides: Partial<AuthoringSession> = {}): AuthoringSession {
  return {
    id: "s1",
    draft_id: "d1",
    mode: "build",
    phase: "building",
    failed_from: null,
    goal: null,
    revision: 2,
    graph: { nodes: [{ ...INDEX, params: [] }], edges: [] },
    row_version: 7,
    model_configured: true,
    turns: [],
    pending_proposal: step("p-align", "star_align", ALIGN),
    ...overrides,
  } as AuthoringSession;
}

const run = (actions: AuthoringAction[], from: AuthoringState = initialAuthoring) =>
  actions.reduce(authoringReducer, from);

const shape = (g: DraftGraph) => ({
  nodes: g.nodes.map((n) => [n.id, n.contract_id]).sort(),
  edges: g.edges.map((e) => `${e.from_node}.${e.from_port}->${e.to_node}.${e.to_port}`).sort(),
});

describe("the checkpoint", () => {
  it("draws the same graph from the optimistic sequence as from the server's snapshot after it", () => {
    const offered = session();
    const optimistic = run([
      { type: "snapshot", session: offered },
      { type: "accept", proposal: offered.pending_proposal!, option: "keep", expectedRevision: 2 },
    ]);

    // What the server committed for the same acceptance: the node and the wire to the index.
    const committed = session({
      revision: 3,
      graph: {
        nodes: [{ ...INDEX, params: [] }, { id: "star_align", contract_id: ALIGN, params: [] }],
        edges: [INDEX_WIRE],
      },
      pending_proposal: step("p-sort", "samtools_sort", "nf-core/samtools/sort@1.21.0", []),
    });
    const reconciled = run(
      [
        { type: "decided", proposalId: "p-align", answer: { phase: "building", revision: 3,
          next_proposal: "p-sort", queued: false } },
        { type: "snapshot", session: committed },
      ],
      optimistic,
    );
    const fresh = run([{ type: "snapshot", session: committed }]);

    expect(shape(visibleGraph(optimistic))).toEqual(shape(visibleGraph(fresh)));
    expect(shape(visibleGraph(reconciled))).toEqual(shape(visibleGraph(fresh)));
    expect(reconciled.optimistic).toBeNull();
  });
});

describe("optimistic acceptance", () => {
  it("draws the step and its wires before the server answers, and disables only that proposal", () => {
    const offered = session();
    const state = run([
      { type: "snapshot", session: offered },
      { type: "accept", proposal: offered.pending_proposal!, option: "keep", expectedRevision: 2 },
    ]);

    expect(visibleGraph(state).nodes.map((n) => n.id)).toContain("star_align");
    expect(visibleGraph(state).edges).toEqual([INDEX_WIRE]);
    expect(state.inFlight).toBe("p-align");
    expect(state.selected).toBe("star_align");
  });

  it("keeps the drawing while a poll arrives before the answer does", () => {
    // A poll racing the POST shows the proposal still pending at the old revision. Retiring the
    // optimistic step then would make it blink out and back in.
    const offered = session();
    const state = run([
      { type: "snapshot", session: offered },
      { type: "accept", proposal: offered.pending_proposal!, option: "keep", expectedRevision: 2 },
      { type: "snapshot", session: offered },
    ]);
    expect(state.optimistic).not.toBeNull();
  });

  it("retires the drawing when a poll shows the commit before the request has returned", () => {
    // **The race only the revision rule handles.** The server committed and offered the next
    // step, and a poll saw it before the POST's own response resolved — so the request is still
    // in flight and the proposal id alone cannot say the acceptance landed. The revision can.
    // Found by a mutation: disabling this comparison failed nothing until this test existed.
    const offered = session();
    const committed = session({
      revision: 3,
      graph: {
        nodes: [{ ...INDEX, params: [] }, { id: "star_align", contract_id: ALIGN, params: [] }],
        edges: [INDEX_WIRE],
      },
      pending_proposal: step("p-sort", "samtools_sort", "nf-core/samtools/sort@1.21.0", []),
    });
    const state = run([
      { type: "snapshot", session: offered },
      { type: "accept", proposal: offered.pending_proposal!, option: "keep", expectedRevision: 2 },
      { type: "snapshot", session: committed },
    ]);
    expect(state.inFlight).toBe("p-align");
    expect(state.optimistic).toBeNull();
  });

  it("does not guess the wires of an alternative", () => {
    const offered = session();
    const state = run([
      { type: "snapshot", session: offered },
      { type: "accept", proposal: offered.pending_proposal!, option: "alt_1", expectedRevision: 2 },
    ]);
    expect(state.optimistic).toBeNull();
    expect(state.inFlight).toBe("p-align");
  });

  it("emits the domain events motion follows, in order", () => {
    const offered = session();
    const state = run([
      { type: "snapshot", session: offered },
      { type: "accept", proposal: offered.pending_proposal!, option: "keep", expectedRevision: 2 },
    ]);
    expect(state.events.map((e) => e.kind)).toEqual([
      "proposal_shown",
      "proposal_accepted",
      "edge_committed",
    ]);
  });
});

describe("reconciliation", () => {
  it("discards the drawing on a refusal and shows the server's notice", () => {
    const offered = session();
    const state = run([
      { type: "snapshot", session: offered },
      { type: "accept", proposal: offered.pending_proposal!, option: "keep", expectedRevision: 2 },
      {
        type: "refused",
        proposalId: "p-align",
        detail: "MI0201: this draft moved while you were looking at it\n  re-read it",
      },
    ]);

    expect(visibleGraph(state).nodes.map((n) => n.id)).not.toContain("star_align");
    expect(state.notice).toEqual({
      code: "MI0201",
      text: "this draft moved while you were looking at it",
    });
    expect(state.inFlight).toBeNull();
  });

  it("never lets a refusal for one proposal erase an acceptance of another", () => {
    const offered = session();
    const state = run([
      { type: "snapshot", session: offered },
      { type: "accept", proposal: offered.pending_proposal!, option: "keep", expectedRevision: 2 },
      { type: "refused", proposalId: "p-something-else", detail: "MI0203: already settled" },
    ]);
    expect(state.optimistic?.proposalId).toBe("p-align");
  });

  it("retires a drawing whose proposal vanished without the revision moving", () => {
    // Withdrawn or marked stale on the server: what was drawn never happened.
    const offered = session();
    const withdrawn = session({ pending_proposal: step("p-fresh", "star_align", ALIGN) });
    const state = run([
      { type: "snapshot", session: offered },
      { type: "accept", proposal: offered.pending_proposal!, option: "keep", expectedRevision: 2 },
      { type: "decided", proposalId: "p-align", answer: { phase: "building", revision: 2,
        next_proposal: null, queued: false } },
      { type: "snapshot", session: withdrawn },
    ]);
    expect(state.optimistic).toBeNull();
  });

  it("clears a stale preview when a new proposal is shown", () => {
    const offered = session();
    const next = session({ pending_proposal: step("p-sort", "samtools_sort", "x@1", []) });
    const state = run([
      { type: "snapshot", session: offered },
      { type: "preview", option: "alt_1" },
      { type: "snapshot", session: next },
    ]);
    expect(state.previewed).toBeNull();
  });
});

describe("the small states", () => {
  it("empties the composer once a message is sent, and not before", () => {
    const typed = run([{ type: "compose", text: "why STAR?" }]);
    expect(typed.composer).toBe("why STAR?");
    const sent = run([{ type: "sent", text: "why STAR?" }], typed);
    expect(sent.composer).toBe("");
    expect(sent.saying).toBe("why STAR?");
  });

  it("forgets an animation once it has played", () => {
    const offered = session();
    const shown = run([{ type: "snapshot", session: offered }]);
    const played = run([{ type: "consumed", seq: shown.events[0].seq }], shown);
    expect(played.events).toEqual([]);
  });

  it("reads a notice with no code as words rather than inventing one", () => {
    expect(noticeFrom("the network went away")).toEqual({
      code: null,
      text: "the network went away",
    });
  });
});

describe("when to poll", () => {
  it("polls while a turn is pending or a Spawn blueprint is resolving, and at no other time", () => {
    const pending = { seq: 1, role: "assistant", state: "pending", text: "", blocks: [],
      base_revision: 0 } as AuthoringSession["turns"][number];
    const answered = { ...pending, state: "answered" } as AuthoringSession["turns"][number];

    expect(isWaiting(session({ turns: [pending] }))).toBe(true);
    expect(isWaiting(session({ phase: "resolving" }))).toBe(true);
    expect(isWaiting(session({ turns: [answered] }))).toBe(false);
    expect(isWaiting(session({ phase: "failed", turns: [answered] }))).toBe(false);
    expect(isWaiting(null)).toBe(false);
  });
});
