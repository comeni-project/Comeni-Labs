import { useId, useState } from "react";

import type { AuthoringProposal, GoalIn } from "../../../api/types";
import { BlockFrame, Primary, Secondary } from "./parts";

type Chosen = { have: string[]; want: string[] };

/** The goal read back — the plain-language summary, and the typed goal it stands for, editable.
 *
 * **Editing a structured field needs no model call.** A person who removes `qc.report` or adds
 * `counts.matrix` has corrected a field the engine can check, so the edit goes straight to the
 * decision with the goal attached and the server holds it to the declared vocabulary (`MI0204`)
 * exactly as it holds a model's. A new *prose* interpretation — *actually these are single-end* —
 * is a different act, and is said in the composer.
 */
export function GoalCard({
  proposal,
  vocabulary,
  busy,
  onConfirm,
  onReject,
}: {
  proposal: AuthoringProposal;
  /** Declared type ids and their states. `null` while it loads — the card is still answerable. */
  vocabulary: Record<string, string[]> | null;
  busy: boolean;
  onConfirm: (edited?: GoalIn) => void;
  onReject: () => void;
}) {
  const block = proposal.block;
  const addHave = useId();
  const addWant = useId();
  const original = block.kind === "goal_summary" ? goalOf(block.goal) : { have: [], want: [] };
  const [chosen, setChosen] = useState<Chosen>(original);
  if (block.kind !== "goal_summary") return null;

  const edited =
    chosen.have.join() !== original.have.join() || chosen.want.join() !== original.want.join();
  const types = vocabulary ? Object.keys(vocabulary) : [];

  const confirm = () => {
    if (!edited) return onConfirm();
    const goal = block.goal as GoalIn;
    // **An input the person kept keeps its states.** Rebuilding `have` from bare type ids would
    // turn `fastq.reads[trimmed]` into `fastq.reads` on every edit that touched something else —
    // a quiet change to the goal nobody made, caught by the typecheck asking where `states` went.
    const kept = new Map((goal.have ?? []).map((entry) => [entry.type_id, entry]));
    onConfirm({
      ...goal,
      have: chosen.have.map((type_id) => kept.get(type_id) ?? { type_id, states: [] }),
      want: chosen.want,
    });
  };

  const list = (side: keyof Chosen, labelId: string, label: string) => (
    <div className="mb-3 grid grid-cols-[76px_1fr] gap-x-3 items-start">
      <span className="font-data text-[9.5px] tracking-[.15em] uppercase text-ink-3 pt-[6px]">
        {side}
      </span>
      <div>
      <ul aria-label={label} className="m-0 p-0 flex flex-wrap gap-[6px]">
        {chosen[side].map((type_id) => (
          <li key={type_id} className="list-none flex items-center gap-2 px-2 py-[3px] border font-data text-[11px] text-ink"
              style={{ borderColor: "var(--line-2)" }}>
            {type_id}
            <button
              type="button"
              aria-label={`remove ${type_id} from ${label}`}
              onClick={() => setChosen({ ...chosen, [side]: chosen[side].filter((t) => t !== type_id) })}
              className="bg-transparent border-0 p-0 text-ink-3 hover:text-ink cursor-pointer
                         focus-visible:shadow-[var(--ring)]"
            >
              ×
            </button>
          </li>
        ))}
      </ul>
      {types.length > 0 && (
        <select
          id={labelId}
          aria-label={`add to ${label}`}
          value=""
          onChange={(e) => {
            const type_id = e.target.value;
            if (type_id && !chosen[side].includes(type_id)) {
              setChosen({ ...chosen, [side]: [...chosen[side], type_id] });
            }
          }}
          className="mt-2 font-data text-[11px] bg-transparent text-ink-2 border px-2 py-[3px]"
          style={{ borderColor: "var(--line)" }}
        >
          <option value="">+ add a type</option>
          {types.filter((t) => !chosen[side].includes(t)).map((t) => (
            <option key={t} value={t}>{t}</option>
          ))}
        </select>
      )}
      </div>
    </div>
  );

  return (
    <BlockFrame
      label="the goal as understood"
      title="Goal"
      aside={edited ? "edited" : "editable"}
      actions={
        <>
          <Primary data-testid="accept-goal" disabled={busy} onClick={confirm}>
            {busy ? "Confirming…" : "That's right"}
          </Primary>
          <Secondary data-testid="reject-goal" disabled={busy} onClick={onReject}>
            Not quite
          </Secondary>
        </>
      }
    >
      {/* **The typed goal first** — it is what the pipeline is built from and what the person is
          checking. The sentences beneath say the same thing in words, quieter, for reading. */}
      {list("have", addHave, "what you have")}
      {list("want", addWant, "what you want")}
      <p className="m-0 mt-1 text-[12px] leading-[1.6] text-ink-3">
        {block.have} — {block.do} — {block.get}.
      </p>
    </BlockFrame>
  );
}

function goalOf(goal: unknown): Chosen {
  const g = goal as { have?: { type_id: string }[]; want?: string[] };
  return { have: (g.have ?? []).map((entry) => entry.type_id), want: [...(g.want ?? [])] };
}
