import type { AuthoringSession, AuthoringVocabulary } from "../../api/types";
import { CurrentFacts, type CorrectFact } from "./CurrentFacts";

/** **What was understood** (the *Describe* board's record, one builder plan 3): the person's
 *  sentence, then each answer and fact with where it came from, correctable line by line. Beside
 *  the conversation while describing; one switch from the canvas while building. */
export function Understood({ session, declarations, onCorrect, onRelease, onUnits, onTable, disabled, openRequest = 0,
  highlight = null }: {
  session: AuthoringSession;
  declarations?: AuthoringVocabulary["measurements"];
  onCorrect?: CorrectFact;
  onRelease?: (type: string, states: string[]) => Promise<unknown>;
  onUnits?: (type: string, on: boolean) => Promise<unknown>;
  onTable?: (type: string, on: boolean) => Promise<unknown>;
  disabled: boolean;
  openRequest?: number;
  /** A line an announcement points at, lit for a moment. */
  highlight?: string | null;
}) {
  const sentence = session.turns.find((turn) => turn.role === "person")?.text ?? null;
  return (
    <section aria-label="What was understood" className="h-full min-h-0 overflow-auto px-[24px] py-[20px] flex flex-col gap-4">
      <header>
        <h2 className="m-0 text-heading font-semibold text-ink">What was understood</h2>
        <p className="m-0 mt-1 text-[13px] text-ink-2">This becomes your pipeline's goal. Wrong? Correct a line.</p>
      </header>
      {sentence && (
        <blockquote data-testid="your-sentence"
                    className="m-0 rounded-panel border px-5 py-4 text-[15px] leading-[1.55] text-ink"
                    style={{ borderColor: "var(--now-line)", background: "var(--surface)", boxShadow: "0 0 0 3px var(--now-soft)" }}>
          {sentence}
        </blockquote>
      )}
      <div className="rounded-panel border border-line px-5 py-4" style={{ background: "var(--surface)" }}>
        <CurrentFacts session={session} declarations={declarations} onCorrect={onCorrect} onRelease={onRelease}
                      onUnits={onUnits} onTable={onTable}
                      openRequest={openRequest} open disabled={disabled} highlight={highlight} />
      </div>
    </section>
  );
}
