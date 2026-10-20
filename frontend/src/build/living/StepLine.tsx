import type { AuthoringSession } from "../../api/types";
import { authorOf, processName, stepWords, type OfferProgress } from "./format";

type Decision = AuthoringSession["history"][number];

/** **The plan as a metro line**: the goal, every step decided so far with who settled it, the step
 *  on offer, then how many are still to come.
 *
 *  The steps to come are counted, not named: the engine offers one step at a time and does not send
 *  the names of the rest, so naming them here would be a guess. A decided step selects itself on the
 *  canvas; nothing on this line changes a decision.
 */
export function StepLine({
  session,
  selected,
  onSelect,
}: {
  session: AuthoringSession;
  selected: string | null;
  onSelect: (node: string | null) => void;
}) {
  const goal = [...session.history].reverse().find((d) => d.kind === "goal" && d.state === "accepted");
  const steps = session.history.filter((d) => d.block.kind === "step_proposal");
  const pending = session.pending_proposal;
  const offered = pending?.block.kind === "step_proposal" ? pending.block.node : null;
  const active = session.progress?.active ?? null;
  const toCome = active ? active.total - active.position : 0;

  return (
    <ol aria-label="the plan" className="relative m-0 p-0 flex flex-col
                                         before:content-[''] before:absolute before:left-[5px] before:top-[14px]
                                         before:bottom-[14px] before:w-[2px] before:bg-[var(--line)]">
      {goal && (
        <Row dot="done" name="Goal" detail={goalWords(goal)} by={goal.actor_kind === "model" ? "confirmed by the policy" : "you confirmed"} />
      )}
      {answered(session).map((decision) => (
        <li key={decision.id} className="relative list-none pl-[24px]">
          <span aria-hidden className="absolute left-[3px] top-[12px] w-[8px] h-[8px] rounded-full" style={{ background: "var(--line-2)" }} />
          <AnswerLine decision={decision} />
        </li>
      ))}
      {steps.map((decision) => {
        const node = decision.block.kind === "step_proposal" ? decision.block.node : "";
        const went = decision.state === "rejected" || decision.state === "stale";
        return (
          <Row key={decision.id} dot={went ? "gone" : "done"} name={processName(node)}
               detail={`${stepAt(offeredAt(decision))}${went ? "" : TIER_WORD[decision.block.kind === "step_proposal" ? decision.block.tier : 0] ?? ""}`}
               by={verbOf(decision)}
               selected={selected === node} onClick={went ? undefined : () => onSelect(node)} />
        );
      })}
      {offered && (
        <Row dot="now" name={processName(offered)} detail={stepAt(active)} by="waiting for you" current
             selected={selected === offered} onClick={() => onSelect(offered)} />
      )}
      {toCome > 0 && (
        <Row dot="later" name={`${toCome} more ${toCome === 1 ? "step" : "steps"}`} detail="" by="" />
      )}
    </ol>
  );
}

type Dot = "done" | "now" | "later" | "gone";

const DOT: Record<Dot, React.CSSProperties> = {
  done: { background: "var(--ink-2)", borderColor: "var(--ink-2)" },
  now: { background: "var(--surface)", borderColor: "var(--now)", boxShadow: "0 0 0 3px var(--now-soft)" },
  later: { background: "var(--surface)", borderColor: "var(--line-2)" },
  gone: { background: "var(--surface)", borderColor: "var(--line-2)", borderStyle: "dashed" },
};

