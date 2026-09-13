import type {
  AuthoringDecided,
  AuthoringProposal,
  AuthoringSession,
  DraftEdge,
  DraftGraph,
  DraftNode,
} from "../../api/types";
import { withEdge, withNode } from "../graphOps";

/** What the living builder is doing between one server answer and the next.
 *
 * **Server data is not here.** The session itself lives in TanStack Query and arrives as
 * `snapshot`; this holds only what the server does not know — which option is being previewed,
 * which step is selected, what is half-typed, what is animating, and the one acceptance that has
 * been drawn before the server confirmed it. Mirroring the whole response into state would give
 * the page two copies of the truth and a reconciliation problem for every field.
 *
 * **Pure.** No timers, no fetches, no React. Every transition is a plain object in and a plain
 * object out, which is what lets the checkpoint be a test: the graph drawn from an optimistic
 * sequence and the graph drawn from the server's snapshot afterwards must be the same graph.
 */

/** The domain events motion follows — §1.11. Never fetch completion, never model tokens. */
export type MotionKind =
  | "proposal_shown"
  | "proposal_accepted"
  | "edge_committed"
  | "parameter_committed"
  | "proposal_rejected"
  | "validation_changed";

export type MotionEvent = { seq: number; kind: MotionKind; subject: string };

/** An acceptance drawn before the server said yes. */
export type Optimistic = {
  proposalId: string;
  /** The revision the request was made against. The server's answer must exceed it. */
  expectedRevision: number;
  node: DraftNode;
  edges: DraftEdge[];
};

export type ServerNotice = { code: string | null; text: string };

export type AuthoringState = {
  snapshot: AuthoringSession | null;
  optimistic: Optimistic | null;
  /** The proposal whose request is in flight. **Only that proposal is disabled.** */
  inFlight: string | null;
  previewed: string | null;
  selected: string | null;
  composer: string;
  notice: ServerNotice | null;
  events: MotionEvent[];
  nextSeq: number;
};

export const initialAuthoring: AuthoringState = {
  snapshot: null,
  optimistic: null,
  inFlight: null,
  previewed: null,
  selected: null,
  composer: "",
  notice: null,
  events: [],
  nextSeq: 1,
};

export type AuthoringAction =
  | { type: "snapshot"; session: AuthoringSession }
  | { type: "accept"; proposal: AuthoringProposal; option: string; expectedRevision: number }
  | { type: "reject"; proposalId: string }
  | { type: "decided"; proposalId: string; answer: AuthoringDecided }
  | { type: "refused"; proposalId: string; detail: string }
  | { type: "preview"; option: string | null }
  | { type: "select"; node: string | null }
  | { type: "compose"; text: string }
  | { type: "sent" }
  | { type: "consumed"; seq: number }
  | { type: "dismiss" };

const KEEP = "keep";

function emit(state: AuthoringState, kind: MotionKind, subject: string): AuthoringState {
  return {
    ...state,
    events: [...state.events, { seq: state.nextSeq, kind, subject }],
    nextSeq: state.nextSeq + 1,
  };
}

/** A step proposal's block, or `null` for anything else — a goal summary has no node to draw. */
function stepOf(proposal: AuthoringProposal): { node: string; contract: string } | null {
  const block = proposal.block;
  return block.kind === "step_proposal" ? { node: block.node, contract: block.contract } : null;
}

/** `MI0201: …` → `{ code: "MI0201", text: "…" }`. A detail with no code keeps its words. */
export function noticeFrom(detail: string): ServerNotice {
  const match = /^(M[A-Z]\d{4}):\s*(.*)$/s.exec(detail);
  return match ? { code: match[1], text: match[2].split("\n")[0] } : { code: null, text: detail };
}

