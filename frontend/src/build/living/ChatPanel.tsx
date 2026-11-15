import { useEffect, useRef } from "react";

import type { AuthoringSession } from "../../api/types";
import { AgentThread } from "./AgentThread";
import type { AnswerValue } from "./AgentQuestion";
import { Composer } from "./Composer";

/** **One conversation beside the canvas** (#463): the agent's thread, and the composer, never
 *  locked. A step's tools open beside the step on the canvas (#499), never over the thread.
 *
 *  **The rail's height is the layout's, never its content's** (`--rail-h` in `main.css`): the
 *  thread scrolls inside it, so a reply landing does not push the page or the canvas around. */
export function ChatPanel({
  session, sending, composer, onCompose, onSay, onAnswer, onRetry, onUpload, notices, onStep, embedded = false,
}: {
  session: AuthoringSession;
  sending: string[];
  composer: string;
  onCompose: (text: string) => void;
  onSay: (text: string) => void;
  onAnswer: (questionId: string, value: AnswerValue) => void;
  onRetry: (seq: number) => void;
  onUpload?: (questionId: string, files: File[]) => Promise<unknown>;
  notices: React.ReactNode;
  /** Show a step an answer used. */
  onStep?: (node: string) => void;
  /** Drawn inside another page (the pipeline file's AI panel): no frame of its own. */
  embedded?: boolean;
}) {
  // **Follow the newest line, unless the person scrolled up to read.**
  const scroller = useRef<HTMLDivElement>(null);
  const pinned = useRef(true);
  const last = session.turns.at(-1);
  const size = `${session.turns.length}:${last?.blocks.length ?? 0}:${sending.length}`;
  useEffect(() => {
    const el = scroller.current;
    if (el && pinned.current) el.scrollTop = el.scrollHeight;
  }, [size]);

  return (
    <section aria-label={embedded ? "the conversation" : "build panel"}
             className={embedded ? "flex flex-col min-h-0 h-full overflow-hidden"
               : "living-rail flex flex-col min-h-0 ml-[8px] mr-[28px] mt-[4px] mb-[24px] rounded-panel border border-line overflow-hidden"}
             style={{ background: "var(--surface)", height: embedded ? undefined : "var(--rail-h)" }}>
      {notices}
      <div ref={scroller} data-testid="thread-scroll" className="flex-1 min-h-0 px-4 pt-4 pb-4"
           style={{ overflowY: "auto", overflowAnchor: "none" }}
           onScroll={(e) => {
             const el = e.currentTarget;
             pinned.current = el.scrollHeight - el.scrollTop - el.clientHeight < 48;
           }}>
        {session.turns.length === 0 && sending.length === 0 ? (
          <p className="m-0 text-[13px] text-ink-2">
            Say what you have and what you want — for example, “12 paired RNA-seq samples and a
            human genome; I want gene counts”.
          </p>
        ) : (
          <AgentThread turns={session.turns} working={session.working} sending={sending}
                       onAnswer={onAnswer} onRetry={onRetry} onUpload={onUpload} onStep={onStep} />
        )}
      </div>
      <div className="px-[16px] pt-[8px] pb-[16px] border-t" style={{ borderColor: "var(--line)" }}>
        <Composer value={composer} onChange={onCompose} onSend={onSay} disabled={session.retired}
                  placeholder={session.working
                    ? "Say more while it works — it reads this next" : "Ask, or say what to change"} />
      </div>
    </section>
  );
}
