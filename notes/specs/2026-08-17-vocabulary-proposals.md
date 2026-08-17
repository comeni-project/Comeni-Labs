# When nothing in the vocabulary fits

**Status:** design spec, written 2026-08-17 with the operator, from measurements rather than
prediction. Follows [`2026-08-17-forge-phase-2.md`](2026-08-17-forge-phase-2.md).

**Precedence:** where this spec and the code disagree, the code is right and this file has
drifted.

---

## 1. The measurement that forced it

Forge Phase 2 was measured by re-deriving every shipped nf-core contract with a local model and
diffing against what a human approved. Two of the surviving failures turned out to have the same
cause, and it was not the model:

- **`star/align` emits nineteen channels.** The shipped contract declares one — a BAM — because
  the other eighteen carry things the vocabulary has no type for. There is no `star.log`. The
  forge asked the model to type all nineteen from twenty-two declared types, so eighteen
  questions had **no correct answer available**. Asked to type a STAR run log, the model answered
  `qc.report`: the closest of twenty-two wrong options.
- **`consumes[0].name` missed on three tools** — `multiqc_files` where the contract says
  `reports`, `bams` where it says `bam`, `input` where it says `bam`. The candidates offered are
  the module's channel names, and the answer usually is not one: **twenty-four of thirty shipped
  ports are named after a segment of their own `type_id`.** For `multiqc` exactly one candidate
  was offered and it was wrong.

**Both are the same defect in two places: a closed choice whose correct answer is not among the
candidates.** The model cannot decline, so it must produce a wrong value — and a wrong `type_id`
routes.

**The measurement is structurally blind to how common this will be.** Every shipped contract has
valid types *by construction*, so "nothing fits" can never appear in that test set. For a tool
nobody has written a contract for — the case the forge exists to serve — it will be ordinary.

## 2. What the invariants already promise

> **Invariant 7.** Vocabularies are closed. A contract using an undeclared state fails to load.
> New states arrive **through the forge's approval queue** as reviewed data changes, never code
> changes.

That queue does not exist. Until it does, "the vocabulary cannot express this" has nowhere to go,
and the forge converts it into a plausible wrong value — the worst available outcome, because a
blank is visible to a reviewer and a wrong type is not.

> **Invariant 2.** AI authors artifacts offline; humans approve.

A proposal is exactly that shape: the model drafts, a person approves, and nothing reaches
`vocabularies/` automatically.

## 3. The decisions

Taken 2026-08-17, after the measurement above.

### 3.1 A no-fit answer produces a **drafted proposal**, not merely a blank

The alternative — flag the hole and stop — was considered and rejected. It is smaller and it
keeps every model output a closed choice, but it means a human hand-writes every new vocabulary
entry, and the registry then grows at human speed. That is the constraint the forge exists to
remove.

**The cost, stated plainly:** a proposal carries free prose (an id and a description) into
declared data, which is what issue #70 gates for `priority_because`. What bounds it is that a
proposal lands in a **queue**, never in the registry — invariant 2's approval step is the whole
guard, and it must stay a real one.

### 3.2 Ask every candidate-bearing hole, and let the answer be "none"

Rather than predicting which ports are untypable and skipping them. **A decline is information**:
it distinguishes *no declared type fits* from *nobody has looked yet*, and those need different
work. Skipping would need a rule for "obviously untypable" that quietly drops ports somebody
wanted.

### 3.3 A port's name candidates come from its type, not only from its channel

Measured: twenty-four of thirty. The candidate set becomes `{module channel names} ∪ {segments of
the chosen type_id}`, which requires the **type to be chosen first** — so `.name` is asked after
`.type_id` for the same port, and its candidates are recomputed when the type lands.

**This makes holes dependent on each other for the first time**, and that is the honest shape:
they always were, and independence is what produced `gtf` for `consumes[1].name` followed by
`genome.index.hisat2` for `consumes[1].type_id` on the same port.

## 4. The surface

### 4.1 `mendel-ai` — a choice may decline with a reason

`choose_one` gains a sibling rather than changing shape, because the ambiguity resolver (Plan 3)
wants the strict form and must not inherit a proposal path it has no use for:

```python
def choose_or_propose(client, question, options, evidence, *, proposing: str) -> Chosen | Proposed | None
```

`Chosen` carries a value from the options. `Proposed` carries an `id`, a `description` and a
`why`. **Exactly one is returned**, enforced by the shape rather than by a convention: a model
that returns both, or neither, fails validation and the hole stays open.

`proposing` names what a proposal would be *for* — "a declared type", "a role" — because a model
asked to invent something needs to know what kind of thing it is inventing.

The rationale cap (`WHY_LIMIT`) applies to `description` too. It is the same argument: this is
the free-text field, and a cap makes it the wrong shape for smuggling something larger.

### 4.2 `mendel-forge` — a hole may be answered by a proposal

`Scaffold` gains `proposed: dict[str, Proposal]` beside `filled` and `holes`. A hole with a
proposal is **not filled** — `is_complete()` stays false, `contract_from` still refuses, and the
draft cannot land. That is deliberate: a contract whose port depends on an unapproved type would
be a contract citing a vocabulary entry that does not exist, which is the load-time refusal
invariant 7 already makes.

`land` refuses a draft carrying proposals, naming them and pointing at the queue. **One review,
not two**: the proposal and the contract that motivated it are reviewed together, because a type
proposed with no consumer is a type nobody can judge.

### 4.3 What a proposal is not

- **Not a vocabulary file.** It is a draft in the workspace. Nothing writes `vocabularies/`.
- **Not a fill.** `Filler.MODEL` marks a value a model chose from a closed set; a proposal is a
  different act and is recorded as one.
- **Not automatic.** No verb promotes a proposal without a person.

## 5. How this gets measured, and why the current test set cannot

**Every shipped contract has valid types by construction**, so the ten-contract accuracy harness
can never exercise §3.1. Measuring it needs tools with **no contract at all**: vendor fresh
nf-core modules, draft them cold, and read what the forge proposes.

That is the same held-out test the overfitting question already wanted, and the two converge —
which is worth noticing rather than treating as a coincidence. A measurement that only covers
tools somebody already solved is a measurement of the wrong thing.

**The judgement is not mechanical there.** With no shipped contract there is no ground truth, so
the report is "did it propose something a reviewer would accept", assessed by a person. That is
weaker evidence than the registry diff and must be labelled as such wherever the number appears.

## 6. What this does not settle

**Which ports a contract should declare.** `star/align` emits nineteen and declares one; nothing
records that the other eighteen were *considered and omitted* rather than missed, so `forge check`
cannot tell the two apart. A proposal path makes this visible — eighteen proposals is a loud
signal — but it does not answer it. Left open deliberately.
