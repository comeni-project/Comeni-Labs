import type { Step } from "./progress";
import type { ItemView } from "./useAdaptation";

export const PIECE_HELP: Record<string, string> = {
  questions: "Choose the tool's job first, then what each input and output holds. These answers guide the remaining pieces.",
  contract: "Check the process, the input and output types, and how they connect to the module. Port order follows the process inputs.",
  parameters: "Check each setting's allowed values, default and route into the tool. A missing default may leave a question for the person building a pipeline.",
  vocabulary: "Review each new type, state, measurement or job. These declarations extend the words available to every tool in this registry layer.",
  rules: "Review the ordered conditions, their decisions and citations. Try hypothetical facts below; the server evaluates the stored rule.",
  tests: "Check the supplied inputs, setup, settings and expected outputs. Approving these declarations does not run the tool. Run tests after Assembly.",
};

/** Attempts are durable events: an empty refused piece still has a history. */
export function attemptNote(steps: Step[], piece: string): string | null {
  const start = steps.findLastIndex((s) => s.kind === "started" && s.data.piece === piece && s.data.what === "drafting");
  if (start < 0) return null;
  const next = steps.findIndex((s, n) => n > start && s.kind === "started");
  const attempt = steps.slice(start, next < 0 ? undefined : next);
  if (attempt.some((s) => s.kind === "saved")) return "draft checked";
  return attempt.some((s) => s.kind === "refused") ? "draft refused · try again" : "draft attempted";
}

export function pieceWaiting(items: ItemView[]): number {
  return items.filter((i) => i.status === "proposed" || i.status === "reopened").length;
}
