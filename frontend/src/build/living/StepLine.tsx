import type { AuthoringSession } from "../../api/types";
import { authorOf, processName, type OfferProgress } from "./format";

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
                                         before:content-[''] before:absolute before:left-[5px] before:top-3
                                         before:bottom-3 before:w-[2px] before:bg-[var(--line)]">
      {goal && (
        <Row dot="done" name="Goal" detail={goalWords(goal)} by={goal.actor_kind === "model" ? "confirmed by the policy" : "you confirmed"} />
      )}
      {steps.map((decision) => {
        const node = decision.block.kind === "step_proposal" ? decision.block.node : "";
        const went = decision.state === "rejected" || decision.state === "stale";
        return (
          <Row key={decision.id} dot={went ? "gone" : "done"} name={processName(node)}
               detail={stepAt(offeredAt(decision))} by={verbOf(decision)}
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
      <span aria-hidden className="absolute left-0 top-[9px] w-3 h-3 rounded-full border-2" style={DOT[dot]} />
      <span className={`font-data text-[12.5px] shrink-0 ${current ? "font-semibold text-ink" : selected ? "text-now-ink" : "text-ink"}`}>
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
                className="w-full flex items-baseline gap-[10px] py-[6px] pl-6 pr-0 bg-transparent border-0
                           text-left cursor-pointer rounded-[8px] focus-visible:shadow-[var(--ring)]">
          {body}
        </button>
      ) : (
        <div className="flex items-baseline gap-[10px] py-[6px] pl-6">{body}</div>
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

const stepAt = (progress: OfferProgress | null | undefined) => (progress ? `step ${progress.position}` : "");

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
