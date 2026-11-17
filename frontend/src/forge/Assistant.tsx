import { useState } from "react";

import { Composer } from "../build/living/Composer";
import { Failed } from "../ui/States";
import { describe } from "./items";
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
  const working = view.phase === "drafting" || view.phase === "asking" || view.messages.some((m) => m.pending);
  const steps = useForgeSteps(view.id, working);
  const progress = progressOf(steps);
  const calls = steps.filter((s) => s.kind === "called").length;
  const tokens = progress.tokens ? progress.tokens.sent + progress.tokens.received : 0;
  const item = about ? view.items.find((i) => i.key === about) : undefined;
  // An engine notice said again and again is said once.
  const messages = view.messages.filter((m, n, all) => m.role !== "engine"
    || (!m.resolved && !(all[n - 1]?.role === "engine" && all[n - 1]?.content === m.content)));

  return (
    <div className="flex flex-col h-[640px]">
      <div className="flex-1 overflow-y-auto overflow-x-hidden flex flex-col gap-3 p-4 break-words">
        {messages.length === 0 && <p className="m-0 text-[13px] text-ink-3">Ask about this tool, or say what to change.</p>}
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
        {calls > 0 && <span className="text-[11.5px] text-ink-3">{tokens ? `${(tokens / 1000).toFixed(1)}k tokens · ` : ""}{calls} call{calls === 1 ? "" : "s"}</span>}
      </div>
      <div className="flex flex-col gap-1 p-3 border-t border-line">
        {item && <span className="text-[11.5px] text-ink-3">About {describe(item).title}</span>}
        <Composer value={text} onChange={setText} disabled={working || actions.say.isPending} placeholder="Ask, or say what to change"
                  onSend={(content) => actions.say.mutate({ content, item: about }, { onSuccess: () => setText("") })} />
        {actions.say.isError && <Failed error={actions.say.error} padded={false} />}
      </div>
    </div>
  );
}
