import { useEffect, useRef, useState } from "react";

import type {
  AuthoringProposal,
  AuthoringSession,
  AuthoringVocabulary,
  GoalIn,
  SampleInspected,
} from "../../api/types";
import { NoticeLine } from "./blocks/Block";
import { DisagreementCard } from "./blocks/DisagreementCard";
import { GapCard } from "./blocks/GapCard";
import { GoalCard } from "./blocks/GoalCard";
import { SampleResult } from "./blocks/SampleUpload";
import { StepProposalCard } from "./blocks/StepProposalCard";
import type { CorrectFact } from "./CurrentFacts";
import type { FactValue } from "./FactEditor";
import { waitingOn } from "./format";

export type WaitingProps = {
  session: AuthoringSession;
  busy: (proposalId: string) => boolean;
  onAccept: (
    proposal: AuthoringProposal, option?: string, goal?: GoalIn, value?: string | number | boolean,
  ) => void;
  onReject: (proposal: AuthoringProposal) => void;
  onPreview: (option: string | null, mode: "temporary" | "pinned") => void;
  /** The alternative whose complete preview is pinned on the canvas now. */
  pinnedPreview?: string | null;
  onSelect: (node: string | null) => void;
  onUpload?: (proposal: AuthoringProposal, files: File[]) => Promise<SampleInspected>;
  /** Ask about the step on offer — a real turn, so the panel turns to the conversation. */
  onAsk: (text: string) => void;
  /** A follow-up sent and not yet answered: nothing is asked of the person meanwhile. */
  saying?: string | null;
  vocabulary?: Record<string, string[]> | null;
  declarations?: AuthoringVocabulary["measurements"];
  onDisagreement?: (proposal: AuthoringProposal, option: string, value?: FactValue) => Promise<unknown>;
  correcting?: boolean;
  onCorrectAnswers?: () => void;
  /** The describe page's: correct a fact from its line in the goal, and whether that is allowed now. */
  onCorrectFact?: CorrectFact;
  factsDisabled?: boolean;
  /** The describe page's pace cards, drawn under the goal, and what *Start building* also does. */
  pace?: React.ReactNode;
  onStart?: () => void;
};

/** **What the engine is waiting on the person for, now** — one card, wherever the page puts it.
 *
 * The describe page puts it under the sentence; the build panel puts it under the step line. Either
 * way it is the one thing to answer, so it is drawn as the page's content, never as an entry in a
 * transcript. When nothing waits, it says what is happening instead, or nothing at all.
 */
export function Waiting({
  session,
  busy,
  onAccept,
  onReject,
  onPreview,
  pinnedPreview = null,
  onSelect,
  onUpload,
  onAsk,
  saying = null,
  vocabulary = null,
  declarations, onDisagreement, onCorrectAnswers, correcting = false, onCorrectFact, factsDisabled, pace, onStart,
}: WaitingProps) {
  // **The sample that answered the last question**, kept above the next one: the answer moves the
  // session on, so the card that showed it is gone the moment it arrives (issue 134). Kept only
  // while that next card is the one on offer: past it, it would sit out of order.
  const [sampled, setSampled] = useState<
    { result: SampleInspected; files: string[]; above: string | null } | null>(null);
  const pending = session.pending_proposal;
  const active = session.progress?.active ?? null;
  // **A new card waiting is brought into view**, as the rail's scroll-to did: the design record
  // found the one thing to answer below the fold under the history above it.
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (pending) box.current?.scrollIntoView?.({ block: "nearest" });
  }, [pending?.id]); // eslint-disable-line react-hooks/exhaustive-deps -- a new card, not a new object

  return (
    <div ref={box} className="flex flex-col gap-3" data-testid="waiting">
      {sampled && pending && sampled.above === pending.id && (
        <section aria-label="what your sample measured" className="border rounded-button"
                 style={{ borderColor: "var(--line-2)", background: "var(--paper-2)" }}>
          <header className="px-3 py-[9px] text-label text-ink-3" style={{ borderBottom: "1px solid var(--line)" }}>
            Measured from your sample
          </header>
          <div className="px-3 py-[11px]">
            <SampleResult result={sampled.result} files={sampled.files} />
          </div>
        </section>
      )}
      {pending && pending.kind === "step" && (
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
            onAsk(`Why is ${pending.block.kind === "step_proposal" ? pending.block.node : "this step"} here?`)}
          onSelect={() => onSelect(pending.block.kind === "step_proposal" ? pending.block.node : null)}
        />
      )}
      {pending?.kind === "disagreement" && onDisagreement && (
        <DisagreementCard key={pending.id} proposal={pending} declarations={declarations}
          busy={correcting || busy(pending.id)} onAnswer={(option, value) => onDisagreement(pending, option, value)} />
      )}
      {pending && pending.kind === "gap" && (
        <GapCard
          key={pending.id}
          proposal={pending}
          busy={busy(pending.id)}
          onAnswer={(option, value) => onAccept(pending, option, undefined, value)}
          onUpload={onUpload && ((files) => onUpload(pending, files))}
          onAnswered={(result, files) =>
            setSampled({ result, files, above: result.session.pending_proposal?.id ?? null })}
        />
      )}
      {pending && pending.kind === "pacing" && (
        // How the walk paces itself (spec §13 of the consultant build): a question with a closed
        // set of answers, so the gap card draws it — framed as the build's, not the data's; there
        // is nothing to upload.
        <GapCard
          key={pending.id}
          frame={{ label: "how we go through the build", title: "How do you want to build it?" }}
          proposal={pending}
          busy={busy(pending.id)}
          onAnswer={(option, value) => onAccept(pending, option, undefined, value)}
        />
      )}
      {pending && pending.kind === "goal" && (
        <GoalCard
          key={pending.id}
          proposal={pending}
          facts={session.facts}
          subjects={session.fact_subjects ?? []}
          onCorrectFact={onCorrectFact}
          declarations={declarations}
          factsDisabled={factsDisabled}
          pace={pace}
          vocabulary={vocabulary}
          busy={busy(pending.id)}
          onConfirm={(edited) => {
            onStart?.();
            onAccept(pending, "keep", edited);
          }}
          replaces={session.hand_edits ?? null}
          onReject={() => onReject(pending)}
        />
      )}
      {session.phase === "stopped" && (
        // Corrections can recover an honest stop without discarding its decisions.
        <p className="m-0">
          {onCorrectAnswers && !session.retired && <button type="button" onClick={onCorrectAnswers}
            className="mr-3 bg-transparent border-0 p-0 text-[12.5px] text-now-ink underline cursor-pointer">
            Correct current answers</button>}
          <a href="/build" className="text-[12.5px] text-now-ink underline focus-visible:shadow-[var(--ring)]">
            Start a new analysis
          </a>
        </p>
      )}
      {saying === null && waitingOn(session) && (
        <p className="m-0 text-[12.5px] leading-[1.6] text-ink-2" data-testid="your-turn">
          {waitingOn(session) === "refused"
            ? "Say it again, or put it differently — nothing was built from that answer."
            : "Say what is wrong with it, and the goal is read again."}
        </p>
      )}
      {session.phase === "resolving" && (
        <NoticeLine notice="pending" code={null}
                    text="Resolving the whole pipeline once, so every step is proposed knowing what comes after it." />
      )}
    </div>
  );
}