export function authoringReducer(state: AuthoringState, action: AuthoringAction): AuthoringState {
  switch (action.type) {
    case "snapshot": {
      const before = state.snapshot?.pending_proposal?.id ?? null;
      const now = action.session.pending_proposal?.id ?? null;
      let next: AuthoringState = { ...state, snapshot: action.session };

      // **Reconcile by proposal id and revision.** The optimistic acceptance is retired only when
      // the server shows a revision past the one the request was made against — the draft now
      // holds the step — or when the proposal is no longer pending without the revision moving,
      // which means it was refused or withdrawn and what was drawn never happened.
      const drawn = state.optimistic;
      if (drawn !== null) {
        const landed = action.session.revision > drawn.expectedRevision;
        const stillPending = now === drawn.proposalId;
        if (landed || (!stillPending && state.inFlight !== drawn.proposalId)) {
          next = { ...next, optimistic: null };
        }
      }
      if (now !== null && now !== before) {
        next = { ...emit(next, "proposal_shown", now), previewed: null };
      }
      return next;
    }

    case "accept": {
      const step = stepOf(action.proposal);
      const base = { ...state, inFlight: action.proposal.id, notice: null };
      if (step === null) return emit(base, "proposal_accepted", action.proposal.id);
      // Only the proposal *as offered* is drawn ahead of the server. An alternative's wires
      // depend on its ports, and drawing a guess would be a picture the server then corrects.
      if (action.option !== KEEP) return emit(base, "proposal_accepted", step.node);
      let next: AuthoringState = {
        ...base,
        optimistic: {
          proposalId: action.proposal.id,
          expectedRevision: action.expectedRevision,
          node: { id: step.node, contract_id: step.contract, params: [] },
          edges: action.proposal.edges ?? [],
        },
        selected: step.node,
      };
      next = emit(next, "proposal_accepted", step.node);
      for (const edge of action.proposal.edges ?? []) {
        next = emit(next, "edge_committed", `${edge.from_node}.${edge.from_port}->${edge.to_node}`);
      }
      return next;
    }

    case "reject":
      return emit({ ...state, inFlight: action.proposalId, notice: null }, "proposal_rejected",
        action.proposalId);

    case "decided":
      // The request is done; the drawing stays until a snapshot shows the revision it produced.
      return state.inFlight === action.proposalId ? { ...state, inFlight: null } : state;

    case "refused": {
      // **Discard only what this proposal drew.** A refusal for one proposal must never erase an
      // acceptance of another — that would be silently overwriting newer work.
      const mine = state.optimistic?.proposalId === action.proposalId;
      return emit(
        {
          ...state,
          optimistic: mine ? null : state.optimistic,
          inFlight: state.inFlight === action.proposalId ? null : state.inFlight,
          notice: noticeFrom(action.detail),
        },
        "validation_changed",
        action.proposalId,
      );
    }

    case "preview":
      return { ...state, previewed: action.option };
    case "select":
      return { ...state, selected: action.node };
    case "compose":
      return { ...state, composer: action.text };
    case "sent":
      return { ...state, composer: "" };
    case "consumed":
      return { ...state, events: state.events.filter((e) => e.seq !== action.seq) };
    case "dismiss":
      return { ...state, notice: null };
  }
}

const EMPTY: DraftGraph = { nodes: [], edges: [] };

/** The graph the canvas draws: the server's draft, plus an acceptance it has not confirmed yet.
 *
 * **Through `graphOps`, the same functions a hand-drawn edit uses**, so a step accepted in the
 * conversation and a step dropped on the canvas become the same graph by the same rules.
 */
export function visibleGraph(state: AuthoringState): DraftGraph {
  const base = state.snapshot?.graph ?? EMPTY;
  const drawn = state.optimistic;
  if (drawn === null) return base;
  return drawn.edges.reduce(withEdge, withNode(base, drawn.node));
}

/** Whether the page should keep asking the server. **Only while something is on its way.** */
export function isWaiting(session: AuthoringSession | null | undefined): boolean {
  if (!session) return false;
  if (session.turns.some((turn) => turn.state === "pending")) return true;
  // A Spawn blueprint resolves on the AI worker; the session sits in `resolving` until it lands.
  return session.phase === "resolving";
}
