import { Fragment, useRef, type ReactNode } from "react";

import type { AuthoringTurn } from "../../api/types";
import { AgentQuestion, type AnswerValue } from "./AgentQuestion";
import { Secondary } from "./blocks/parts";
import { ToolTrail, type TrailStep } from "./ToolTrail";

/** **The conversation with the builder agent** (#463): the person's words, and each of the
 *  agent's turns as what it did (its working trail), what it said, and what it asks. Nothing here
 *  is a stage or a form the person must get through; the canvas beside it is the pipeline. */
export function AgentThread({ turns, working, sending = [], onAnswer, onRetry, onUpload }: {
  turns: AuthoringTurn[];
  /** Whether the agent is working on a turn now. */
  working: boolean;
  /** Messages sent and not yet in the transcript, drawn at once. */
  sending?: string[];
  onAnswer: (questionId: string, value: AnswerValue) => void;
  onRetry: (seq: number) => void;
  onUpload?: (questionId: string, files: File[]) => Promise<unknown>;
}) {
  // **Only the newest question is answerable**: once the person has said anything after it, the
  // conversation has moved on and the agent will ask again if it still needs to know.
  const lastPerson = turns.reduce((seq, t) => (t.role === "person" ? Math.max(seq, t.seq) : seq), -1);
  // **What was there when the page opened stays still**; an item that arrives after fades in.
  const opened = useRef<Set<number> | null>(null);
  if (opened.current === null) opened.current = new Set(turns.map((t) => t.seq));
  // A person's words faded in as they were sent; only the agent's turns fade in on arrival.
  const arriving = (turn: AuthoringTurn) =>
    turn.role === "assistant" && !opened.current!.has(turn.seq) ? " agent-arrive" : "";
  return (
    <ol role="log" aria-label="conversation" className="m-0 p-0 flex flex-col gap-4">
      {turns.map((turn) => (
        <li key={turn.seq} className={`list-none flex flex-col${arriving(turn)}`}>
          {turn.role === "person"
            ? <Said text={turn.text} />
            : <AgentTurn turn={turn} answerable={turn.seq > lastPerson && !working}
                         onAnswer={onAnswer} onRetry={onRetry} onUpload={onUpload} />}
        </li>
      ))}
      {sending.map((text, i) => (
        <li key={`sending-${i}`} className="list-none flex flex-col agent-arrive">
          <Said text={text} pending />
        </li>
      ))}
    </ol>
  );
}

function Said({ text, pending = false }: { text: string; pending?: boolean }) {
  return (
    <div className="self-end max-w-[85%] px-3 py-2 rounded-panel text-[13.5px] leading-[1.55] text-ink whitespace-pre-wrap"
         style={{ background: "var(--now-soft)", opacity: pending ? 0.7 : undefined }}>
      {text}
    </div>
  );
}

function AgentTurn({ turn, answerable, onAnswer, onRetry, onUpload }: {
  turn: AuthoringTurn;
  answerable: boolean;
  onAnswer: (questionId: string, value: AnswerValue) => void;
  onRetry: (seq: number) => void;
  onUpload?: (questionId: string, files: File[]) => Promise<unknown>;
}) {
  // **The trail is the working; the rest is the answer** (#504): tools and what the agent said
  // beside them, in order, then its words, notices and question.
  const trail = turn.blocks.filter((b): b is TrailStep =>
    b.kind === "tool" || (b.kind === "message" && b.narration));
  const rest = turn.blocks.filter((b) => !trail.includes(b as TrailStep));
  return (
    <div className="flex flex-col gap-[10px] min-w-0">
      <ToolTrail steps={trail} live={turn.state === "pending"} />
      {rest.map((block) => {
        switch (block.kind) {
          case "message":
            return <Prose key={block.id} text={block.text} />;
          case "notice":
            return (
              <p key={block.id} role={turn.state === "failed" ? "alert" : undefined}
                 className="m-0 text-[12.5px] text-ink-2">
                {block.text}
                {block.code && <span className="ml-2 font-data text-[10px] text-ink-3">{block.code}</span>}
              </p>
            );
          case "ask":
            return answerable
              ? <AgentQuestion key={block.id} question={block} onAnswer={onAnswer} onUpload={onUpload} />
              : <p key={block.id} className="m-0 text-[12.5px] text-ink-3">Asked: {block.question}</p>;
          default:
            return null;
        }
      })}
      {turn.state === "failed" && (
        <span className="self-start"><Secondary onClick={() => onRetry(turn.seq)}>Retry</Secondary></span>
      )}
    </div>
  );
}

/** The agent's words: paragraphs, `- ` lists, `**bold**` and `` `code` ``, and nothing else. A
 *  model writes a little markdown; drawing it raw reads as noise, and more than this is not needed. */
function Prose({ text }: { text: string }) {
  const paragraphs = text.split(/\n{2,}/).map((p) => p.trim()).filter(Boolean);
  return (
    <div className="flex flex-col gap-2 text-[13.5px] leading-[1.6] text-ink">
      {paragraphs.map((p, i) => {
        const lines = p.split("\n");
        if (lines.every((l) => /^[-*] /.test(l))) {
          return (
            <ul key={i} className="m-0 pl-[18px] flex flex-col gap-1">
              {lines.map((l, j) => <li key={j}>{inline(l.slice(2))}</li>)}
            </ul>
          );
        }
        return <p key={i} className="m-0 whitespace-pre-wrap">{inline(p)}</p>;
      })}
    </div>
  );
}

function inline(text: string): ReactNode {
  return text.split(/(\*\*[^*]+\*\*|`[^`]+`)/).map((part, i) => {
    if (part.startsWith("**") && part.endsWith("**") && part.length > 4) {
      return <strong key={i} className="font-semibold">{part.slice(2, -2)}</strong>;
    }
    if (part.startsWith("`") && part.endsWith("`") && part.length > 2) {
      return <code key={i} className="font-data text-[12px]">{part.slice(1, -1)}</code>;
    }
    return <Fragment key={i}>{part}</Fragment>;
  });
}
