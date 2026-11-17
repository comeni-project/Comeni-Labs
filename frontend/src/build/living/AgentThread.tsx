import { createContext, Fragment, useContext, useRef, type ReactNode } from "react";

import type { AuthoringTurn } from "../../api/types";
import { AgentQuestion, type AnswerValue } from "./AgentQuestion";
import { Secondary } from "./blocks/parts";
import { ToolTrail, type TrailStep } from "./ToolTrail";

/** **The shell a suggested command goes to** (#511): Run → Console provides it, so the agent's
 *  *Suggested command* cards can be run or inserted there; anywhere else they show the command. */
export const ShellContext = createContext<{ run: (command: string) => void; insert: (command: string) => void } | null>(null);

/** **The conversation with the builder agent** (#463): the person's words, and each of the
 *  agent's turns as what it did (its working trail), what it said, and what it asks. Nothing here
 *  is a stage or a form the person must get through; the canvas beside it is the pipeline. */
export function AgentThread({ turns, working, sending = [], onAnswer, onRetry, onStep }: {
  turns: AuthoringTurn[];
  /** Whether the agent is working on a turn now. */
  working: boolean;
  /** Messages sent and not yet in the transcript, drawn at once. */
  sending?: string[];
  onAnswer: (questionId: string, value: AnswerValue) => void;
  onRetry: (seq: number) => void;
  /** Show a step an answer used: on the canvas, or in the pipeline file. */
  onStep?: (node: string) => void;
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
            ? <Said text={turn.text} console={turn.blocks.some((b) => b.kind === "console")} />
            : <AgentTurn turn={turn} answerable={turn.seq > lastPerson && !working}
                         onAnswer={onAnswer} onRetry={onRetry} onStep={onStep} />}
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

function Said({ text, pending = false, console = false }: { text: string; pending?: boolean; console?: boolean }) {
  return (
    <div className="self-end max-w-[85%] flex flex-col items-end gap-[3px]">
      <div className="px-3 py-2 rounded-panel text-[13.5px] leading-[1.55] text-ink whitespace-pre-wrap"
           style={{ background: "var(--now-soft)", opacity: pending ? 0.7 : undefined }}>
        {text}
      </div>
      {console && <span className="text-[11px] text-ink-3">with what the console showed</span>}
    </div>
  );
}

/** A command the agent suggests: run in the shell or inserted there; a read-only one the Console
 *  has already run for it. Marked AI, like everything the agent chooses. */
function CommandCard({ command, readOnly, because }: { command: string; readOnly: boolean; because: string }) {
  const shell = useContext(ShellContext);
  return (
    <div data-testid="suggested-command" className="flex flex-col gap-2 px-3 py-[10px] rounded-panel border border-ai-line bg-surface">
      <span className="flex items-center gap-[6px]">
        <span className="px-[5px] rounded-xs bg-ai-soft text-ai text-[10.5px] font-semibold leading-[16px]">AI</span>
        <span className="text-[12.5px] font-semibold text-ink">{readOnly ? "Looked with" : "Suggested command"}</span>
      </span>
      <code className="block px-[10px] py-2 rounded-control bg-surface-2 font-data text-[11.5px] text-ink whitespace-pre-wrap break-all">{command}</code>
      <span className="text-[12px] text-ink-2">{because}</span>
      {shell && !readOnly && (
        <span className="flex gap-[6px]">
          <button type="button" onClick={() => shell.run(command)}
                  className="h-[30px] px-3 rounded-control border-0 bg-action text-on-action shadow-raise text-[12px] font-semibold cursor-pointer">
            Run in the shell
          </button>
          <button type="button" onClick={() => shell.insert(command)}
                  className="h-[30px] px-[10px] rounded-control border border-line-2 bg-surface text-[12px] font-semibold text-ink-2 cursor-pointer">
            Insert
          </button>
        </span>
      )}
    </div>
  );
}

function AgentTurn({ turn, answerable, onAnswer, onRetry, onStep }: {
  turn: AuthoringTurn;
  answerable: boolean;
  onAnswer: (questionId: string, value: AnswerValue) => void;
  onRetry: (seq: number) => void;
  onStep?: (node: string) => void;
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
          case "command":
            return <CommandCard key={block.id} command={block.command} readOnly={block.read_only} because={block.because} />;
          case "ask":
            return answerable
              ? <AgentQuestion key={block.id} question={block} onAnswer={onAnswer} />
              : <p key={block.id} className="m-0 text-[12.5px] text-ink-3">Asked: {block.question}</p>;
          default:
            return null;
        }
      })}
      {turn.state === "answered" && rest.some((b) => b.kind === "message") && (
        <Used steps={[...new Set(trail.flatMap((b) => (b.kind === "tool" && b.node ? [b.node] : [])))]} onStep={onStep} />
      )}
      {turn.state === "failed" && (
        <span className="self-start"><Secondary onClick={() => onRetry(turn.seq)}>Retry</Secondary></span>
      )}
    </div>
  );
}

