import type { AuthoringSession, Step } from "../../api/types";
import { authorOf, processName, type OfferProgress } from "./format";
import { valuesOf } from "./values";

type Decision = AuthoringSession["history"][number];

/** **The plan as a metro line** (the *Build* board): the goal, every step decided so far with who
 *  settled it, the step on offer, then the steps the walk will still offer, by their place.
 *
 *  The line is green as far as the walk has reached and grey after; a step whose values include
 *  one measured from the data is ringed in the measured colour and says how many. The steps to come
 *  are the server's (`progress.upcoming`), named by process until roles carry a plain name. A
 *  decided step selects itself on the canvas; nothing on this line changes a decision.
 */
export function StepLine({
  session,
  steps = {},
  selected,
  onSelect,
}: {
  session: AuthoringSession;
  /** The frame's steps, for how many values each one measured. */
  steps?: Record<string, Step>;
  selected: string | null;
  onSelect: (node: string | null) => void;
}) {
  const goal = [...session.history].reverse().find((d) => d.kind === "goal" && d.state === "accepted");
  const decided = session.history.filter((d) => d.block.kind === "step_proposal");
  const pending = session.pending_proposal;
  const offered = pending?.block.kind === "step_proposal" ? pending.block.node : null;
  const active = session.progress?.active ?? null;
  const upcoming = offered ? session.progress?.upcoming ?? [] : [];

  const rows: Entry[] = [
    ...(goal ? [{ key: "goal", dot: "done" as Dot, row: (
      <Row name="Goal" plain detail={goalWords(goal)} by={goal.actor_kind === "model" ? "confirmed by the policy" : "you confirmed"} />
    ) }] : []),
    ...answered(session).map((decision) => ({ key: decision.id, dot: "answer" as Dot, row: <AnswerLine decision={decision} /> })),
    ...decided.map((decision) => {
      const node = decision.block.kind === "step_proposal" ? decision.block.node : "";
      const went = decision.state === "rejected" || decision.state === "stale";
      const measured = went || !steps[node] ? 0 : valuesOf([steps[node]]).measured;
      return { key: decision.id, dot: (went ? "gone" : measured > 0 ? "measured" : "done") as Dot, row: (
        <Row name={processName(node)}
             detail={`${placeOf(offeredAt(decision))}${went ? "" : TIER_WORD[decision.block.kind === "step_proposal" ? decision.block.tier : 0] ?? ""}`}
             by={verbOf(decision)} measured={measured}
             selected={selected === node} onClick={went ? undefined : () => onSelect(node)} />
      ) };
    }),
    ...(offered ? [{ key: "offered", dot: "now" as Dot, current: true, row: (
      <Row name={processName(offered)} detail={placeOf(active)} by="waiting for you" current
           selected={selected === offered} onClick={() => onSelect(offered)} />
    ) }] : []),
    ...upcoming.map((step) => ({ key: `later-${step.node}`, dot: "later" as Dot, row: (
      <Row name={processName(step.node)} detail={`step ${step.position}`} by="" later />
    ) })),
  ];

  return (
    <ol aria-label="the plan" className="m-0 p-0 flex flex-col">
      {rows.map((entry, i) => (
        <li key={entry.key} data-dot={entry.dot} data-line={i === 0 ? undefined : lineOf(entry.dot)}
            aria-current={entry.current ? "step" : undefined} className="relative list-none pl-[24px]">
          {i > 0 && <Segment from={0} to={DOT_MIDDLE[entry.dot]} line={lineOf(entry.dot)} />}
          {i < rows.length - 1 && <Segment from={DOT_MIDDLE[entry.dot]} line={lineOf(rows[i + 1].dot)} />}
          <span aria-hidden className="absolute rounded-full" style={DOT[entry.dot]} />
          {entry.row}
        </li>
      ))}
    </ol>
  );
}

type Dot = "done" | "measured" | "now" | "later" | "gone" | "answer";
type Entry = { key: string; dot: Dot; current?: boolean; row: React.ReactNode };

