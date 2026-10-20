import type { AuthoringSession } from "../../api/types";

export type Stage = "describe" | "build";

const DESCRIBING = new Set<AuthoringSession["phase"]>(["understanding", "gathering", "goal_review", "resolving"]);

/** **Which page the session is on**, read from the session alone: *describe* while there is nothing
 *  to draw yet, *build* once there is. The pacing question is asked in the building phase but
 *  before any step, so it is still describe's; a stop or failure stays where it happened. */
export function stageOf(session: AuthoringSession): Stage {
  if (DESCRIBING.has(session.phase)) return "describe";
  if (session.pending_proposal?.kind === "pacing") return "describe";
  const built = session.graph.nodes.length > 0
    || session.history.some((d) => d.state === "accepted" && d.block.kind === "step_proposal");
  return built || session.phase === "building" || session.phase === "complete" ? "build" : "describe";
}
