# The forge interface — visual and interaction design

**Date:** 2026-08-18. **Status:** designed against the code that exists, drawn, reviewed.
**Screens:** ten artboards, published as a design canvas rather than committed HTML — the
mockups for this one are a pan/zoom canvas, not a single page.

**This replaces the 2026-08-02 design of the same name**, which is preserved in git history. The
old one is not superseded because it was ugly. It was designed for **a job the forge no longer
does**, and §1 is the argument.

Shares the token, type and spacing system in [`dashboard.md`](dashboard.md) §2 — that system
governs **both halves** and there is one copy of it, which happens to live in the other file
because that is where it was first written. Only what differs is recorded here.

---

## 1. Why the previous design was replaced

It assumed a model drafts a **whole contract** and a curator reads it and approves. Eight
numbered stages, four of which cleared themselves automatically.

What the forge actually produces, run today against `nf-core:fastqc`, is **ten derived facts and
six questions**:

```
open (6):
  consumes[0].name
      what: what this contract calls the thing arriving on channel 0
      why open: a port name says what the channel carries; the module's says
                what the process calls it, and the two are not the same choice
      one of: reads
```

That is not a document to review. It is six specific questions, each carrying candidates,
evidence, and a reason it is open. The old design's own header half-admits this — it notes the
typed holes are *"more than these mockups assume, not less"*.

**Two of its three blocking gaps have also closed.** It recorded that `Provenance` was
per-contract, so the per-field origin stripe it specified **could not be built**; `FilledValue`
carries `how` and `by` per field now. It recorded that `copied` was an assertion rather than a
verification; conformance checking exists (Plan 1.6).

**And the eight-stage wizard was the wrong shape twice over.** It imposed a *procedure* where the
dashboard offers a *representation* — you read a picture at a glance, you march through steps —
and it made the **module** the unit of work when the actual unit is a **question**.

---

## 2. The governing idea

The dashboard's is *certainty is a property of how a thing is drawn*. The forge's is:

> **A question is the unit of work — not a document, and not a module.**

The ten derived facts are not review material; they are *evidence*. So the interface shows
questions, and offers evidence on demand.

That single line deletes the wizard, and it is what makes the throughput move in §4 possible.

---

## 3. Three destinations, and the rule that decides

| | |
|---|---|
| **Queue** | work that needs deciding |
| **Contracts** | what exists — inspect, browse, resolve drift |
| **Sources** | what could exist — ingest |

> **A page earns its place by being a different *kind of work*, not a different *subject*.**

Everything else is a **view** or a **state** of one of those three. A question is an item in the
queue. A proposal is an item in the queue. Drift is a state of a contract. *By module* is a
grouping of the queue; *Confirmable* is a filter of it.

**The registry is a lookup, not a destination.** Types, states and roles open in a panel
*beside* the current decision — the question narrows, the panel opens, nothing dims and nothing
navigates away. You consult it mid-decision, and losing your place is exactly the friction being
removed.

Applied backwards the rule already deleted things: an **Overview** page was designed and then
cut, because it answered the same question as the Queue.

> **This constraint was lifted on 2026-08-30**, by the operator, in Plan 4 phase 2. `/` is now
> the lab's work — it renders **pipelines and runs**, as items, with a NOW band and a Work
> table. It is recorded here rather than left for a reader to trip over, because the argument
> above is a good one and the next person to find it would reasonably re-apply it.
>
> **What survives is the narrower rule**, and it is still enforced: the front door may never
> render a *registry* subject — a contract id, a question subject, a drift row. Those are the
> Queue's, and the moment one appears on `/` it has become the page that was cut.
> `test_it_points_at_a_screen_and_never_at_a_registry_subject` holds it.
>
> **What did not survive**: the `standing` block, which reported what the registry *holds* — 12
> contracts, 22 types, 3 rules. That is the product's state rather than the reader's, and it is
> most of why the old page read as generated.

---

## 4. The Queue — the only home

**Default grouping is by question, not by module.** All the *"what type arrives on this BAM
input?"* questions across `samtools/index`, `samtools/sort` and `picard/markduplicates` appear
together and are answered once. The old design asked that question three times, in three separate
reviews, with three context switches.

**Default sort is consequence, not recency**, in this order:

1. **Drift** — a contract that *was* true and now is not. It breaks pipelines that already run.
2. **Blocked** — a proposal the vocabulary needs before a module can land.
3. **Ask** — a question a model would not answer.
4. **Confirm** — a model answered; you are checking.
5. **Label / Draft** — cosmetic, or not started.

Three bands, taken from the forge's **own measurement** (`notes/journal/2026-08-17-prompt-search.md`):

| Band | What it is | Interaction |
|---|---|---|
| **Confirmable** | model answered, candidates bind — **97%** accurate on the fields that change the pipeline | one keystroke; batch-acceptable |
| **Needs you** | model declined, proposed a new type, or candidates do not bind | full evidence, one at a time |
| **Cosmetic** | port *labels* — **~60%** accurate, and a rename takes seconds | deprioritised, batch by default |

Grading by consequence rather than by hit rate was the operator's call on 2026-08-17, and the
bands are that call made structural.

### What keeps it bounded as the registry grows

