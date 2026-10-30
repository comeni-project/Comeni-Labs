import { useState } from "react";

import { Failed } from "../../ui/States";
import type { AdaptationView } from "./useAdaptation";
import { nameOf } from "./useAdaptation";
import type { useForgeActions } from "./useForgeActions";

type Actions = ReturnType<typeof useForgeActions>;
type Proposal = { move: string; item: string; value?: unknown; because?: string };

const MOVE: Record<string, string> = {
  revise: "AI revises", add: "AI adds", propose_removal: "AI proposes removing",
};

/** The chat beside the pieces (boards 3c, 3d). A message may be about one item; the AI's
 *  proposals arrive as cards the person approves, changes or rejects, never the chat itself. */
export function Chat({ view, actions, about, setAbout }: {
  view: AdaptationView;
  actions: Actions;
  about: string | null;
  setAbout: (key: string | null) => void;
}) {
  const [text, setText] = useState("");
  const current = (key: string) => view.items.find((i) => i.key === key);
  const decide = (key: string, move: "approve" | "reject") => {
    const item = current(key);
    if (item) actions.command.mutate({ move, item: key, expected: item.current_n });
  };

  return (
    <aside aria-label="Chat with the AI"
           className="flex-[1_1_300px] max-w-[400px] bg-surface border border-line rounded-panel flex flex-col min-h-[480px]">
      <div className="px-[18px] py-[14px] border-b border-line">
        <h2 className="m-0 text-[14px] font-semibold">Chat <span className="text-[12px] font-normal text-ink-3">about {view.path}</span></h2>
      </div>
      <ol aria-label="Messages" className="list-none m-0 px-[18px] py-4 flex flex-col gap-3 flex-1 text-[13.5px] leading-[1.5]">
        {view.messages.length === 0 && (
          <li className="text-ink-3">Ask anything about {view.path}, or say what to change.</li>
        )}
        {view.messages.map((m) => (
          <li key={m.seq} className="flex flex-col gap-2">
            <div className={m.role === "person"
              ? "self-end max-w-[92%] bg-now-soft px-[13px] py-[10px] rounded-panel"
              : m.role === "engine"
                ? "self-stretch border border-line rounded-control px-3 py-2 text-[13px] text-ink-2 whitespace-pre-line"
                : "self-start max-w-[92%] bg-paper-2 px-[13px] py-[10px] rounded-panel text-ink-2"}>
              {m.item && <span className="block font-data text-[11.5px] text-action">→ {m.item}</span>}
              {m.content}
              {m.pending && <span className="block text-[12px] text-ink-3">the AI is replying…</span>}
            </div>
            {(m.commands as Proposal[]).map((c, n) => {
              const item = current(c.item);
              const waiting = item && (item.status === "proposed" || item.status === "reopened");
              return (
                <div key={n} className="self-stretch border border-line-2 rounded-control p-3 flex flex-col gap-[6px]">
                  <span className={`text-[12px] ${c.move === "propose_removal" ? "text-needs-you-ink" : "text-measured-ink"}`}>
                    {MOVE[c.move] ?? c.move} · <span className="font-data">{nameOf(c.item)}</span>
                  </span>
                  {c.value !== undefined && c.value !== null && (
                    <span className="font-data text-[12.5px] break-all">{JSON.stringify(c.value)}</span>
                  )}
                  {c.because && <span className="text-[12.5px] text-ink-2">{c.because}</span>}
                  {waiting ? (
                    <span className="flex gap-[6px]">
                      <button type="button" onClick={() => decide(c.item, "approve")}
                              className="px-3 py-[6px] rounded-control bg-action text-on-action text-[12.5px] font-semibold shadow-raise">
                        Approve
                      </button>
                      <button type="button" onClick={() => { decide(c.item, "reject"); setAbout(c.item); }}
                              className="px-3 py-[6px] rounded-control border border-line-2 bg-surface text-[12.5px] text-needs-you-ink">
                        Reject
                      </button>
                    </span>
                  ) : (
                    <span className="text-[12px] text-ink-3">{item?.status === "approved" ? "Approved" : item?.status ?? ""}</span>
                  )}
                </div>
              );
            })}
          </li>
        ))}
      </ol>
      {actions.command.isError && <div className="px-3"><Failed error={actions.command.error} padded={false} /></div>}
      <form className="flex flex-col gap-[6px] p-3 border-t border-line" onSubmit={(e) => {
        e.preventDefault();
        if (!text.trim()) return;
        actions.say.mutate({ content: text, item: about });
        setText("");
      }}>
        {about && (
          <span className="font-data text-[11.5px] text-action">
            about {about} · <button type="button" className="text-ink-3 bg-transparent border-0 p-0 underline" onClick={() => setAbout(null)}>clear</button>
          </span>
        )}
        <span className="flex gap-2">
          <label htmlFor="forge-say" className="sr-only">Message the AI</label>
          <input id="forge-say" value={text} onChange={(e) => setText(e.target.value)}
                 placeholder="Ask, or say what to change"
                 className="flex-1 min-w-0 px-3 py-[10px] border border-line-2 rounded-control" />
          <button type="submit" className="px-[14px] py-[10px] rounded-control bg-ink text-paper font-medium">Send</button>
        </span>
        {actions.say.isError && <Failed error={actions.say.error} padded={false} />}
      </form>
    </aside>
  );
}
