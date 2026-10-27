import type { AuthoringProposal } from "../../api/types";
import { questionTitle } from "./format";

/** **The open question, docked above the composer** (one builder plan 3, *the open question
 *  follows you*). Once the person talks past a question, its full card leaves the end of the
 *  conversation; this keeps it answerable where they type. The answers are the question's own,
 *  sent as the card would send them; anything the dock cannot hold (a typed value, a sample, the
 *  goal) is one click away in the full card. Under 640 px it folds to its title. */
export function QuestionDock({ proposal, busy, onAnswer, onShow }: {
  proposal: AuthoringProposal;
  busy: boolean;
  onAnswer: (option: string) => void;
  onShow: () => void;
}) {
  const block = proposal.block;
  const answers = block.kind === "question"
    ? block.options.filter((o) => o.id !== "value" && o.id !== "upload").map((o) => ({ id: o.id, label: o.label }))
    : block.kind === "step_proposal" ? [{ id: "keep", label: "Add it" }] : [];
  return (
    <section aria-label="the open question" data-testid="question-dock"
             className="mx-[16px] mt-[8px] px-[12px] py-[9px] rounded-button border"
             style={{ borderColor: "var(--needs-you)", background: "var(--needs-you-soft)" }}>
      <details open className="group">
        <summary className="flex items-baseline gap-2 cursor-pointer list-none text-[13px] text-ink">
          <span className="font-semibold text-needs-you-ink">Still needed:</span>
          <span className="flex-1 min-w-0 truncate">{questionTitle(proposal)}</span>
          <button type="button" onClick={(e) => { e.preventDefault(); onShow(); }}
                  className="bg-transparent border-0 p-0 text-[12px] text-now-ink underline cursor-pointer">
            show the full question
          </button>
        </summary>
        {answers.length > 0 && (
          <div className="flex flex-wrap gap-[6px] mt-[8px]">
            {answers.map((a) => (
              <button key={a.id} type="button" disabled={busy} onClick={() => onAnswer(a.id)}
                      className="px-[10px] py-[5px] rounded-full border text-[12.5px] text-ink cursor-pointer
                                 disabled:opacity-40 focus-visible:shadow-[var(--ring)]"
                      style={{ borderColor: "var(--line-2)", background: "var(--surface)" }}>
                {a.label}
              </button>
            ))}
          </div>
        )}
      </details>
    </section>
  );
}
