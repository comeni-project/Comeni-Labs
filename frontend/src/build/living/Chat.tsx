import { useEffect, useRef } from "react";

import type { AuthoringBlock, AuthoringSession } from "../../api/types";
import { Block, NoticeLine, Primary } from "./blocks/Block";
import { processName } from "./format";

/** **The conversation, and only the conversation**: what the person said and what the model said.
 *
 * The engine's cards are not drawn here. A reply that carried one — a question, a step, a setting
 * request, a change — leaves a line saying what it did, which takes the person to the Step panel
 * where the card waits. Answered decisions are not repeated here either; the step line and *What
 * was understood* are their record. A conversation made of form boxes is the thing this replaced.
 */
export function Chat({
  session,
  saying,
  failedPhase,
  onRetry,
  onPoint,
}: {
  session: AuthoringSession;
  /** A follow-up sent and not yet in the transcript — drawn now, marked as sending. */
  saying: string | null;
  failedPhase: boolean;
  onRetry: () => void;
  /** Show the card a pointer line is about: the step it names, or whatever is waiting. */
  onPoint: (node: string | null) => void;
}) {
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => {
    end.current?.scrollIntoView?.({ block: "end" });
  }, [session.turns.length, saying]);

  return (
    <div>
      <ol role="log" aria-label="conversation" className="m-0 p-0 flex flex-col gap-3">
        {session.turns.map((turn) => {
          if (turn.role === "person") {
            return (
              <li key={turn.seq} className="list-none self-end max-w-[85%] px-3 py-2 rounded-[10px]
                                            text-[13.5px] leading-[1.55] text-ink whitespace-pre-wrap"
                  style={{ background: "var(--now-soft)" }}>
                {turn.text}
              </li>
            );
          }
          if (turn.state === "pending") {
            return (
              <li key={turn.seq} className="list-none">
                <NoticeLine notice="pending" code={null}
                            text="The canvas is still yours — move things, open a step, nothing is locked." />
              </li>
            );
          }
          if (turn.state === "failed") {
            return (
              <li key={turn.seq} className="list-none text-[12px] text-ink-3">
                An answer arrived after the draft changed, and was not applied.
              </li>
            );
          }
          return turn.blocks.map((block) => (
            <li key={block.id} className="list-none">
              <Spoken block={block} failedPhase={failedPhase} onRetry={onRetry} onPoint={onPoint} />
            </li>
          ));
        })}
        {saying !== null && (
          <li className="list-none self-end max-w-[85%] px-3 py-2 rounded-[10px]"
              style={{ background: "var(--now-soft)" }}>
            <p className="m-0 text-[13.5px] leading-[1.55] text-ink whitespace-pre-wrap" data-testid="saying">
              {saying}
            </p>
            <p className="m-0 mt-1 text-[11px] text-ink-3">sending…</p>
          </li>
        )}
      </ol>
      <div ref={end} />
    </div>
  );
}

const UNREACHABLE = new Set(["MI0106", "MA0002", "MA0003", "MA0007"]);

function Spoken({ block, failedPhase, onRetry, onPoint }: {
  block: AuthoringBlock;
  failedPhase: boolean;
  onRetry: () => void;
  onPoint: (node: string | null) => void;
}) {
  const pointer = pointerOf(block);
  if (pointer) {
    return (
      <button type="button" data-testid="pointer" onClick={() => onPoint(pointer.node)}
              className="bg-transparent border-0 p-0 text-left text-[12.5px] text-now-ink underline
                         cursor-pointer focus-visible:shadow-[var(--ring)]">
        {pointer.words} — see Step
      </button>
    );
  }
  const unreachable = block.kind === "notice" && block.notice === "refusal" && UNREACHABLE.has(block.code ?? "");
  return (
    <Block
      block={block}
      actions={unreachable && failedPhase ? <Primary data-testid="retry" onClick={onRetry}>Try again</Primary> : undefined}
    />
  );
}

/** What a reply's engine block did, in one line, and the step it is about. Speech has none. */
function pointerOf(block: AuthoringBlock): { words: string; node: string | null } | null {
  switch (block.kind) {
    case "goal_summary":
      return { words: "Read the goal", node: null };
    case "question":
      return { words: "Asked a question", node: null };
    case "step_proposal":
      return { words: `Proposed ${processName(block.node)}`, node: block.node };
    case "setting_request":
      return { words: `Asked for a setting on ${processName(block.node)}`, node: block.node };
    case "change_set":
      return { words: `Suggested a change: ${block.summary}`, node: block.removes[0] ?? block.adds[0] ?? null };
    default:
      return null;
  }
}
