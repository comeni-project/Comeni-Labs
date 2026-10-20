import type { AuthoringSession, AuthoringVocabulary } from "../../api/types";
import { Chat } from "./Chat";
import { StatusChip } from "./LivingHeader";
import { Composer } from "./Composer";
import { CurrentFacts, hasCurrentFacts, type CorrectFact } from "./CurrentFacts";
import { AnswerLine, answered } from "./StepLine";
import { Waiting, type WaitingProps } from "./Waiting";

/** **Describe — one column, while there is nothing to draw yet** (the *Describe* board).
 *
 * The sentence, then the one thing the engine is waiting on (the goal to check, a gap, how to go
 * through the build), then what was understood so far, then the conversation. The canvas is not
 * drawn: an empty canvas beside a transcript was the page this replaced.
 */
export function DescribePage({
  session,
  waiting,
  composer,
  composerHint,
  composerDisabled,
  onCompose,
  onSay,
  saying,
  onRetry,
  declarations,
  onCorrect,
  onRelease,
  correcting,
  factsRequest,
  notices,
}: {
  session: AuthoringSession;
  waiting: Omit<WaitingProps, "session" | "onAsk" | "saying">;
  composer: string;
  composerHint: string | undefined;
  composerDisabled: boolean;
  onCompose: (text: string) => void;
  onSay: (text: string) => void;
  saying: string | null;
  onRetry: () => void;
  declarations?: AuthoringVocabulary["measurements"];
  onCorrect?: CorrectFact;
  onRelease?: (type: string, states: string[]) => Promise<unknown>;
  correcting: boolean;
  factsRequest: number;
  notices: React.ReactNode;
}) {
  const first = session.turns.find((turn) => turn.role === "person") ?? null;
  const sentence = first?.text ?? null;
  // The conversation past the sentence quoted above: drawn only when there is some.
  const more = saying !== null || session.turns.some((turn) => turn.seq !== first?.seq &&
    (turn.role === "person" || turn.state !== "answered" || turn.blocks.some((b) => SPEECH.has(b.kind))));
  const pending = session.pending_proposal;

  return (
    <section aria-label="describe" className="min-h-0 overflow-auto">
      <div className="mx-auto w-full max-w-[860px] px-4 sm:px-6 pt-10 pb-16 flex flex-col gap-6">
        <header>
          <h1 className="m-0 text-title font-semibold tracking-[-.02em] text-ink">What do you want to analyse?</h1>
          <p className="m-0 mt-1 text-body text-ink-2">
            You will see what was understood before anything is built.
          </p>
        </header>
        {notices}
        {sentence && (
          <div className="rounded-panel border px-5 py-4 flex flex-col gap-3"
               style={{ borderColor: "var(--now-line)", background: "var(--surface)", boxShadow: "0 0 0 3px var(--now-soft)" }}>
            <blockquote data-testid="your-sentence" className="m-0 text-[16px] leading-[1.55] text-ink">
              {sentence}
            </blockquote>
            {/* The board's footer line: here, where the page says what it is doing with the
                sentence — reading it, or waiting for you (issues 110, 112). */}
            <div className="flex items-center gap-3 text-[13px] text-ink-2">
              <StatusChip session={session} />
            </div>
          </div>
        )}
        <Waiting session={session} onAsk={onSay} saying={saying} {...waiting} />
        {(hasCurrentFacts(session) || answered(session).length > 0) && <section aria-label="What was understood" className="rounded-panel border px-5 py-4"
                 style={{ borderColor: "var(--line)", background: "var(--surface)" }}>
          <h2 className="m-0 mb-2 text-heading font-semibold text-ink">What was understood</h2>
          {answered(session).map((decision) => <AnswerLine key={decision.id} decision={decision} />)}
          <CurrentFacts session={session} declarations={declarations} onCorrect={onCorrect} onRelease={onRelease}
            openRequest={factsRequest} open
            disabled={correcting || session.retired || session.turns.some((t) => t.state === "pending") ||
              session.phase === "resolving" ||
              (pending?.block.kind === "question" && pending.block.reading?.state === "pending")} />
        </section>}
        <section aria-label="Conversation" className="flex flex-col gap-3">
          {more && <>
            <h2 className="m-0 text-heading font-semibold text-ink">Conversation</h2>
            <Chat session={session} saying={saying} failedPhase={session.phase === "failed"}
                  onRetry={onRetry} onPoint={() => undefined} pointers={false} skip={first?.seq ?? null} follow={false} />
          </>}
          <Composer value={composer} onChange={onCompose} onSend={onSay}
                    disabled={composerDisabled} placeholder={composerHint ?? "Or say it in your own words"} />
        </section>
      </div>
    </section>
  );
}

/** Block kinds that are speech — what the conversation shows when there are no pointer lines. */
const SPEECH = new Set(["narrative", "receipt", "notice"]);