/** **What an answer rests on** (#499): each step its tools read or changed, as a link —
 *  derived by the engine from the tools, never written by the model. Nothing when there is none. */
function Used({ steps, onStep }: { steps: string[]; onStep?: (node: string) => void }) {
  if (!onStep || steps.length === 0) return null;
  return (
    <div role="group" aria-label="what this answer used" className="flex flex-wrap items-center gap-[6px] text-[11.5px]">
      {onStep && steps.map((node) => (
        <button key={node} type="button" onClick={() => onStep(node)}
                className="px-[8px] py-[1px] rounded-full border bg-transparent font-data text-now-ink cursor-pointer
                           hover:bg-[var(--hover)] focus-visible:shadow-[var(--ring)]"
                style={{ borderColor: "var(--now-line)" }}>
          {node.toUpperCase()}
        </button>
      ))}
    </div>
  );
}

/** The agent's words: paragraphs, `- ` lists, `**bold**` and `` `code` ``, and nothing else. A
 *  model writes a little markdown; drawing it raw reads as noise, and more than this is not needed. */
function Prose({ text }: { text: string }) {
  // Fenced code blocks first, kept whole; the rest splits into paragraphs.
  const parts = text.split(/```[^\n]*\n([\s\S]*?)```/g);
  return (
    <div className="flex flex-col gap-2 text-[13.5px] leading-[1.6] text-ink">
      {parts.flatMap<ReactNode>((part, at) => at % 2 === 1
        ? [<pre key={`code-${at}`} className="m-0 px-3 py-2 rounded-control font-data text-[12px] whitespace-pre overflow-x-auto"
                style={{ background: "var(--paper)" }}>{part.replace(/\n$/, "")}</pre>]
        : paragraphsOf(part, at))}
    </div>
  );
}

function paragraphsOf(text: string, at: number): ReactNode[] {
  const paragraphs = text.split(/\n{2,}/).map((p) => p.trim()).filter(Boolean);
  return paragraphs.map((p, n) => {
    const i = `${at}-${n}`;
    // Runs of `- ` lines are a list, whatever lines lead into them (walk 2026-11-15).
    const runs: { list: boolean; lines: string[] }[] = [];
    for (const line of p.split("\n")) {
      const list = /^\s*[-*] /.test(line);
      if (runs.at(-1)?.list === list) runs.at(-1)!.lines.push(line);
      else runs.push({ list, lines: [line] });
    }
    return (
      <div key={i} className="flex flex-col gap-1">
        {runs.map((run, r) => run.list ? (
          <ul key={r} className="m-0 pl-[18px] flex flex-col gap-1">
            {run.lines.map((l, j) => <li key={j}>{inline(l.replace(/^\s*[-*] /, ""))}</li>)}
          </ul>
        ) : <p key={r} className="m-0 whitespace-pre-wrap">{inline(run.lines.join("\n"))}</p>)}
      </div>
    );
  });
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
