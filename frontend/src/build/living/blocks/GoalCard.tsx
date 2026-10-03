import { useId, useState } from "react";

import type { AuthoringProposal, AuthoringSession, GoalIn } from "../../../api/types";
import { BlockFrame, Primary, Secondary } from "./parts";
import { piece } from "./piece";

type Chosen = { have: string[]; want: string[] };
type Fact = AuthoringSession["facts"][number];

/** Where a fact came from, in the words the protocol's diagram uses. */
const SOURCE: Record<Fact["source"], string> = {
  person_said: "you said",
  measured: "measured",
  model_read: "read by AI",
  open: "left open",
};


/** A fact's source, and **what measured it** when a sample did (issue 134). *From 1 sample* is
 *  a constant on purpose: one sample is all the conversation accepts (issue 218 changes that). */
const sourceLabel = (f: Fact) =>
  f.source === "measured" && f.pieces?.length
    ? `measured · ${piece(f.pieces[0])} · from 1 sample`
    : SOURCE[f.source];

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
  facts = [],
}: {
  proposal: AuthoringProposal;
  /** Declared type ids and their states. `null` while it loads — the card is still answerable. */
  vocabulary: Record<string, string[]> | null;
  busy: boolean;
  onConfirm: (edited?: GoalIn) => void;
  onReject: () => void;
  /** What gathering learned, each with its source (14.7.3). Empty for a goal nobody gathered. */
  facts?: Fact[];
}) {
  const block = proposal.block;
  const addHave = useId();
  const addWant = useId();
  const original = block.kind === "goal_summary" ? goalOf(block.goal) : { have: [], want: [] };
  const [chosen, setChosen] = useState<Chosen>(original);
  // **States belong to the input the person is holding, not to its type id** (issue 111). Looked up
  // by type id from the model's goal, an invented state came back every time the type was
  // removed and added again, and nothing else could take it off.
  const [held, setHeld] = useState<Record<string, string[]>>(() =>
    block.kind === "goal_summary" ? Object.fromEntries(statesOf(block.goal).have) : {});
  // Constraints the model wrote are offered, not applied: only the ones kept reach the goal
  // (issue 176). Keyed on the constraint as spelled.
  const [chosenSuggestions, setChosenSuggestions] = useState<string[]>([]);
  if (block.kind !== "goal_summary") return null;

  const states = statesOf(block.goal);
  const statesMoved = original.have.some(
    (t) => (held[t] ?? []).join() !== (states.have.get(t) ?? []).join());
  const suggested = block.suggested ?? [];
  const keyOf = (r: { type_id: string; states?: string[] }) =>
    `${r.type_id} [${(r.states ?? []).join(", ")}]`;
  const edited = chosenSuggestions.length > 0 || statesMoved ||
    chosen.have.join() !== original.have.join() || chosen.want.join() !== original.want.join();
  const types = vocabulary ? Object.keys(vocabulary) : [];
  // **Each input once, its source on its chip** (issue 172); the facts list below is for
  // measurements.
  const sourceOf = new Map(
    facts.filter((f) => f.kind === "input").map((f) => [f.subject, sourceLabel(f)] as const));
  const measured = facts.filter((f) => f.kind === "measurement");

  const confirm = () => {
    if (!edited) return onConfirm();
    const goal = block.goal as GoalIn;
    // **An input the person kept keeps its states.** Rebuilding `have` from bare type ids would
    // turn `fastq.reads[trimmed]` into `fastq.reads` on every edit that touched something else —
    // a quiet change to the goal nobody made, caught by the typecheck asking where `states` went.
    const kept = new Map((goal.have ?? []).map((entry) => [entry.type_id, entry]));
    const required = [
      ...(goal.constraints?.required_states ?? []),
      ...suggested.filter((r) => chosenSuggestions.includes(keyOf(r))),
    ];
    onConfirm({
      ...goal,
      constraints: { ...(goal.constraints ?? {}), required_states: required },
      have: chosen.have.map((type_id) => ({
        ...(kept.get(type_id) ?? { type_id }),
        type_id,
        states: held[type_id] ?? [],
      })),
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
            {side === "want" ? spelled(type_id, states.want.get(type_id)) : (
              <span>
                {type_id}
                {(held[type_id] ?? []).length > 0 && (
                  <>
                    [
                    {(held[type_id] ?? []).map((state, i) => (
                      <span key={state}>
                        {i > 0 && ", "}
                        <button
                          type="button"
                          title="not true of this input — take it off"
                          aria-label={`remove state ${state} from ${type_id}`}
                          onClick={() => setHeld({ ...held, [type_id]: held[type_id].filter((x) => x !== state) })}
                          className="bg-transparent border-0 p-0 font-data text-[11px] text-ink cursor-pointer
                                     hover:line-through focus-visible:shadow-[var(--ring)]"
                        >
                          {state}
                        </button>
                      </span>
                    ))}
                    ]
                  </>
                )}
              </span>
            )}
            {side === "have" && sourceOf.has(type_id) && (
              <span className="font-data text-[9.5px] text-ink-3">{sourceOf.get(type_id)}</span>
            )}
            <button
              type="button"
              aria-label={`remove ${type_id} from ${label}`}
              onClick={() => {
                setChosen({ ...chosen, [side]: chosen[side].filter((t) => t !== type_id) });
                if (side === "have") setHeld({ ...held, [type_id]: [] });
              }}
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
      {measured.length > 0 && <Facts facts={measured} />}
      {suggested.length > 0 && (
        <div className="mb-3">
          <p className="m-0 mb-1 font-data text-[9.5px] tracking-[.15em] uppercase text-ink-3">
            Suggested — keep what you asked for
          </p>
          <ul aria-label="suggested constraints" className="m-0 p-0 flex flex-wrap gap-[6px]">
            {suggested.map((r) => {
              const key = keyOf(r);
              const on = chosenSuggestions.includes(key);
              return (
                <li key={key} className="list-none">
                  <button type="button" aria-pressed={on}
                          aria-label={`${on ? "drop" : "keep"} ${key}`}
                          onClick={() => setChosenSuggestions(on
                            ? chosenSuggestions.filter((k) => k !== key)
                            : [...chosenSuggestions, key])}
                          className={`font-data text-[11px] px-2 py-[3px] border cursor-pointer
                                      focus-visible:shadow-[var(--ring)] ${on
                                        ? "text-link border-[var(--link)]"
                                        : "text-ink-3 border-dashed border-[var(--line-2)]"}`}>
                    {key}
                  </button>
                </li>
              );
            })}
          </ul>
        </div>
      )}
      {block.readback ? (
        <p className="m-0 mt-1 text-[12px] leading-[1.6] text-ink-2">
          {block.readback}{" "}
          <span className="font-data text-[9.5px] text-ink-4">in the AI's words</span>
        </p>
      ) : (
        <p className="m-0 mt-1 text-[12px] leading-[1.6] text-ink-3">
          {[block.have, block.do, block.get].map(sentence).join(" — ")}.
        </p>
      )}
      {edited && (
        // The sentence is the model's and the chips are now the person's. Rewriting the prose
        // would be a second author putting words in the model's mouth, so it stays and says
        // which of the two runs (issue 116).
        <p className="m-0 mt-1 font-data text-[10px] text-ink-4">
          that sentence was the model's reading, before your edit — the types above are what will be built
        </p>
      )}
    </BlockFrame>
  );
}

/** Each gathered fact with its source, and what was deliberately left open.
 *
 * **Open is said out loud**, because it is a decision deferred rather than a gap forgotten: every
 * step that reads an open measurement comes back as a tier-4 choice during the build. */
function Facts({ facts }: { facts: Fact[] }) {
  const known = facts.filter((f) => f.source !== "open");
  const open = facts.filter((f) => f.source === "open");
  const said = (f: Fact) =>
    f.value === null || f.value === undefined ? f.subject
      : `${f.subject}: ${f.value === true ? "yes" : f.value === false ? "no" : String(f.value)}`;
  return (
    <div className="mb-3">
      <ul aria-label="what the engine knows" className="m-0 p-0">
        {known.map((f) => (
          <li key={`${f.kind}-${f.subject}`} className="list-none font-data text-[11px] text-ink">
            {said(f)}{" "}
            <span className={f.source === "measured" ? "text-[var(--measured)]" : "text-ink-3"}>
              · {sourceLabel(f)}
            </span>
          </li>
        ))}
      </ul>
      {open.length > 0 && (
        <>
          <p className="m-0 mt-2 font-data text-[9.5px] tracking-[.15em] uppercase text-ink-3">
            Left open, you'll choose during the build
          </p>
          <ul aria-label="Left open, you'll choose during the build" className="m-0 p-0">
            {open.map((f) => (
              <li key={`${f.kind}-${f.subject}`} className="list-none font-data text-[11px] text-ink-2">
                {f.subject}
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}

/** `fastq.reads[paired]`, as `LivingGoal` draws it. **States are what a person is confirming**:
 * a model that writes a state nobody stated tells the engine to skip the step that makes it
 * true, and a chip showing only the type hides exactly that. */
function spelled(type_id: string, states: string[] | undefined): string {
  return states && states.length > 0 ? `${type_id}[${states.join(", ")}]` : type_id;
}

/** A model's sentence usually ends in a full stop already; the card adds its own once. */
function sentence(text: string): string {
  return text.trim().replace(/\.+$/, "");
}

function statesOf(goal: unknown): Record<keyof Chosen, Map<string, string[]>> {
  const g = goal as {
    have?: { type_id: string; states?: string[] }[];
    constraints?: { required_states?: { type_id: string; states?: string[] }[] };
  };
  return {
    have: new Map((g.have ?? []).map((e) => [e.type_id, e.states ?? []])),
    want: new Map((g.constraints?.required_states ?? []).map((e) => [e.type_id, e.states ?? []])),
  };
}

function goalOf(goal: unknown): Chosen {
  const g = goal as { have?: { type_id: string }[]; want?: string[] };
  return { have: (g.have ?? []).map((entry) => entry.type_id), want: [...(g.want ?? [])] };
}
