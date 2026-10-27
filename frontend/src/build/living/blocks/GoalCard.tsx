import { useEffect, useId, useRef, useState } from "react";

import type { AuthoringProposal, AuthoringSession, AuthoringVocabulary, GoalIn } from "../../../api/types";
import type { CorrectFact } from "../CurrentFacts";
import { FactEditor } from "../FactEditor";
import { NotOffered } from "../NotOffered";
import { factWords } from "../FactHistory";
import { Primary, Secondary } from "./parts";
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
 *  a constant on purpose: one sample is all the conversation accepts (issue 218 changes that).
 *  An open fact *needs you*: it comes back as a question during the build. */
const sourceLabel = (f: Pick<Fact, "source" | "pieces">) =>
  f.source === "measured" && f.pieces?.length
    ? `measured · ${piece(f.pieces[0])} · from 1 sample`
    : f.source === "open" ? "needs you" : SOURCE[f.source];

/** The goal read back as **What was understood** (the *Describe* board) — one line per input, per
 * output and per fact, each with where it came from and the words it was heard in, corrected by
 * clicking the line.
 *
 * **The words it was heard in** (Part I.0) are on every line that has them: a model's reading of
 * *"not paired-end"* holds *"paired-end"*, and the quote is how the person sees what it was taken
 * from. The board's *convention* and *will be measured* chips have no source in a fact, so the
 * chips are the fact's own: *you said*, *measured*, *read by AI*, *needs you*.
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
  subjects = [],
  onCorrectFact,
  declarations,
  factsDisabled = false,
  pace,
  confirmRequest = 0,
  startInHeader = false,
  notOffered = [],
}: {
  proposal: AuthoringProposal;
  /** Declared type ids and their states. `null` while it loads — the card is still answerable. */
  vocabulary: Record<string, string[]> | null;
  busy: boolean;
  onConfirm: (edited?: GoalIn) => void;
  onReject: () => void;
  /** What gathering learned, each with its source (14.7.3). Empty for a goal nobody gathered. */
  facts?: Fact[];
  /** Facts the engine reads that nobody has given — drawn as open lines. */
  subjects?: string[];
  /** Correct a fact from its line; absent, fact lines are read-only. */
  onCorrectFact?: CorrectFact;
  declarations?: AuthoringVocabulary["measurements"];
  factsDisabled?: boolean;
  /** Drawn between the table and *Start building* — how the build will go. */
  pace?: React.ReactNode;
  /** *Start building* pressed elsewhere (the describe header, one builder plan 3): confirm as
   *  this card's own button does, with the person's edits. */
  confirmRequest?: number;
  /** The header holds *Start building*, so this card does not draw it. */
  startInHeader?: boolean;
  /** What was asked for and is not offered here (Part I.2). */
  notOffered?: string[];
}) {
  const block = proposal.block;
  const seen = useRef<number | null>(null);
  // **Start building from the header** confirms once per press, with the edits held here; the
  // effect is above any early return, and calls the newest `confirm`.
  const latest = useRef<() => void>(() => undefined);
  useEffect(() => {
    if (confirmRequest > 0 && confirmRequest !== seen.current) {
      seen.current = confirmRequest;
      latest.current();
    }
  }, [confirmRequest]);
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
  const [editing, setEditing] = useState<string | null>(null);
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
  // **Each input once, its source on its chip** (issue 172); the fact lines are for measurements.
  const inputOf = new Map(facts.filter((f) => f.kind === "input").map((f) => [f.subject, f] as const));
  const measured = [
    ...facts.filter((f) => f.kind === "measurement"),
    ...subjects.filter((subject) => !facts.some((f) => f.kind === "measurement" && f.subject === subject))
      .map((subject) => ({ kind: "measurement", subject, source: "open", states: [], pieces: [] }) as Fact),
  ];

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
  latest.current = confirm;

  const group = (side: keyof Chosen, labelId: string, label: string) => {
    const open = editing === side;
    const word = side === "have" ? "You have" : "You want";
    return (
      <ul aria-label={label} className="m-0 p-0">
        {chosen[side].map((type_id, i) => {
          const fact = side === "have" ? inputOf.get(type_id) : undefined;
          const value = side === "want" ? spelled(type_id, states.want.get(type_id)) : (
            <span>
              {type_id}
              {(held[type_id] ?? []).length > 0 && (
                <>
                  [
                  {(held[type_id] ?? []).map((state, j) => (
                    <span key={state}>
                      {j > 0 && ", "}
                      {open ? (
                        <button type="button" title="not true of this input — take it off"
                                aria-label={`remove state ${state} from ${type_id}`}
                                onClick={() => setHeld({ ...held, [type_id]: held[type_id].filter((x) => x !== state) })}
                                className="bg-transparent border-0 p-0 font-data text-[inherit] text-ink cursor-pointer
                                           underline decoration-dotted hover:line-through focus-visible:shadow-[var(--ring)]">
                          {state}
                        </button>
                      ) : state}
                    </span>
                  ))}
                  ]
                </>
              )}
            </span>
          );
          return (
            <Line key={type_id} label={i === 0 ? word : ""} heard={fact?.heard}
                  chip={fact ? { words: sourceLabel(fact), source: fact.source } : undefined}
                  correct={open ? undefined : { name: `correct ${type_id}`, onClick: () => setEditing(side) }}>
              <span className="font-data text-[14px] text-ink">{value}</span>
              {open && (
                <button type="button" aria-label={`remove ${type_id} from ${label}`}
                        onClick={() => {
                          setChosen({ ...chosen, [side]: chosen[side].filter((t) => t !== type_id) });
                          if (side === "have") setHeld({ ...held, [type_id]: [] });
                        }}
                        className="ml-2 bg-transparent border-0 p-0 text-ink-3 hover:text-ink cursor-pointer
                                   focus-visible:shadow-[var(--ring)]">
                  ×
                </button>
              )}
            </Line>
          );
        })}
        {(open || chosen[side].length === 0) && (
          <Line label={chosen[side].length === 0 ? word : ""}>
            {types.length > 0 && (
              <select id={labelId} aria-label={`add to ${label}`} value=""
                      onChange={(e) => {
                        const type_id = e.target.value;
                        if (type_id && !chosen[side].includes(type_id)) {
                          setChosen({ ...chosen, [side]: [...chosen[side], type_id] });
                        }
                      }}
                      className="font-data text-[12px] bg-[var(--surface)] text-ink-2 border rounded-control px-2 py-[4px]"
                      style={{ borderColor: "var(--line-2)" }}>
                <option value="">+ add a type</option>
                {types.filter((t) => !chosen[side].includes(t)).map((t) => (
                  <option key={t} value={t}>{t}</option>
                ))}
              </select>
            )}
            {open && (
              <button type="button" onClick={() => setEditing(null)}
                      className="ml-3 bg-transparent border-0 p-0 text-[12.5px] text-now-ink underline cursor-pointer
                                 rounded-control focus-visible:shadow-[var(--ring)]">
                Done
              </button>
            )}
          </Line>
        )}
      </ul>
    );
  };

  return (
    <>
      <section aria-label="the goal as understood" className="rounded-panel border px-[20px] pt-[16px] pb-[6px]"
               style={{ borderColor: "var(--line)", background: "var(--surface)" }}>
        <header className="flex flex-wrap items-baseline gap-x-3 gap-y-1 pb-[10px]">
          <h2 className="m-0 text-[17px] font-semibold text-ink">What was understood</h2>
          {edited && <span className="text-[12px] font-semibold text-now-ink">edited</span>}
          <span className="ml-auto text-[12.5px] text-ink-3">Wrong? Click a line to correct it</span>
        </header>
        {/* **The typed goal first** — it is what the pipeline is built from and what the person is
            checking. The sentence beneath says the same thing in words, quieter, for reading. */}
        {group("have", addHave, "what you have")}
        {group("want", addWant, "what you want")}
        <NotOffered phrases={notOffered} />
        {measured.length > 0 && (
          <ul aria-label="what the engine knows" className="m-0 p-0">
            {measured.map((f) => (
              <Line key={`${f.kind}-${f.subject}`} label={labelOf(f.subject)} heard={f.heard}
                    note={f.source === "open" ? "Left open — you'll choose during the build." : undefined}
                    chip={{ words: sourceLabel(f), source: f.source }}
                    correct={onCorrectFact && editing !== f.subject
                      ? { name: `correct ${f.subject}`, onClick: () => setEditing(f.subject) } : undefined}
                    editor={onCorrectFact && editing === f.subject ? (
                      <FactEditor subject={f.subject} value={(f.value ?? null) as never} kind="measurement"
                                  declaration={declarations?.[f.subject]} disabled={factsDisabled}
                                  onSave={(value) => onCorrectFact(f.subject, value, "measurement")
                                    .then((done) => { setEditing(null); return done; })} />
                    ) : undefined}>
                <span className="text-[14px] text-ink">
                  {f.source === "open" || f.value === null || f.value === undefined ? "Not known yet" : factWords(f.value)}
                </span>
              </Line>
            ))}
          </ul>
        )}
        {suggested.length > 0 && (
          <Line label="Suggested">
            <ul aria-label="suggested constraints" className="m-0 p-0 flex flex-wrap gap-[6px]">
              {suggested.map((r) => {
                const key = keyOf(r);
                const on = chosenSuggestions.includes(key);
                return (
                  <li key={key} className="list-none">
                    <button type="button" aria-pressed={on} aria-label={`${on ? "drop" : "keep"} ${key}`}
                            onClick={() => setChosenSuggestions(on
                              ? chosenSuggestions.filter((k) => k !== key)
                              : [...chosenSuggestions, key])}
                            className={`font-data text-[12px] px-[9px] py-[3px] border rounded-full cursor-pointer
                                        focus-visible:shadow-[var(--ring)] ${on
                                          ? "text-now-ink border-[var(--now)] bg-[var(--now-soft)]"
                                          : "text-ink-3 border-dashed border-[var(--line-2)] bg-transparent"}`}>
                      {key}
                    </button>
                  </li>
                );
              })}
            </ul>
            <span className="block mt-[4px] text-[12.5px] text-ink-3">Kept only if you keep them.</span>
          </Line>
        )}
        <div className="py-[12px] border-t" style={{ borderColor: "var(--line-soft)" }}>
          {block.readback ? (
            <p className="m-0 text-[13px] leading-[1.6] text-ink-2">
              {block.readback}{" "}
              <span className="text-[12px] text-ink-3">in the AI's words</span>
            </p>
          ) : (
            <p className="m-0 text-[13px] leading-[1.6] text-ink-3">
              {[block.have, block.do, block.get].map(sentence).join(" — ")}.
            </p>
          )}
          {edited && (
            // The sentence is the model's and the lines are now the person's. Rewriting the prose
            // would be a second author putting words in the model's mouth, so it stays and says
            // which of the two runs (issue 116).
            <p className="m-0 mt-1 text-[12px] text-ink-3">
              That sentence was the model's reading, before your edit — the lines above are what will be built.
            </p>
          )}
        </div>
      </section>
      {pace}
      <div className="flex flex-wrap items-center gap-3">
        <p className="m-0 text-[13px] text-ink-3">The same goal and answers always give the same pipeline.</p>
        <span className="ml-auto flex gap-2">
          <Secondary data-testid="reject-goal" disabled={busy} onClick={onReject}>
            Not quite
          </Secondary>
          {!startInHeader && (
            <Primary data-testid="accept-goal" disabled={busy} onClick={confirm}>
              {busy ? "Starting…" : "→ Start building"}
            </Primary>
          )}
        </span>
      </div>
    </>
  );
}

