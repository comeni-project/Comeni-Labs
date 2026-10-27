import { useEffect, useId, useRef, useState } from "react";

import type { AuthoringSession, AuthoringVocabulary } from "../../api/types";
import { usePacing } from "../usePacing";
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
 *
 * **While the goal is checked, the goal is *What was understood*** — one table, corrected line by
 * line — and *Start building* confirms it. When the installation asks the pace every time, the
 * two pace cards are drawn under it and the one chosen answers the engine's pacing question when
 * it arrives (once; still the person's answer, recorded by the engine). When the pace is fixed,
 * the engine never asks, so the page says how it will go instead of offering a choice that
 * changes nothing.
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
  sending,
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
  sending: string[];
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
  const checking = pending?.kind === "goal";
  const pacing = usePacing();
  const [pace, setPace] = useState<string>("together");
  // **Held from Start building until the engine asks**, then spent: a ref, so a re-render between
  // the two cannot answer twice.
  const held = useRef<string | null>(null);
  useEffect(() => {
    if (pending?.kind !== "pacing" || held.current === null) return;
    const chosen = held.current;
    held.current = null;
    if (pending.options.includes(chosen)) waiting.onAccept(pending, chosen);
  }, [pending?.id]); // eslint-disable-line react-hooks/exhaustive-deps -- once per question asked
  const paces = pacing === "ask" ? <Paces value={pace} onChange={setPace} />
    : pacing && PACE_WORDS[pacing] ? (
      <p className="m-0 text-[13.5px] text-ink-2">
        {PACE_WORDS[pacing]} — change it in <a href="/settings/building" className="text-now-ink underline">Settings</a>.
      </p>
    ) : null;
  const facts = correcting || session.retired || session.turns.some((t) => t.state === "pending") ||
    session.phase === "resolving";
  const pins = (session.goal?.constraints?.producers ?? []).length > 0;

  return (
    <section aria-label="describe" className="min-h-0 overflow-auto">
      <div className="mx-auto w-full max-w-[860px] px-[16px] sm:px-[24px] pt-10 pb-16 flex flex-col gap-6">
        <header>
          <h1 className="m-0 text-hero leading-tight font-semibold tracking-[-.02em] text-ink">What do you want to analyse?</h1>
          <p className="m-0 mt-[6px] text-lede text-ink-2">
            Say it the way you would to a colleague. You'll see what was understood before anything is built.
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
        <Waiting session={session} onAsk={onSay} saying={saying} {...waiting}
                 onCorrectFact={onCorrect} factsDisabled={facts} pace={paces}
                 onStart={() => { held.current = pacing === "ask" ? pace : null; }} />
        {/* While the goal is checked it *is* what was understood; this list would say it twice. */}
        {(!checking || pins) && (hasCurrentFacts(session) || answered(session).length > 0) && <section aria-label="What was understood" className="rounded-panel border px-5 py-4"
                 style={{ borderColor: "var(--line)", background: "var(--surface)" }}>
          <h2 className="m-0 mb-2 text-heading font-semibold text-ink">What was understood</h2>
          {answered(session).map((decision) => <AnswerLine key={decision.id} decision={decision} />)}
          <CurrentFacts session={session} declarations={declarations} onCorrect={onCorrect} onRelease={onRelease}
            openRequest={factsRequest} open
            disabled={facts || (pending?.block.kind === "question" && pending.block.reading?.state === "pending")} />
        </section>}
        <section aria-label="Conversation" className="flex flex-col gap-3">
          {more && <>
            <h2 className="m-0 text-heading font-semibold text-ink">Conversation</h2>
            <Chat session={session} sending={sending} failedPhase={session.phase === "failed"}
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

/** How the build will go when the installation has fixed it, in the board's words. */
const PACE_WORDS: Record<string, string> = {
  together: "Goes through it together, step by step",
  stop_where_needed: "Builds everything a rule can settle at once, then stops only where it needs you",
};

/** The two paces as the *Describe* board draws them; ids are the engine's `Pacing` values. */
const PACES = [
  { id: "together", title: "Step by step, with me", chip: "good for a first pipeline",
    text: "Each step is proposed with its reason and the alternatives. You add it, ask why, or pick another." },
  { id: "stop_where_needed", title: "All at once", chip: null,
    text: "Everything a rule can settle is built in one go. Then only the open questions are left for you." },
];

function Paces({ value, onChange }: { value: string; onChange: (pace: string) => void }) {
  const group = useId();
  return (
    <section className="flex flex-col gap-[10px]">
      <h2 id={`${group}-title`} className="m-0 text-heading font-semibold text-ink">How do you want to build it?</h2>
      <div role="radiogroup" aria-labelledby={`${group}-title`} className="grid gap-[14px] sm:grid-cols-2">
        {PACES.map((pace) => {
          const on = value === pace.id;
          return (
            <label key={pace.id} className="flex items-start gap-[12px] px-[18px] py-[16px] rounded-panel border cursor-pointer
                                            focus-within:shadow-[var(--ring)]"
                   style={{ borderColor: on ? "var(--now)" : "var(--line-2)", borderWidth: on ? 2 : 1,
                            background: "var(--surface)" }}>
              <input type="radio" name={group} value={pace.id} checked={on} onChange={() => onChange(pace.id)}
                     aria-label={pace.title} className="sr-only" />
              <span aria-hidden className="mt-[3px] shrink-0 w-[16px] h-[16px] rounded-full border"
                    style={{ borderColor: on ? "var(--now)" : "var(--line-2)",
                             background: on ? "radial-gradient(circle, var(--now) 0 4px, var(--surface) 4.5px)" : "var(--surface)" }} />
              <span className="min-w-0">
                <span className="block text-[15px] font-semibold text-ink">{pace.title}</span>
                <span className="block mt-[4px] text-[13.5px] leading-[1.55] text-ink-2">{pace.text}</span>
                {pace.chip && (
                  <span className="inline-block mt-[8px] rounded-full px-[9px] py-[1px] text-[11.5px] font-semibold"
                        style={{ background: "var(--done-soft)", color: "var(--done-ink)" }}>{pace.chip}</span>
                )}
              </span>
            </label>
          );
        })}
      </div>
    </section>
  );
}
