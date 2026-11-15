import { useEffect, useRef } from "react";

import type { AuthoringSession, DraftGraph } from "../../api/types";
import type { AnsweredStep } from "../useBuilder";
import { AgentThread } from "./AgentThread";
import type { AnswerValue } from "./AgentQuestion";
import { Composer } from "./Composer";
import { processName } from "./format";
import { StepSheet } from "./StepSheet";

/** **One conversation beside the canvas** (#463): the agent's thread, and the composer, never
 *  locked. A step opened from the canvas shows over the thread, and closing it returns there.
 *
 *  **The rail's height is the layout's, never its content's** (`--rail-h` in `main.css`): the
 *  thread scrolls inside it, so a reply landing does not push the page or the canvas around. */
export function ChatPanel({
  session, sending, composer, onCompose, onSay, onAnswer, onRetry, onUpload,
  selected, onSelect, graph, steps, onEdit, onSetParam, onSwitchInput, onWhole, onReviewed, notices,
}: {
  session: AuthoringSession;
  sending: string[];
  composer: string;
  onCompose: (text: string) => void;
  onSay: (text: string) => void;
  onAnswer: (questionId: string, value: AnswerValue) => void;
  onRetry: (seq: number) => void;
  onUpload?: (questionId: string, files: File[]) => Promise<unknown>;
  selected: string | null;
  onSelect: (node: string | null) => void;
  /** The draft as saved — what a step's tools change. */
  graph: DraftGraph;
  /** Each step with what the person typed laid over it. */
  steps: Record<string, AnsweredStep>;
  onEdit: (graph: DraftGraph) => void;
  onSetParam: (node: string, setting: string, value: string, why?: string) => void;
  onSwitchInput?: (contract: string, port: string, state: "off" | "optional" | "required") => void;
  onWhole?: (contract: string, whole: boolean) => void;
  onReviewed: (node: string) => void;
  notices: React.ReactNode;
}) {
  const open = selected !== null && graph.nodes.some((n) => n.id === selected) ? selected : null;
  // An open step closes so the reply is seen.
  const say = (text: string) => {
    if (open) onSelect(null);
    onSay(open ? `About ${processName(open)}: ${text}` : text);
  };
  const choices = session.ai_unreviewed.filter((c) => c.node === open).map((c) => c.what);

  // **Follow the newest line, unless the person scrolled up to read.**
  const scroller = useRef<HTMLDivElement>(null);
  const pinned = useRef(true);
  const last = session.turns.at(-1);
  const size = `${session.turns.length}:${last?.blocks.length ?? 0}:${sending.length}`;
  useEffect(() => {
    const el = scroller.current;
    if (el && pinned.current) el.scrollTop = el.scrollHeight;
  }, [size, open]);

  return (
    <section aria-label="build panel"
             className="living-rail flex flex-col min-h-0 ml-[8px] mr-[28px] mt-[4px] mb-[24px] rounded-panel border border-line overflow-hidden"
             style={{ background: "var(--surface)", height: "var(--rail-h)" }}>
      {notices}
      <div ref={scroller} data-testid="thread-scroll" className="flex-1 min-h-0 px-4 pt-4 pb-4"
           style={{ overflowY: "auto", overflowAnchor: "none" }}
           onScroll={(e) => {
             const el = e.currentTarget;
             pinned.current = el.scrollHeight - el.scrollTop - el.clientHeight < 48;
           }}>
        {open ? (
          <StepSheet node={open} step={steps[open]} graph={graph} onSetParam={onSetParam} onEdit={onEdit}
                     onClose={() => onSelect(null)} onSwitchInput={onSwitchInput} onWhole={onWhole}
                     aiChoices={choices} onReviewed={onReviewed} />
        ) : session.turns.length === 0 && sending.length === 0 ? (
          <p className="m-0 text-[13px] text-ink-2">
            Say what you have and what you want — for example, “12 paired RNA-seq samples and a
            human genome; I want gene counts”.
          </p>
        ) : (
          <AgentThread turns={session.turns} working={session.working} sending={sending}
                       onAnswer={onAnswer} onRetry={onRetry} onUpload={onUpload} />
        )}
      </div>
      <div className="px-[16px] pt-[8px] pb-[16px] border-t" style={{ borderColor: "var(--line)" }}>
        <Composer value={composer} onChange={onCompose} onSend={say} disabled={session.retired}
                  placeholder={open ? "Ask about this step…" : session.working
                    ? "Say more while it works — it reads this next" : "Ask, or say what to change"} />
      </div>
    </section>
  );
}