/** Reached as far as the step on offer; everything after it is still to come. */
const lineOf = (dot: Dot): "reached" | "later" => (dot === "later" ? "later" : "reached");

/** Where each dot's middle sits from its row's top — where the line meets it. */
const DOT_MIDDLE: Record<Dot, number> = { done: 16, measured: 16, now: 16, later: 16, gone: 16, answer: 14 };

function Segment({ from, to, line }: { from: number; to?: number; line: "reached" | "later" }) {
  return (
    <span aria-hidden className="absolute left-[5px] w-[2px]"
          style={{ top: from, ...(to === undefined ? { bottom: 0 } : { height: to - from }),
                   background: line === "reached" ? "var(--done)" : "var(--line)" }} />
  );
}

const RING = { top: 10, left: 0, width: 12, height: 12, borderWidth: 2, borderStyle: "solid" } as const;

const DOT: Record<Dot, React.CSSProperties> = {
  done: { ...RING, background: "var(--ink-2)", borderColor: "var(--ink-2)" },
  measured: { ...RING, background: "var(--surface)", borderColor: "var(--measured)" },
  now: { ...RING, borderColor: "var(--now)",
         background: "radial-gradient(circle, var(--now) 0 2.5px, var(--surface) 3px)",
         boxShadow: "0 0 0 3px var(--now-soft)" },
  later: { ...RING, background: "var(--surface)", borderColor: "var(--line-2)" },
  gone: { ...RING, background: "var(--surface)", borderColor: "var(--line-2)", borderStyle: "dashed" },
  answer: { top: 10, left: 3, width: 8, height: 8, background: "var(--line-2)" },
};

function Row({ name, detail, by, measured = 0, plain = false, current = false, later = false, selected = false, onClick }: {
  name: string; detail: string; by: string; measured?: number;
  plain?: boolean; current?: boolean; later?: boolean; selected?: boolean; onClick?: () => void;
}) {
  const body = (
    <>
      <span title={name} className={`${plain ? "text-[13px] font-semibold" : "font-data text-[12.5px]"} truncate min-w-0 shrink
                        ${current ? "font-semibold text-ink" : later ? "text-ink-3" : selected ? "text-now-ink" : "text-ink"}`}>
        {name}
      </span>
      <span className="text-[12px] text-ink-3 truncate min-w-0 shrink-[2]">{detail}</span>
      <span className={`ml-auto text-[11.5px] shrink-0 whitespace-pre ${current ? "text-now-ink" : "text-ink-3"}`}>
        {by}
        {measured > 0 && <>{" · "}<span className="font-semibold text-measured-ink">{measured} measured</span></>}
      </span>
    </>
  );
  return onClick ? (
    <button type="button" onClick={onClick} aria-pressed={selected}
            className="w-full flex items-baseline gap-[10px] py-[6px] px-0 bg-transparent border-0
                       text-left cursor-pointer rounded-control focus-visible:shadow-[var(--ring)]">
      {body}
    </button>
  ) : (
    <div className="flex items-baseline gap-[10px] py-[6px]">{body}</div>
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

/** *step 4*, as the boards say it; *review step 4 again* when it was reviewed before. */
const placeOf = (progress: OfferProgress | null | undefined) =>
  !progress ? "" : progress.again ? `review step ${progress.position} again` : `step ${progress.position}`;

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
 *  **Nothing is cut short**: the question wraps (issue 306; issue 169 kept the answer whole), and a typed
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
      <span className="text-[12px] text-ink-2 min-w-0 break-words">{block.asks}</span>
      <span data-testid={`gap-answer-${decision.id}`} className="font-data text-[12px] text-ink shrink-0">{answer}</span>
      <span className="ml-auto text-[11.5px] text-ink-3 shrink-0">
        {model ? "read by AI" : aiRead ? "from your sample" : sampled ? "measured from your sample" : "you said"}
      </span>
    </div>
  );
}