const CHIP: Record<Fact["source"], React.CSSProperties> = {
  person_said: { borderColor: "var(--line-2)", color: "var(--ink-2)", background: "var(--surface)" },
  model_read: { borderColor: "var(--line-2)", color: "var(--ink-2)", background: "var(--surface)" },
  measured: { borderColor: "transparent", color: "var(--measured-ink)", background: "var(--measured-soft)" },
  open: { borderColor: "transparent", color: "var(--needs-you-ink)", background: "var(--needs-you-soft)" },
};

/** One line of the table: what it is, its value, the words it was heard in, where it came from.
 *  Clicking the value opens its editor when the line can be corrected. */
function Line({ label, children, heard, note, chip, correct, editor }: {
  label: string; children: React.ReactNode; heard?: string | null; note?: string;
  chip?: { words: string; source: Fact["source"] };
  correct?: { name: string; onClick: () => void }; editor?: React.ReactNode;
}) {
  const value = (
    <>
      <span className="flex flex-wrap items-baseline">{children}</span>
      {(heard || note) && (
        <span className="block mt-[3px] text-[13px] leading-[1.5] text-ink-2">
          {heard && <>From "{heard}".</>}{heard && note ? " " : ""}{note}
        </span>
      )}
    </>
  );
  return (
    <li className="list-none grid grid-cols-[minmax(0,110px)_minmax(0,1fr)_auto] gap-x-4 py-[12px] border-t"
        style={{ borderColor: "var(--line-soft)" }}>
      <span className="text-[13px] text-ink-2 pt-[1px]">{label}</span>
      <span className="min-w-0">
        {correct ? (
          <button type="button" aria-label={correct.name} onClick={correct.onClick}
                  className="block w-full text-left bg-transparent border-0 p-0 cursor-pointer rounded-control
                             hover:[&_*]:decoration-[var(--line-2)] focus-visible:shadow-[var(--ring)]">
            {value}
          </button>
        ) : <span className="block">{value}</span>}
        {editor}
      </span>
      {chip ? (
        <span data-testid="source" className="self-start shrink-0 rounded-full border px-[9px] py-[1px] text-[11.5px] font-semibold"
              style={CHIP[chip.source]}>
          {chip.words}
        </span>
      ) : <span />}
    </li>
  );
}

/** `read_length` as a line's label: *Read length*. */
function labelOf(subject: string): string {
  const words = subject.replaceAll("_", " ");
  return words.charAt(0).toUpperCase() + words.slice(1);
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
