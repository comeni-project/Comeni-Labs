import { useEffect, useRef, useState } from "react";

import { Composer } from "../build/living/Composer";
import { Failed } from "../ui/States";
import { describe, waiting } from "./items";
import { QuestionAnswer } from "./QuestionAnswer";
import { progressOf } from "./progress";
import type { AdaptationView } from "./useAdaptation";
import type { useForgeActions } from "./useForgeActions";
import { useForgeSteps } from "./useForgeSteps";

type Actions = ReturnType<typeof useForgeActions>;

/** **Assistant** (board "6 · Forging"): the conversation about this tool — what you asked, what
 *  the AI did and changed, how much it cost — and the box to ask or say what to change. A message
 *  sent while a part is selected is about that part. */
export function Assistant({ view, about, actions }: { view: AdaptationView; about: string | null; actions: Actions }) {
  const [text, setText] = useState("");
  const scroller = useRef<HTMLDivElement>(null);
  const pinned = useRef(true);
  const working = view.phase === "drafting" || view.phase === "asking" || view.messages.some((m) => m.pending);
  const steps = useForgeSteps(view.id, working);
  const progress = progressOf(steps, view.next_piece);
  const questions = view.items.filter((item) => item.key.startsWith("questions:") && waiting(item));
  const calls = steps.filter((s) => s.kind === "called").length;
  const tokens = progress.tokens ? progress.tokens.sent + progress.tokens.received : 0;
  const item = about ? view.items.find((i) => i.key === about) : undefined;
  // An engine notice said again and again is said once.
  const messages = view.messages.filter((m, n, all) => m.role !== "engine"
    || (!m.resolved && !(all[n - 1]?.role === "engine" && all[n - 1]?.content === m.content)));
  useEffect(() => {
    if (pinned.current && scroller.current) scroller.current.scrollTop = scroller.current.scrollHeight;
  }, [messages.length, messages.at(-1)?.content, steps.length, questions.length]);

  return (
    <div className="flex flex-col min-h-0 h-[min(640px,calc(100dvh-220px))]">
      <div ref={scroller} onScroll={(event) => {
        const element = event.currentTarget;
        pinned.current = element.scrollHeight - element.scrollTop - element.clientHeight < 48;
      }} className="flex-1 min-h-0 overflow-y-auto overflow-x-hidden flex flex-col gap-3 p-4 break-words">
        {messages.length === 0 && !working && questions.length === 0 && <p className="m-0 text-[13px] text-ink-3">Ask me to draft this tool’s inputs, outputs and settings, or tell me what to change.</p>}
        {messages.map((m) => (
          m.role === "person" ? (
            <div key={m.seq} className="self-end max-w-[85%] px-3 py-2 rounded-panel bg-now-soft text-[13px] text-ink whitespace-pre-wrap">{m.content}</div>
          ) : m.role === "ai" ? (
            <div key={m.seq} className="flex flex-col gap-1 text-[13px] text-ink">
              <span className="whitespace-pre-wrap">{m.pending ? "…" : m.content}</span>
              {m.commands.length > 0 && (
                <span className="flex flex-wrap gap-1">
                  {m.commands.map((c, n) => {
                    const key = typeof c.item === "string" ? c.item : "";
                    const known = view.items.find((i) => i.key === key);
                    return <span key={n} className="px-2 py-[1px] rounded-full border border-line text-[11.5px] text-ink-2">{known ? describe(known).title : key || String(c.move ?? "")}</span>;
                  })}
                </span>
              )}
            </div>
          ) : (
            <p key={m.seq} className="m-0 text-[12px] text-ink-3">{m.content}</p>
          )
        ))}
        {steps.length > 0 && <details className="text-[12px] text-ink-3">
          <summary className="cursor-pointer">How I got here · {steps.length} events</summary>
          <ul className="list-none m-0 p-0 pt-2 flex flex-col gap-2">
            {progress.steps.map((step) => <li key={step.key} className="flex flex-col gap-1">
              <span>{step.state === "done" ? "✓ " : step.state === "refused" ? "! " : "· "}{step.label}</span>
              {step.detail && <span className="text-needs-you-ink">{step.detail}</span>}
            </li>)}
          </ul>
        </details>}
        {working && <div role="status" className="flex items-center gap-2 text-[13px] text-now-ink">
          <span aria-hidden className="w-2 h-2 rounded-full bg-now run-status-pulse shrink-0" />
          {view.messages.some((message) => message.pending) ? "Working on your message…"
            : `Drafting ${view.next_piece === "contract" ? "inputs and outputs" : view.next_piece ?? "the next part"}…`}
        </div>}
        {questions.map((question) => <section key={`${question.key}:${question.current_n}`} className="flex flex-col gap-3 p-3 rounded-panel border border-now-line bg-surface-2">
          <h3 className="m-0 text-[13px] font-semibold text-ink">{describe(question).title}</h3>
          <QuestionAnswer item={question} actions={actions} />
        </section>)}
        {!working && questions.length === 0 && view.next_piece && <p className="m-0 text-[12px] text-ink-3">
          Next: {view.next_piece === "contract" ? "inputs and outputs" : view.next_piece}. Ask me to draft it, or describe your changes.
        </p>}
        {calls > 0 && <span className="text-[11.5px] text-ink-3">{tokens ? `${(tokens / 1000).toFixed(1)}k tokens · ` : ""}{calls} call{calls === 1 ? "" : "s"}</span>}
      </div>
      <div className="shrink-0 flex flex-col gap-1 p-3 border-t border-line">
        {item && <span className="text-[11.5px] text-ink-3">About {describe(item).title}</span>}
        <Composer value={text} onChange={setText} disabled={actions.say.isPending} placeholder="Ask, or say what to change"
                  onSend={(content) => actions.say.mutate({ content, item: about }, { onSuccess: () => setText("") })} />
        {actions.say.isError && <Failed error={actions.say.error} padded={false} />}
      </div>
    </div>
  );
}
