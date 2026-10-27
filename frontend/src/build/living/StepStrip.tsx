import type { AuthoringSession } from "../../api/types";
import { processName } from "./format";
import { stageOf } from "./stage";

/** **The plan, slim, pinned above the conversation** (one builder plan 3): the steps decided, the
 *  one on offer, and the steps still to come, each one click from opening; then where the walk is,
 *  which opens the whole plan (the step line: who decided each step, and how) below it. */
export function StepStrip({ session, selected, onSelect, planOpen = false, onTogglePlan }: {
  session: AuthoringSession;
  selected: string | null;
  onSelect: (node: string | null) => void;
  /** Whether the whole plan (the step line: who decided each step, and how) is open below. */
  planOpen?: boolean;
  onTogglePlan?: () => void;
}) {
  const decided = session.history
    .filter((d) => d.block.kind === "step_proposal" && d.state === "accepted")
    .map((d) => (d.block.kind === "step_proposal" ? d.block.node : ""));
  const pending = session.pending_proposal;
  const offered = pending?.block.kind === "step_proposal" ? pending.block.node : null;
  const later = offered ? (session.progress?.upcoming ?? []).map((s) => s.node) : [];
  const steps = [...decided.map((node) => ({ node, state: "done" })),
    ...(offered ? [{ node: offered, state: "now" }] : []),
    ...later.map((node) => ({ node, state: "later" }))];
  const active = session.progress?.active ?? null;
  const describing = steps.length === 0 && stageOf(session) === "describe";

  return (
    <nav aria-label="the plan"
         className="flex items-center gap-[6px] px-[16px] py-[10px] border-b border-line text-[12px] text-ink-2
                    overflow-x-auto whitespace-nowrap">
      {describing ? (
        <span><span className="font-semibold text-now-ink">Describing</span> · then you choose how to build</span>
      ) : steps.map(({ node, state }) => (
        <button key={node} type="button" aria-current={state === "now" ? "step" : undefined}
                aria-pressed={selected === node} onClick={() => onSelect(node)}
                className="px-[8px] py-[3px] rounded-full border font-data text-[11px] cursor-pointer
                           focus-visible:shadow-[var(--ring)]"
                style={STYLE[state]}>
          {processName(node)}
        </button>
      ))}
      {!describing && (
        <button type="button" aria-label="the whole plan" aria-expanded={planOpen} onClick={onTogglePlan}
                className="ml-auto pl-2 bg-transparent border-0 p-0 text-[12px] text-ink-2 cursor-pointer
                           hover:text-ink focus-visible:shadow-[var(--ring)]">
          {active ? `Step ${active.position} of ${active.total}` : "The plan"} {planOpen ? "▴" : "▾"}
        </button>
      )}
    </nav>
  );
}

const STYLE: Record<string, React.CSSProperties> = {
  done: { background: "var(--done-soft)", color: "var(--done-ink)", borderColor: "var(--done-soft)" },
  now: { background: "var(--now-soft)", color: "var(--now-ink)", borderColor: "var(--now-line)", fontWeight: 600 },
  later: { background: "transparent", color: "var(--ink-3)", borderColor: "var(--line)" },
};
