import { useEffect, useRef } from "react";

import type { AuthoringProposal, AuthoringSession } from "../../api/types";
import { Block, NoticeLine, Primary, Secondary } from "./blocks/Block";
import { StepProposalCard } from "./blocks/StepProposalCard";
import { authorOf, processName } from "./format";
import { Turn, type Tick } from "./blocks/parts";

type Entry =
  | { at: string; order: number; kind: "turn"; turn: AuthoringSession["turns"][number] }
  | { at: string; order: number; kind: "decision"; decision: AuthoringSession["history"][number] };

/** The conversation, as a ruled log: every turn and every answered decision, oldest first.
 *
 * **There is no inspector, and this is why.** Every object on the canvas was put there by a
 * decision already in this log, so selecting a node scrolls here rather than opening a panel. An
 * answered decision collapses to one line — fifteen tall cards is a transcript nobody scrolls —
 * and the pending proposal is the only card that stays open.
 *
 * **The log scrolls to what is waiting**, with history above it: the design record found four
 * boards where the one thing to answer had fallen below the fold under full history.
 */
export function DecisionLog({
  session,
  selected,
  busy,
  onAccept,
  onReject,
  onPreview,
  onSelect,
  onRetry,
  onSay,
}: {
  session: AuthoringSession;
  selected: string | null;
  busy: (proposalId: string) => boolean;
  onAccept: (proposal: AuthoringProposal, option?: string) => void;
  onReject: (proposal: AuthoringProposal) => void;
  onPreview: (option: string | null) => void;
  onSelect: (node: string | null) => void;
  onRetry: () => void;
  onSay: (text: string) => void;
}) {
  const end = useRef<HTMLDivElement>(null);
  const list = useRef<HTMLOListElement>(null);

  const entries: Entry[] = [
    ...session.turns.map((turn, i) => ({ at: turn.at, order: i, kind: "turn" as const, turn })),
    ...session.history.map((decision, i) => ({
      at: decision.at,
      order: 1000 + i,
      kind: "decision" as const,
      decision,
    })),
  ].sort((a, b) => (a.at === b.at ? a.order - b.order : a.at < b.at ? -1 : 1));

  const accepted = new Set(session.history.filter((d) => d.state === "accepted").map((d) => d.block.id));
  const pending = session.pending_proposal;
  const stepsSoFar = session.history.filter((d) => d.kind === "step").length;
  const stepNumber = new Map(
    session.history.filter((d) => d.kind === "step").map((d, i) => [d.id, i + 1] as const),
  );

  useEffect(() => {
    end.current?.scrollIntoView?.({ block: "end" });
  }, [pending?.id, session.turns.length]);

  useEffect(() => {
    if (!selected) return;
    list.current
      ?.querySelector(`[data-decision-node="${CSS.escape(selected)}"]`)
      ?.scrollIntoView?.({ block: "nearest" });
  }, [selected]);

  return (
    <div className="relative">
      <ol
        ref={list}
        aria-label="decisions and conversation"
        className="relative m-0 p-0 pl-5 before:content-[''] before:absolute before:left-[4px]
                   before:top-[4px] before:bottom-0 before:w-px before:bg-[var(--surface-2)]"
      >
        {entries.map((entry) =>
          entry.kind === "turn" ? (
            <TurnEntry key={`t${entry.turn.seq}`} turn={entry.turn} accepted={accepted}
                       failedPhase={session.phase === "failed"} onRetry={onRetry} />
          ) : (
            <DecisionEntry key={`d${entry.decision.id}`} decision={entry.decision}
                           position={stepNumber.get(entry.decision.id) ?? 0}
                           selected={selected} onSelect={onSelect} />
          ),
        )}

        {pending && pending.kind === "step" && (
          <Turn tick="quiet">
            <p className="m-0 text-[12.5px] leading-[1.6] text-ink-2">
              Step {stepsSoFar + 1}{session.steps_total ? ` of ${session.steps_total}` : ""}, on the
              canvas already and drawn dashed. Nothing is committed until you add it.
            </p>
          </Turn>
        )}
        {pending && pending.kind === "step" && (
          <Turn tick="wait" anchor={pending.block.kind === "step_proposal" ? pending.block.node : undefined}>
            <StepProposalCard
              key={pending.id}
              proposal={pending}
              position={stepsSoFar + 1}
              busy={busy(pending.id)}
              onAccept={(option) => onAccept(pending, option)}
              onReject={() => onReject(pending)}
              onPreview={onPreview}
              onExplain={() =>
                onSay(`Why is ${pending.block.kind === "step_proposal" ? pending.block.node : "this step"} here?`)}
            />
          </Turn>
        )}
        {pending && pending.kind === "goal" && (
          <Turn tick="wait">
            <Block
              block={pending.block}
              actions={
                <>
                  <Primary data-testid="accept-goal" disabled={busy(pending.id)}
                           onClick={() => onAccept(pending)}>
                    {busy(pending.id) ? "Confirming…" : "That's right"}
                  </Primary>
                  <Secondary data-testid="reject-goal" disabled={busy(pending.id)}
                             onClick={() => onReject(pending)}>
                    Not quite
                  </Secondary>
                </>
              }
            />
          </Turn>
        )}
        {session.phase === "resolving" && (
          <Turn tick="wait">
            <NoticeLine notice="pending" code={null}
                        text="Resolving the whole pipeline once, so every step is proposed knowing what comes after it." />
          </Turn>
        )}
      </ol>
      <div ref={end} />
    </div>
  );
}

