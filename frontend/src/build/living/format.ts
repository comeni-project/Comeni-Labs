import type { AuthoringSession } from "../../api/types";

/** Small, pure readings of session data that more than one component needs. */

/** A node id as the canvas and the log name it: `star_align` → `STAR_ALIGN`.
 *
 * The node id and not the contract, because it is what the draft, the artifact and every decision
 * record are keyed on — a reader matching the log to the canvas to `pipeline.yml` reads one name.
 */
export const processName = (node: string) => node.toUpperCase();

/** Who decided something, as the three marks the canvas bar and the log tick share. */
export type Author = "resolver" | "model" | "person";

/** The author of an answered proposal, from what the server recorded — never guessed from mode. */
export function authorOf(decision: AuthoringSession["history"][number]): Author {
  const by = decision.by ?? "";
  if (by === "person" || by === "model" || by === "resolver") return by;
  if (decision.kind === "step" && decision.chosen_option && decision.chosen_option !== "keep") {
    return "person";
  }
  if (decision.block.kind === "step_proposal") {
    // A step settled at tiers 1–3 and acknowledged unchanged keeps the resolver as its author;
    // a tier-4 one a person pressed is theirs. Spawn's model choices arrive with `by` naming it.
    return decision.block.tier === 4 ? "person" : "resolver";
  }
  return "person";
}

/** `saved 3s ago`, from nothing but a revision and a clock the caller owns. */
export function phaseWords(session: AuthoringSession): string {
  switch (session.phase) {
    case "understanding":
      return "reading your goal";
    case "goal_review":
      return "check the goal";
    case "resolving":
      return "resolving";
    case "building":
      return "building";
    case "complete":
      return "complete";
    case "failed":
      return "waiting";
  }
}

/** How many of the blueprint's steps are in the draft — `4 of 7 steps`, or nothing at all. */
export function progressWords(session: AuthoringSession): string | null {
  if (!session.steps_total) return null;
  return `${session.graph.nodes.length} of ${session.steps_total} steps`;
}
