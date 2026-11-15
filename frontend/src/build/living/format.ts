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
