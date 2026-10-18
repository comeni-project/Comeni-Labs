import { useEffect, useRef, useState } from "react";

import type {
  AuthoringBlock,
  AuthoringProposal,
  AuthoringSession,
  AuthoringVocabulary,
  DraftGraph,
  GoalIn,
  SampleInspected,
  Step,
} from "../../api/types";
import { Block, NoticeLine, Primary } from "./blocks/Block";
import { ChangeSetCard } from "./blocks/ChangeSetCard";
import { DisagreementCard } from "./blocks/DisagreementCard";
import type { FactValue } from "./FactEditor";
import { GapCard } from "./blocks/GapCard";
import { GoalCard } from "./blocks/GoalCard";
import { SampleResult } from "./blocks/SampleUpload";
import { SettingCard } from "./blocks/SettingCard";
import { StepProposalCard } from "./blocks/StepProposalCard";
import { StepTools } from "./blocks/StepTools";
import { authorOf, processName, stepWords, waitingOn, type OfferProgress } from "./format";
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
  pinnedPreview = null,
  onSelect,
  onRetry,
  onUpload,
  onSay,
  saying = null,
  vocabulary = null,
  declarations, onDisagreement, onCorrectAnswers, correcting = false,
  onSetParam,
  onApplyChange,
  graph,
  steps,
  onEdit,
}: {
  session: AuthoringSession;
  selected: string | null;
  busy: (proposalId: string) => boolean;
  onAccept: (
    proposal: AuthoringProposal, option?: string, goal?: GoalIn, value?: string | number | boolean,
  ) => void;
  onReject: (proposal: AuthoringProposal) => void;
  onPreview: (option: string | null, mode: "temporary" | "pinned") => void;
  /** The alternative whose complete preview is pinned on the canvas now. */
  pinnedPreview?: string | null;
  onSelect: (node: string | null) => void;
  onRetry: () => void;
  onUpload?: (proposal: AuthoringProposal, files: File[]) => Promise<SampleInspected>;
  onSay: (text: string) => void;
  /** A follow-up sent and not yet in the transcript — drawn now, marked as sending. */
  saying?: string | null;
  vocabulary?: Record<string, string[]> | null;
  declarations?: AuthoringVocabulary["measurements"];
  onDisagreement?: (proposal: AuthoringProposal, option: string, value?: FactValue) => Promise<unknown>;
  correcting?: boolean;
  onCorrectAnswers?: () => void;
  onSetParam: (node: string, setting: string, value: string) => void;
  onApplyChange: (block: Extract<AuthoringBlock, { kind: "change_set" }>) => void;
  /** The draft as drawn — what a step's tools change. */
  graph: DraftGraph;
  /** The drawn view of each step, by id: the ports a swap matches and the settings a card lists. */
  steps: Record<string, Step>;
  onEdit: (graph: DraftGraph) => void;
}) {
  const end = useRef<HTMLDivElement>(null);
  const list = useRef<HTMLOListElement>(null);
  // **The sample that answered the last question**, kept above the next one: the answer moves
  // the session on, so the card that showed it is gone the moment it arrives (issue 134). Kept
  // only while that next card is the one on offer: past it, it would sit out of order.
  const [sampled, setSampled] = useState<
    { result: SampleInspected; files: string[]; above: string | null } | null>(null);

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
  const acceptedBy = new Map(session.history.map((d) => [d.block.id, d.actor_kind ?? "unknown"] as const));
  const pending = session.pending_proposal;
  const drawnOnTurns = new Set(session.turns.flatMap((t) => t.blocks.map((b) => b.id)));
  // **Where each step stood when it was offered**, from its own envelope, and where the walk is
  // now, from the server's count against the plan — never a count of proposals in the transcript.
  const active = session.progress?.active ?? null;

  // **A selected step that is in the draft gets its tools under the line that created it** — or,
  // for a step added by hand that no decision created, after the history. A ghost is not in the
  // draft, and its own card already offers the alternatives.
  const editable = selected !== null && graph.nodes.some((n) => n.id === selected) ? selected : null;
  const created = new Set(
    session.history.flatMap((d) =>
      d.state === "accepted" && d.block.kind === "step_proposal" ? [d.block.node] : []),
  );
  const tools = editable ? (
    <StepTools key={editable} node={editable} step={steps[editable]} graph={graph} onEdit={onEdit} />
  ) : null;

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
                       acceptedBy={acceptedBy}
                       offered={pending?.kind === "goal" ? pending.block.id : null}
                       failedPhase={session.phase === "failed"} onRetry={onRetry}
                       onSetParam={onSetParam} onApplyChange={onApplyChange} />
          ) : (
            <DecisionEntry key={`d${entry.decision.id}`} decision={entry.decision}
                           progress={offeredAt(entry.decision)}
                           selected={selected} onSelect={onSelect} tools={tools}
                           inTurns={drawnOnTurns.has(entry.decision.block.id)} />
          ),
        )}

        {editable && !created.has(editable) && (
          <Turn tick="person" anchor={editable}>
            {tools}
          </Turn>
        )}

        {pending && pending.kind === "step" && (
          <Turn tick="quiet">
            <p className="m-0 text-[12.5px] leading-[1.6] text-ink-2">
              {stepWords(active)}, on the canvas already and drawn dashed. Nothing is committed
              until you add it.
            </p>
          </Turn>
        )}
        {pending && pending.kind === "step" && (
          <Turn tick="wait" anchor={pending.block.kind === "step_proposal" ? pending.block.node : undefined}>
            <StepProposalCard
              key={pending.id}
              proposal={pending}
              progress={active}
              showGapDetails={session.show_gap_details ?? false}
              onCorrectAnswers={onCorrectAnswers}
              busy={busy(pending.id)}
              onAccept={(option, value) => onAccept(pending, option, undefined, value)}
              onPreview={onPreview}
              pinned={pinnedPreview}
              previewable={(pending.envelope as { preview_options?: string[] } | undefined)?.preview_options ?? []}
              onExplain={() =>
                onSay(`Why is ${pending.block.kind === "step_proposal" ? pending.block.node : "this step"} here?`)}
              onSelect={() => onSelect(pending.block.kind === "step_proposal" ? pending.block.node : null)}
            />
          </Turn>
        )}
        {sampled && pending && sampled.above === pending.id && (
          <Turn tick="person">
            <section aria-label="what your sample measured" className="border"
              style={{ borderColor: "var(--line-2)", background: "var(--paper-2)" }}>
              <header className="px-3 py-[9px] font-data text-[9.5px] tracking-[.15em] uppercase
                                 text-ink-3" style={{ borderBottom: "1px solid var(--line)" }}>
                Measured from your sample
              </header>
              <div className="px-3 py-[11px]">
                <SampleResult result={sampled.result} files={sampled.files} />
              </div>
            </section>
          </Turn>
        )}
        {pending?.kind === "disagreement" && onDisagreement && <Turn tick="wait">
          <DisagreementCard key={pending.id} proposal={pending} declarations={declarations}
            busy={correcting || busy(pending.id)} onAnswer={(option, value) => onDisagreement(pending, option, value)} />
        </Turn>}
        {pending && pending.kind === "gap" && (
          <Turn tick="wait">
            <GapCard
              key={pending.id}
              proposal={pending}
              busy={busy(pending.id)}
              onAnswer={(option, value) => onAccept(pending, option, undefined, value)}
              onUpload={onUpload && ((files) => onUpload(pending, files))}
              onAnswered={(result, files) =>
                setSampled({ result, files, above: result.session.pending_proposal?.id ?? null })}
            />
          </Turn>
        )}
        {pending && pending.kind === "pacing" && (
          // How the walk paces itself (spec §13 of the consultant build): a question with a
          // closed set of answers, so the gap card draws it — framed as the build's, not the
          // data's; there is nothing to upload.
          <Turn tick="wait">
            <GapCard
              key={pending.id}
              frame={{ label: "how we go through the build", title: "How we go" }}
              proposal={pending}
              busy={busy(pending.id)}
              onAnswer={(option, value) => onAccept(pending, option, undefined, value)}
            />
          </Turn>
        )}
        {pending && pending.kind === "goal" && (
          <Turn tick="wait">
            <GoalCard
              key={pending.id}
              proposal={pending}
              facts={session.facts}
              vocabulary={vocabulary}
              busy={busy(pending.id)}
              onConfirm={(edited) => onAccept(pending, "keep", edited)}
              replaces={session.hand_edits ?? null}
              onReject={() => onReject(pending)}
            />
          </Turn>
        )}
        {session.phase === "stopped" && (
          // Corrections can recover an honest stop without discarding its decisions.
          <Turn tick="open">
            {onCorrectAnswers && !session.retired && <button type="button" onClick={onCorrectAnswers}
              className="mr-3 text-[12.5px] text-link underline">Correct current answers</button>}
            <a href="/build" className="text-[12.5px] text-link underline focus-visible:shadow-[var(--ring)]">
              Start a new analysis
            </a>
          </Turn>
        )}
        {saying === null && waitingOn(session) && (
          <Turn tick="open">
            <p className="m-0 text-[12.5px] leading-[1.6] text-ink-2" data-testid="your-turn">
              {waitingOn(session) === "refused"
                ? "Say it again, or put it differently — nothing was built from that answer."
                : "Say what is wrong with it, and the goal is read again."}
            </p>
          </Turn>
        )}
        {saying !== null && (
          <Turn tick="you">
            <p className="m-0 text-[13.5px] leading-[1.55] text-ink whitespace-pre-wrap" data-testid="saying">
              {saying}
            </p>
            <p className="m-0 mt-1 font-data text-[10px] text-ink-4">sending…</p>
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
  acceptedBy,
  offered,
  failedPhase,
  onRetry,
  onSetParam,
  onApplyChange,
}: {
  turn: AuthoringSession["turns"][number];
  accepted: Set<string>;
  /** Who accepted each answered block — a Spawn goal is accepted by policy on the model's reading. */
  acceptedBy: Map<string, string>;
  /** The goal summary currently on offer as a card — drawn there, and so not drawn here. */
  offered: string | null;
  failedPhase: boolean;
  onRetry: () => void;
  onSetParam: (node: string, setting: string, value: string) => void;
  onApplyChange: (block: Extract<AuthoringBlock, { kind: "change_set" }>) => void;
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
        // **The goal on offer is the card, and only the card.** The first render drew it twice —
        // read-only in the turn that produced it and editable underneath — which is two goals on a
        // screen whose whole job at that moment is to make one of them checkable.
        if (block.kind === "goal_summary" && block.id === offered) {
          return (
            <Turn key={block.id} tick="quiet">
              <p className="m-0 text-[12.5px] leading-[1.6] text-ink-2">
                Here is the goal I read. Nothing is decided yet.
              </p>
            </Turn>
          );
        }
        // A goal summary that was confirmed collapses to one line, like every answered decision.
        if (block.kind === "goal_summary" && accepted.has(block.id)) {
          return (
            <Turn key={block.id} tick={acceptedBy.get(block.id) === "model" ? "model" : "person"}>
              <Collapsed name="Goal confirmed" detail={block.get}
                         by={acceptedBy.get(block.id) === "model" ? "read by the model" :
                           acceptedBy.get(block.id) === "person" ? "you chose" : "chooser unknown"} />
            </Turn>
          );
        }
        if (block.kind === "setting_request") {
          return (
            <Turn key={block.id} tick="open" anchor={block.node}>
              <SettingCard block={block} onApply={onSetParam} />
            </Turn>
          );
        }
        if (block.kind === "change_set") {
          return (
            <Turn key={block.id} tick="wait">
              <ChangeSetCard block={block} onApply={onApplyChange} />
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
const TIER_WORD: Record<number, string> = { 4: " · open" };

/** The position a decided step was offered at, or `null` for an offer older than the record. */
function offeredAt(decision: AuthoringSession["history"][number]): OfferProgress | null {
  return (decision.envelope as { progress?: OfferProgress | null } | null | undefined)?.progress ?? null;
}

function DecisionEntry({
  decision,
  progress,
  selected,
  onSelect,
  tools,
  inTurns = false,
}: {
  decision: AuthoringSession["history"][number];
  progress: OfferProgress | null;
  selected: string | null;
  onSelect: (node: string | null) => void;
  /** The selected step's tools, drawn here only when this is the decision that put it there. */
  tools: React.ReactNode;
  /** Whether this decision's block is already drawn on a turn of the transcript. */
  inTurns?: boolean;
}) {
  if (decision.kind === "goal") {
    // A goal a model read is drawn on its own turn, where it was offered. **One gathering
    // composed has no turn** — the engine offered it — so it gets its line here, or a confirmed
    // goal would vanish from the log (issue 173).
    if (inTurns || decision.state !== "accepted" || decision.block.kind !== "goal_summary") {
      return null;
    }
    const goal = decision.block.goal as { have?: { type_id: string }[]; want?: string[] };
    const flow = `${(goal.have ?? []).map((h) => h.type_id).join(", ")} → ${(goal.want ?? []).join(", ")}`;
    return (
      <Turn tick={decision.actor_kind === "model" ? "model" : "person"}>
        <Collapsed name="Goal confirmed" detail={flow}
                   by={decision.actor_kind === "model" ? "confirmed by the policy" :
                     decision.actor_kind === "person" ? "you confirmed" : "chooser unknown"} />
      </Turn>
    );
  }
  const block = decision.block;
  if ((decision.kind === "gap" || decision.kind === "pacing") && block.kind === "question") {
    // One quiet line per answered gap. **The answer is never the part cut short** (issue 169): a
    // long question truncates, and a typed value is shown as the value, not the field's label.
    const answer = decision.answer
      ?? block.options.find((o) => o.id === decision.chosen_option)?.label
      ?? decision.chosen_option ?? "";
    const model = decision.actor_kind === "model";
    const sampled = decision.chosen_option === "upload";
    // A sample the AI read, not one an inspector measured (issue 135).
    const aiRead = sampled && (block as { reading?: { state?: string } | null }).reading?.state === "read";
    return (
      <Turn tick={model ? "model" : "person"}>
        <div className="flex items-baseline gap-[9px] py-[5px]">
          <span className="font-data text-[10px] text-ink-3 truncate min-w-0">{block.asks}</span>
          <span data-testid={`gap-answer-${decision.id}`}
                className="font-data text-[11px] text-ink-2 shrink-0">{answer}</span>
          <span className="ml-auto font-data text-[9px] text-ink-4 shrink-0">
            {model ? "read by AI" : aiRead ? "from your sample"
              : sampled ? "measured from your sample" : "you said"}
          </span>
        </div>
      </Turn>
    );
  }
  if (block.kind !== "step_proposal") return null;
  const author = authorOf(decision);
  const tick: Tick = author === "model" ? "model" : author === "person" ? "person" : author === "unknown" ? "quiet" : "resolver";
  // **A withdrawn offer says why** (#354): the engine withdraws one when the answers it was
  // built on change. It was never decided, so its tier's *open* does not apply.
  const went = decision.state === "rejected" || decision.state === "stale";
  const verb =
    decision.state === "rejected" ? "skipped" : decision.state === "stale" ? "answers changed"
      : author === "model" ? "model chose" : author === "person" ? "you chose" : author === "unknown" ? "chooser unknown" : "settled";
  const replaced =
    decision.chosen_contract && decision.chosen_contract !== block.contract
      ? ` · ${decision.chosen_contract}`
      : "";

  return (
    <Turn tick={tick} anchor={block.node}>
      <Collapsed
        name={processName(block.node)}
        detail={`${progress ? stepWords(progress).toLowerCase() : ""}${went ? "" : TIER_WORD[block.tier] ?? ""}${replaced}${decision.applicability && decision.applicability !== "retained" ? ` · ${decision.applicability}` : ""}`.replace(/^ · /, "")}
        by={verb}
        selected={selected === block.node}
        onClick={() => onSelect(block.node)}
      />
      {tools && decision.state === "accepted" && (!decision.applicability || decision.applicability === "retained") && selected === block.node && (
        <div className="mt-2">{tools}</div>
      )}
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
      <span className={`font-data text-[11px] shrink-0 whitespace-nowrap ${selected ? "text-link" : "text-ink-2"}`}>{name}</span>
      <span className="font-data text-[10px] text-ink-3 truncate min-w-0">{detail}</span>
      <span className="ml-auto font-data text-[9px] text-ink-4 shrink-0">{by}</span>
    </button>
  );
}