function TurnEntry({
  turn,
  accepted,
  failedPhase,
  onRetry,
}: {
  turn: AuthoringSession["turns"][number];
  accepted: Set<string>;
  failedPhase: boolean;
  onRetry: () => void;
}) {
  if (turn.role === "person") {
    return (
      <Turn tick="you">
        <p className="m-0 text-[13.5px] leading-[1.55] text-ink whitespace-pre-wrap">{turn.text}</p>
      </Turn>
    );
  }
  if (turn.state === "pending") {
    return (
      <Turn tick="wait">
        <NoticeLine notice="pending" code={null}
                    text="The canvas is still yours — move things, open a step, nothing is locked." />
      </Turn>
    );
  }
  if (turn.state === "failed") {
    return (
      <Turn tick="quiet">
        <p className="m-0 font-data text-[10px] leading-[1.5] text-ink-4">
          an answer arrived after the draft changed, and was not applied
        </p>
      </Turn>
    );
  }
  return (
    <>
      {turn.blocks.map((block) => {
        // A goal summary that was confirmed collapses to one line, like every answered decision.
        if (block.kind === "goal_summary" && accepted.has(block.id)) {
          return (
            <Turn key={block.id} tick="person">
              <Collapsed name="Goal confirmed" detail={block.get} by="you chose" />
            </Turn>
          );
        }
        const refused = block.kind === "notice" && block.notice === "refusal";
        const unreachable = refused && block.code !== null && UNREACHABLE.has(block.code ?? "");
        return (
          <Turn key={block.id} tick={refused ? "open" : "quiet"}>
            <Block
              block={block}
              actions={
                unreachable && failedPhase ? (
                  <Primary data-testid="retry" onClick={onRetry}>Try again</Primary>
                ) : undefined
              }
            />
          </Turn>
        );
      })}
    </>
  );
}

const UNREACHABLE = new Set(["MI0106", "MA0002", "MA0003", "MA0007"]);

/** What a collapsed row says about a tier, in the artboard's words. Tiers 1 and 2 say nothing. */
const TIER_WORD: Record<number, string> = { 3: " · measured", 4: " · open" };

function DecisionEntry({
  decision,
  position,
  selected,
  onSelect,
}: {
  decision: AuthoringSession["history"][number];
  position: number;
  selected: string | null;
  onSelect: (node: string | null) => void;
}) {
  if (decision.kind === "goal") return null; // drawn on its own turn, where it was offered
  const block = decision.block;
  if (block.kind !== "step_proposal") return null;
  const author = authorOf(decision);
  const tick: Tick = author === "model" ? "model" : author === "person" ? "person" : "resolver";
  const verb =
    decision.state === "rejected" ? "skipped" : decision.state === "stale" ? "withdrawn"
      : author === "model" ? "model chose" : author === "person" ? "you chose" : "settled";
  const replaced =
    decision.chosen_contract && decision.chosen_contract !== block.contract
      ? ` · ${decision.chosen_contract}`
      : "";

  return (
    <Turn tick={tick} anchor={block.node}>
      <Collapsed
        name={processName(block.node)}
        detail={`step ${position}${TIER_WORD[block.tier] ?? ""}${replaced}`}
        by={verb}
        selected={selected === block.node}
        onClick={() => onSelect(block.node)}
      />
    </Turn>
  );
}

function Collapsed({
  name,
  detail,
  by,
  selected = false,
  onClick,
}: {
  name: string;
  detail: string;
  by: string;
  selected?: boolean;
  onClick?: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={onClick ? selected : undefined}
      className="w-full flex items-baseline gap-[9px] py-[5px] px-0 bg-transparent border-0
                 text-left cursor-pointer focus-visible:shadow-[var(--ring)]"
    >
      <span className={`font-data text-[11px] ${selected ? "text-link" : "text-ink-2"}`}>{name}</span>
      <span className="font-data text-[10px] text-ink-3 truncate">{detail}</span>
      <span className="ml-auto font-data text-[9px] text-ink-4 shrink-0">{by}</span>
    </button>
  );
}
