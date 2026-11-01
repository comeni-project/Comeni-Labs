export type Step = { seq: number; kind: string; data: Record<string, unknown>; at: string };
export type Line = { key: string; label: string; state: "done" | "now" | "waiting" | "refused"; detail?: string };
export type Progress = { title: string; steps: Line[]; tokens: { sent: number; received: number } | null; since: string | null };

const titled = (what: unknown, piece: unknown) =>
  (what === "replying" ? "Writing a reply" : `Drafting the ${String(piece ?? "piece")}`);

/** The latest piece of work, as a person reads it: what has happened, what is happening, what is
 *  left. A refused attempt appears when it happens, not as one message after the last. */
export function progressOf(all: Step[], piece?: string | null): Progress {
  const from = all.findLastIndex((s) => s.kind === "started");
  const steps = from < 0 ? [] : all.slice(from);
  const lines: Line[] = [{ key: "read", label: "Read the module", state: "done" }];
  let sent = 0;
  let received = 0;
  let counted = false;
  let checking = false;
  let finished = false;
  for (const { seq, kind, data } of steps) {
    if (kind === "asking") {
      lines.push({ key: `ask-${seq}`, state: "now",
                   label: `Asking ${String(data.model)}, attempt ${String(data.attempt)} of ${String(data.attempts)}` });
      checking = false;
    }
    if (kind === "called" && typeof data.input_tokens === "number") {
      counted = true;
      sent += data.input_tokens;
      received += typeof data.output_tokens === "number" ? data.output_tokens : 0;
    }
    if (kind === "checking") {
      lines[lines.length - 1].state = "done";
      checking = true;
    }
    if (kind === "refused") {
      const last = lines[lines.length - 1];
      lines[lines.length - 1] = { ...last, state: "refused", label: `Attempt ${String(data.attempt)} was refused`,
                                  detail: (data.problems as string[])[0] };
      checking = false;
    }
    if (kind === "saved") finished = true;
  }
  lines.push({ key: "check", label: "The engine checks the reply",
               state: finished ? "done" : checking ? "now" : "waiting" });
  return { title: titled(steps[0]?.data.what ?? "drafting", steps[0]?.data.piece ?? piece), steps: lines,
           tokens: counted ? { sent, received } : null, since: steps[0]?.at ?? null };
}

/** How long something has run, as a clock reads it. */
export function elapsed(from: string, now: number): string {
  const seconds = Math.max(0, Math.floor((now - Date.parse(from)) / 1000));
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
}

export type Outcome = { tone: "none" | "some"; label: string; note?: string };

/** What a reply did, from the commands it sent and never from its words: a promise and a change
 *  must not look alike (#423). */
export function outcomeOf(message: { role: string; commands: unknown[]; pending: boolean }): Outcome | null {
  if (message.role !== "ai") return null;
  const n = message.commands.length;
  if (n === 0) return { tone: "none", label: "No changes made", note: "It sent nothing the engine could apply." };
  return { tone: "some", label: `${n} ${n === 1 ? "change" : "changes"} proposed` };
}
