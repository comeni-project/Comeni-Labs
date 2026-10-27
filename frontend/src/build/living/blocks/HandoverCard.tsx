import type { AuthoringSession } from "../../../api/types";
import { open, type AnsweredStep } from "../../useBuilder";
import { processName, stepsInOrder } from "../format";
import { valuesOf } from "../values";
import { Primary, Secondary } from "./parts";

/** **The hand-over** (issue 393; the one-builder design's *My calls*): when a build finishes, the
 *  conversation says so in four parts, composed from records the page already holds, no model
 *  call — what was built, how its values were decided (counted by evidence, issue 397), what
 *  still needs you (Run stays locked, issue 385), and what next. The engine's own sentence stays
 *  under it as the record. */
export function HandoverCard({ session, steps, summary, runnable, onRun, onView, onSelect }: {
  session: AuthoringSession;
  steps: Record<string, AnsweredStep>;
  /** The engine's wrap-up sentence. */
  summary: string;
  runnable: boolean;
  onRun: () => void;
  onView: (view: "canvas" | "artifact") => void;
  onSelect: (node: string | null) => void;
}) {
  const goal = [...session.history].reverse().find((d) => d.kind === "goal" && d.state === "accepted");
  const shape = goal?.block.kind === "goal_summary"
    ? goal.block.goal as { have?: { type_id: string }[]; want?: string[] } : {};
  const have = (shape.have ?? []).map((h) => h.type_id);
  const want = shape.want ?? [];
  const order = stepsInOrder(session);
  const values = valuesOf(order.map((node) => steps[node]).filter(Boolean));
  const counts = ([["settled", values.settled], ["measured", values.measured], ["read by AI", values.read],
    ["optional", values.optional], [values.open === 1 ? "needs you" : "need you", values.open]] as const)
    .filter(([, n]) => n > 0);
  const needing = order.map((node) => [node, (steps[node]?.settings ?? []).filter(open).length] as const)
    .filter(([, n]) => n > 0);
  const locked = needing.length > 0;

  return (
    <section aria-label="the hand-over" className="rounded-panel border px-4 py-4 flex flex-col gap-4"
             style={{ borderColor: "var(--done)", background: "var(--surface)" }}>
      <p className="m-0 text-[15px] font-semibold text-ink">The pipeline is built.</p>
      <Part label="What you built">
        {have.length > 0 && want.length > 0 && (
          <p className="m-0 font-data text-[12.5px] text-ink">{have.join(", ")} → {want.join(", ")}</p>
        )}
        <p className="m-0 mt-1 font-data text-[11.5px] text-ink-2">{order.map(processName).join(" → ")}</p>
      </Part>
      <Part label="How its values were decided">
        <div className="flex flex-wrap gap-[6px]">
          {counts.map(([word, n]) => (
            <button key={word} type="button" onClick={() => onView("artifact")}
                    className="px-[9px] py-[3px] rounded-full border text-[12px] cursor-pointer focus-visible:shadow-[var(--ring)]"
                    style={CHIP[word] ?? CHIP.settled}>
              {n} {word}
            </button>
          ))}
        </div>
      </Part>
      {locked && (
        <Part label="What still needs you">
          <div className="flex flex-col gap-[6px]">
            {needing.map(([node, n]) => (
              <button key={node} type="button" onClick={() => onSelect(node)}
                      className="text-left px-[10px] py-[7px] rounded-button border bg-transparent text-[13px] text-ink
                                 cursor-pointer hover:bg-[var(--hover)] focus-visible:shadow-[var(--ring)]"
                      style={{ borderColor: "var(--needs-you)" }}>
                {processName(node)} · {n} {n === 1 ? "value" : "values"}
              </button>
            ))}
          </div>
        </Part>
      )}
      <Part label="Next">
        <div className="flex flex-wrap items-center gap-2">
          <Primary disabled={locked || !runnable} onClick={onRun}>Run it</Primary>
          <Secondary onClick={() => onView("artifact")}>Look at the pipeline file</Secondary>
          <span className="text-[12.5px] text-ink-2">or keep asking below.</span>
        </div>
        {locked && <p className="m-0 mt-2 text-[12.5px] text-needs-you-ink">Answer the values above first.</p>}
      </Part>
      <p className="m-0 font-data text-[10.5px] leading-[1.5] text-ink-3">{summary}</p>
    </section>
  );
}

function Part({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <section aria-label={label}>
      <h3 className="m-0 mb-[6px] text-label text-ink-3">{label}</h3>
      {children}
    </section>
  );
}

const CHIP: Record<string, React.CSSProperties> = {
  settled: { borderColor: "var(--line-2)", color: "var(--ink-2)", background: "var(--surface)" },
  measured: { borderColor: "transparent", color: "var(--measured-ink)", background: "var(--measured-soft)" },
  "read by AI": { borderColor: "transparent", color: "var(--measured-ink)", background: "var(--measured-soft)" },
  optional: { borderColor: "var(--line)", color: "var(--ink-3)", background: "transparent" },
  "needs you": { borderColor: "transparent", color: "var(--needs-you-ink)", background: "var(--needs-you-soft)" },
  "need you": { borderColor: "transparent", color: "var(--needs-you-ink)", background: "var(--needs-you-soft)" },
};