function Row({ dot, name, detail, by, current = false, selected = false, onClick }: {
  dot: Dot; name: string; detail: string; by: string;
  current?: boolean; selected?: boolean; onClick?: () => void;
}) {
  const body = (
    <>
      <span aria-hidden className="absolute left-0 top-[10px] w-[12px] h-[12px] rounded-full border-2" style={DOT[dot]} />
      <span className={`${dot === "later" || name === "Goal" ? "text-[13px]" : "font-data text-[12.5px]"} shrink-0 ${current ? "font-semibold text-ink" : selected ? "text-now-ink" : "text-ink"}`}>
        {name}
      </span>
      <span className="text-[12px] text-ink-3 truncate min-w-0">{detail}</span>
      <span className={`ml-auto text-[11.5px] shrink-0 ${current ? "text-now-ink" : "text-ink-3"}`}>{by}</span>
    </>
  );
  return (
    <li className="relative list-none" aria-current={current ? "step" : undefined}>
      {onClick ? (
        <button type="button" onClick={onClick} aria-pressed={selected}
                className="w-full flex items-baseline gap-[10px] py-[6px] pl-[24px] pr-0 bg-transparent border-0
                           text-left cursor-pointer rounded-control focus-visible:shadow-[var(--ring)]">
          {body}
        </button>
      ) : (
        <div className="flex items-baseline gap-[10px] py-[6px] pl-[24px]">{body}</div>
      )}
    </li>
  );
}

function goalWords(decision: Decision): string {
  if (decision.block.kind !== "goal_summary") return "";
  const goal = decision.block.goal as { have?: { type_id: string }[]; want?: string[] };
  const have = (goal.have ?? []).map((h) => h.type_id);
  const want = goal.want ?? [];
  return have.length && want.length ? `${have.join(", ")} → ${want.join(", ")}` : decision.block.get;
}

/** The position a decided step was offered at, or `null` for an offer older than the record. */
function offeredAt(decision: Decision): OfferProgress | null {
  return (decision.envelope as { progress?: OfferProgress | null } | null | undefined)?.progress ?? null;
}

const stepAt = (progress: OfferProgress | null | undefined) => (progress ? stepWords(progress).toLowerCase() : "");

/** What a decided step's row says about its tier: tier 4 stays open for review; 1–3 say nothing. */
const TIER_WORD: Record<number, string> = { 4: " · open" };

/** Who settled a step, in the words the rail used: a withdrawn offer says why it went. */
function verbOf(decision: Decision): string {
  if (decision.state === "rejected") return "skipped";
  if (decision.state === "stale") return "answers changed";
  const author = authorOf(decision);
  const verb = author === "model" ? "model chose" : author === "person" ? "you chose"
    : author === "unknown" ? "chooser unknown" : "settled";
  const applies = decision.applicability && decision.applicability !== "retained" ? ` · ${decision.applicability}` : "";
  return verb + applies;
}

/** The gaps and pacing questions answered so far, oldest first. */
export function answered(session: AuthoringSession): Decision[] {
  return session.history.filter((d) =>
    (d.kind === "gap" || d.kind === "pacing") && d.state === "accepted" && d.block.kind === "question");
}

/** One answered question: what was asked, the answer whole, and where the answer came from.
 *
 *  **The answer is never the part cut short** (issue 169): a long question truncates, and a typed
 *  value is shown as the value, not the field's label. A sample the AI read is not one an inspector
 *  measured (issue 135), and the line says which.
 */
export function AnswerLine({ decision }: { decision: Decision }) {
  const block = decision.block;
  if (block.kind !== "question") return null;
  const answer = decision.answer
    ?? block.options.find((o) => o.id === decision.chosen_option)?.label
    ?? decision.chosen_option ?? "";
  const model = decision.actor_kind === "model";
  const sampled = decision.chosen_option === "upload";
  const aiRead = sampled && (block as { reading?: { state?: string } | null }).reading?.state === "read";
  return (
    <div className="flex items-baseline gap-[10px] py-[5px]">
      <span className="text-[12px] text-ink-2 truncate min-w-0">{block.asks}</span>
      <span data-testid={`gap-answer-${decision.id}`} className="font-data text-[12px] text-ink shrink-0">{answer}</span>
      <span className="ml-auto text-[11.5px] text-ink-3 shrink-0">
        {model ? "read by AI" : aiRead ? "from your sample" : sampled ? "measured from your sample" : "you said"}
      </span>
    </div>
  );
}
