# When nothing fits: ask, never force — design

**Issue:** #202 (under #180, step 14.7.4). **Decided** by the operator on 2026-09-30: *verdict
first* and *dead end asks*, and it must be shown to work.

## 1. What goes wrong today

A request no family fits (*"variant calls from my exomes"*; the registry holds no variant types)
fails twice in a row:

1. **The family call picks the nearest family anyway.** `builder.family.v1` allows an empty
   `families` with a question in `unclear`, and says in bold never to pick the nearest. gemma3:12b,
   under an enforced reply format, answered `{"families": ["annotation"]}`. An empty list is a way
   out the model has to *skip* to, and the grammar lets it write an item first.
2. **The engine then fails the session.** `goal.v7` chose `annotation.gtf` from that family,
   `gaps.gaps()` returned `Unreachable`, and `offer_next_gap` moved the session to `failed` with
   `MI0209`. The person asked for something reasonable and got a dead end, not a question.

## 2. What the person gets instead

- A request nothing here can produce ends in **a question**: the model's own, or the engine's
  (*"I can't produce that with the tools here. What result do you want?"*). The session stays in
  *understanding*, and the reply is read from the top.
- A request that fits behaves exactly as it does today: same calls, same card.

## 3. Verdict first (`builder.family.v2`)

`FamilyChoice` gains a required **`fits`**, declared **first**:

```python
class FamilyChoice(_Shape):
    fits: Literal["yes", "no", "unsure"]   # first: judged before anything is listed
    families: list[str] = []
    ack: Prose
    unclear: Prose | None = None
```

- **Order matters.** The reply is written left to right, so the model commits to whether anything
  fits before it can start a list. The field comes first in the schema, and the enforced format
  keeps that order (a test asserts `fits` is the schema's first property).
- **The engine reads the verdict, not the list:**
  - `fits == "yes"` with at least one family: the goal call follows, as today.
  - otherwise (`no`, `unsure`, or `yes` with nothing listed): the engine asks and makes no goal
    call. It asks with `unclear` if the model wrote one, or else with `NO_FAMILY_FITS`. Any
    families listed beside a `no` are ignored, never half-trusted.
- **The prompt** (`builder.family.v2.md`) explains the three values in the words of the person's
  request: *yes*, one of these families holds what they want to end up with; *no*, none does;
  *unsure*, you cannot tell which.
- `family.v1` stays on disk; `FAMILY` points at v2. Recorded fixtures for the family call are
  re-recorded.

## 4. Dead end asks

When `offer_next_gap` finds the want **unreachable**, the session goes back to *understanding*
with a question, instead of to `failed`:

- **Only model-chosen wants reach this path.** `gaps.gaps()` returns `Unreachable` only for a want
  type, and `offer_next_gap` runs only after `WANT_RETURNED` (a model's want) or after a gap is
  answered (the want is unchanged). A goal edited on the card is admitted and goes straight to
  resolving. So this changes no path a person's own choice takes; `resolve → failed` (*can't build
  it*) is untouched.
- **What is said:** the engine's own sentence, which **names no type**: *"Nothing here can
  produce what you asked for. What result do you want?"* Types declare no description, and the
  type was the model's guess, not the person's word, so naming it (the #195 lesson) would show
  them an id they never chose. The `MI0209` diagnostic is still recorded as a notice on the turn,
  so the log says which type and why.
- **The want is cleared**, so the next reply chooses again from the top (family, then goal) with
  the engine's question in the conversation it reads.
- **Protocol:** a new event `WANT_UNREACHABLE`, *gathering → understanding*. The edge
  `list_needs → failed` (*nothing can make it*) becomes `list_needs → say` (*nothing makes it: it
  asks you*). `TRANSITIONS` and the Mermaid diagram are derived from `protocol.py` and
  regenerated. `authoring-protocol.md` gets a loosening entry and a changelog row.

## 5. Shown to work

- **Unit and route tests** (recorded or fake transports only, never a live model):
  - `fits` is the family schema's first property;
  - `fits: no` with a family listed: one call, a question block, still *understanding*, no goal
    call;
  - `fits: unsure` without `unclear`: the engine's question;
  - `fits: yes` with families: the goal call follows (today's path);
  - a model-chosen unreachable want: the engine's question (no type id in it), phase *understanding*,
    want cleared, `MI0209` recorded, never `failed`;
  - a goal edited on the card is unaffected;
  - protocol: the new edge, and no edge from `list_needs` to `failed`.
- **The walk** (gemma3:12b, reply format enforced, family step on, the real stack):
  - three no-fit sentences: *variant calls from my exomes*, *a phylogenetic tree from my 16S
    amplicons*, *peaks from my ChIP-seq*. Each must end in a question, **never `failed`**. The walk
    records which layer caught it: the verdict, or the dead-end net;
  - the three sentences that fit, from earlier walks. Same card and the same number of calls as
    the 2026-09-29 walk.
  - The results go on #202 and in the plan's execution record.

## 6. Out of scope

- Telling `goal.v7` to refuse a family (not chosen), and a `none` value in the family list (not
  chosen).
- The narrowed benchmark (#198) runs after this, on the behaviour kept here.
- Suggesting a nearby result that *can* be made (*"did you mean …?"*): the question stays open.
