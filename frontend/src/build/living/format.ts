import type { components } from "../../api/schema";
import type { AuthoringSession } from "../../api/types";

/** Small, pure readings of session data that more than one component needs. */

/** A node id as the canvas and the log name it: `star_align` → `STAR_ALIGN`.
 *
 * The node id and not the contract, because it is what the draft, the artifact and every decision
 * record are keyed on — a reader matching the log to the canvas to `pipeline.yml` reads one name.
 */
export const processName = (node: string) => node.toUpperCase();

/** Who decided something, as the three marks the canvas bar and the log tick share. */
export type Author = "resolver" | "model" | "person" | "unknown";

/** The author of an answered proposal, from what the server recorded — never guessed from mode. */
export function authorOf(decision: AuthoringSession["history"][number]): Author {
  return decision.actor_kind === "unknown" || !decision.actor_kind ? "unknown" : decision.actor_kind;
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

export type OfferProgress = components["schemas"]["OfferProgress"];

/** How many of the plan's steps hold a review — `3 of 5 steps reviewed` — or nothing before a
 *  plan exists. **Counted by the server against the plan**, never from the transcript, so a swap
 *  or a step offered again cannot make it run past the end. */
export function progressWords(session: AuthoringSession): string | null {
  const progress = session.progress;
  if (!progress?.total) return null;
  return `${progress.reviewed} of ${progress.total} steps reviewed`;
}

/** `Step 4 of 5`, `Review step 4 of 5 again`, or plain `Step` for an offer made before positions
 *  were recorded — an ordinal nobody stored is not invented. */
export function stepWords(progress: OfferProgress | null | undefined): string {
  if (!progress) return "Step";
  const place = `step ${progress.position} of ${progress.total}`;
  return progress.again ? `Review ${place} again` : place[0].toUpperCase() + place.slice(1);
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

/** **Messages waiting in line** (issue 392): the person turns whose reply is pending behind an
 *  older pending reply. The oldest pending reply is the one being written; the others wait. */
export function queued(session: AuthoringSession): Set<number> {
  const pending = session.turns.filter((t) => t.role === "assistant" && t.state === "pending");
  const behind = new Set(pending.slice(1).map((t) => t.seq));
  const waiting = new Set<number>();
  session.turns.forEach((turn, i) => {
    const reply = session.turns[i + 1];
    if (turn.role === "person" && reply && behind.has(reply.seq)) waiting.add(turn.seq);
  });
  return waiting;
}

/** **The open question follows you** (one builder plan 3): once the person says anything after
 *  it was asked, it leaves the end of the conversation and docks above the composer. */
export function docked(session: AuthoringSession): boolean {
  const asked = session.pending_proposal?.asked_at;
  if (!asked) return false;
  const at = Date.parse(asked);
  return session.turns.some((turn) => turn.role === "person" && Date.parse(turn.at) > at);
}

/** What the open question asks, in one line: the dock's title and the pointer left in its place. */
export function questionTitle(proposal: NonNullable<AuthoringSession["pending_proposal"]>): string {
  const block = proposal.block;
  if (block.kind === "question") return block.asks;
  if (block.kind === "step_proposal") return `Add ${processName(block.node)}?`;
  if (proposal.kind === "goal") return "Is this what you want?";
  return "The question above";
}