The Queue is the monitoring surface, because **the forge maintains as well as creates** — sources
drift, and `forge check` is what notices. So it must survive 58 contracts and 5,800. Three things
do that, and each is a deliberate constraint rather than a happy accident:

- **The facet rail never grows.** Six kinds of work, fixed, whatever the registry size.
- **The health strip is O(1)** — *58 contracts · 54 match their source · 22 declared types ·
  checked 4 min ago*. It is genuinely summary data, so it can sit above everything.
- **Identical work collapses into one row.** 86 confirmable answers are not 86 rows; they are
  `consumes[0].type_id → alignment.bam ×11`. 104 labels are one row.

Two controls make one page enough: **sort** (consequence by default) and **changed since my last
visit** — which is the maintenance case, because at 232 open items you do not want everything,
you want what moved.

---

## 5. Answering one

One question at a time, in a reading column, with context as **prose rather than cards**:

> Asked by `samtools/index`, `samtools/sort` and `picard/markduplicates` — answering once settles
> all three.

**Evidence is collapsed to one line** — *"Evidence — 3 lines from the module"*, `E` to open. This
is the change that removes the overwhelm: on the confirmable questions you never open it, and the
screen is a question, three options and a button.

**The suggestion is marked `MODEL`, explicitly.** Who answered is what a reviewer needs, and a
model suggestion and a human answer oblige different amounts of trust.

**"Nothing here fits" is always visible** as an option, never buried. It is invariant 7's escape
hatch, and a closed choice with no way to decline forces a wrong answer — which is exactly the
defect `notes/specs/2026-08-17-vocabulary-proposals.md` was written about.

**Emptying a band reports what it *unblocked*** — *"Two modules can land now"* — then offers the
next work in consequence order. Questions are not the point; contracts are.

---

## 6. Confirming many

The confirmable band is **a list you scan, not a wizard you march through**. Seventeen questions
at 97% accuracy do not each deserve a full screen.

**Answers are grouped so identical ones stack.** Four rows reading `alignment.bam` and then
`samtools/faidx` also reading `alignment.bam` makes the wrong one visible without reading a word —
flagged amber with *"the only faidx input is a FASTA — check this one"*. One button accepts the
ticked remainder.

This is [OpenRefine's reconciliation pattern](https://openrefine.org/docs/manual/reconciling):
auto-match high confidence, surface only the ambiguous, and offer *"apply to every cell with this
value"* alongside *"apply here only"*.

---

## 7. Contracts, browsing, and drift

**Contracts** lists what has landed, sorted drifted-first, with facets for *against source*
(drifted / matching / **unverifiable**), source, and role. `unverifiable` is present because a
contract whose module source is absent is marked rather than trusted — never assert a conformance
property over modules that were not readable.

**The module page is a dense read-only reference**, and dense is correct there: it is browsed, not
burned through, so it has different rules from the queue. Left column is the contract and its
source; right column is **everything that points at this module** — the tier-3 rules aiming at its
roles, what its inputs come from and its output feeds, what it competes with, how many published
pipelines pin it. Per-field origin renders as a stripe in a left gutter, which forms a continuous
band you read as a column.

It states two things nothing else surfaces: **"1 of 19 emit channels is declared"** with the
reason a contract may legitimately model a subset, and which **source line** the contract drifted
at, so browsing and the diff point at the same place.

**Read-only stays read-only.** Contracts change through the queue (a question) or through drift
resolution (a diff you accept), both of which record *why*. A free-text edit surface has nowhere
to put the reason, and every value carrying a reason is the product claim.

**Drift** shows **every field checked, not only the one that differs** — four matching rows, then
*"11 further fields checked, all matching"*. "One field drifted" is otherwise an unfalsifiable
claim.

Its verdict block answers the only question a maintainer really has:

> **Nothing routes differently.** `container` is not read by the router — no type, state or role
> changed, so every pipeline that resolved to this contract still resolves to it.

That is the old design's stage-5 routing check, moved to where it belongs and made specific to the
change in front of you. A container bump and a `type_id` change are wildly different events.

---

## 8. What is firm and what is provisional

**Firm** — these are the structural claims, and changing one is a redesign:

- three destinations, subpages beneath, and the rule in §3 that decides
- one queue as the home, sorted by consequence
- one row shape for every kind of work
- a question, not a module, as the unit
- read-only browse

**Provisional** — expected to move once somebody uses it:

- densities and exact spacing within the scale
- the facet set, and whether *Labels* deserves its own band
- keyboard map beyond `J` / `A` / `E`
- whether *changed since my last visit* is the right default filter

---

## 9. Not designed

Stated plainly rather than implied by omission:

- **Sources** is in the navigation and undrawn. It is where drafting starts and where a second
  source ([#65](https://github.com/comeni-project/Comeni-Labs/issues/65), pegi3s) would appear.
- **Pipeline review** is a separate screen set. The [federation spec](federation.md) adds
  `kind: pipeline` to the queue, but it asks *is this a defensible way to do this analysis?*
  rather than *does the source support this claim?* — different kind of work, so by §3's rule it
  earns its own destination.
- **A diff view for re-drafts** — when a rejected proposal is redrafted, a reviewer will want to
  see what changed rather than re-read it whole. Carried over from the old design, still true.
- **No accounts.** `--by` is a string; read `git config user.name` and let it be overridden.
  Nothing gates on identity, and adding real auth later changes one field's source.
