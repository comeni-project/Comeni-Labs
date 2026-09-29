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

/** Whether the goal phase is waiting on the **person**, and why — or `null` while it is not.
 *
 * `understanding` covers two very different moments: a model reading what was said, and nothing
 * happening until the person says something. A refusal stays in `understanding` by design — the
 * way forward is to say it again, not to retry a call that answered — and so does a goal answered
 * *Not quite*. Found by the first walk (issues 110 and 112): both left the page claiming to be reading.
 */
export function waitingOn(session: AuthoringSession): "refused" | "rejected" | null {
  if (session.phase !== "understanding" || session.pending_proposal) return null;
  if (session.turns.some((t) => t.state === "pending")) return null;
  const last = [...session.turns].reverse().find((t) => t.role === "assistant");
  if (!last) return null;
  if (last.blocks.some((b) => b.kind === "notice" && b.notice === "refusal")) return "refused";
  const goal = [...session.history].reverse().find((d) => d.kind === "goal");
  return goal?.state === "rejected" ? "rejected" : null;
}

/** `saved 3s ago`, from nothing but a revision and a clock the caller owns. */
export function phaseWords(session: AuthoringSession): string {
  switch (session.phase) {
    case "understanding":
      return waitingOn(session) ? "waiting for you" : "reading your goal";
    case "gathering":
      return "gathering what it needs";
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
    case "stopped":
      return "stopped: something is missing";
  }
}

/** How many of the blueprint's steps are in the draft — `4 of 7 steps`, or nothing at all. */
export function progressWords(session: AuthoringSession): string | null {
  if (!session.steps_total) return null;
  return `${session.graph.nodes.length} of ${session.steps_total} steps`;
}

type Usage = NonNullable<AuthoringSession["usage"]>;

/** `13.3k tokens · 7 calls`, and `· thinking…` while a call is on its way — or nothing before
 *  the first call, so a new conversation's header carries no *0 tokens* (issue 191). */
export function usageWords(usage: Usage | undefined): string | null {
  if (!usage?.calls) return null;
  const total = usage.input + usage.output;
  const tokens = total >= 1000 ? `${(total / 1000).toFixed(1)}k` : String(total);
  const calls = `${usage.calls} ${usage.calls === 1 ? "call" : "calls"}`;
  return `${tokens} tokens · ${calls}${usage.in_flight ? " · thinking…" : ""}`;
}

const PURPOSE: Record<string, string> = {
  family: "choosing the kind of result",
  goal: "reading your request",
  chat: "answering you",
  gap: "reading your reply",
  tier4: "choosing between tools",
  ask: "phrasing a question",
  readback: "writing the read-back",
};

/** What a model call was for, in the words the page uses. */
export function purposeWords(purpose: string): string {
  return PURPOSE[purpose] ?? purpose;
}
