# The forge, redesigned

> **Status: spec, no plan yet.** Written 2026-08-19 after the operator's verdict that the forge
> is *"really unintuitive"* and *"unusable"*, and after walking the whole loop as a user rather
> than reading the code.

## 1. What is wrong, measured rather than asserted

The complaint was about looks. **It is not a looks problem**, and that is the most useful thing
the walk produced. Four findings, in the order they hurt.

### 1.1 The tool asks 11 questions per module and helps you answer none of them

`forge draft nf-core:samtools/faidx` derives 11 fields and opens 11 holes. Seven of those are
`type_id` holes, and **every one offers the same 22 candidates, in alphabetical order**:

```
one of: alignment.bai, alignment.bam, annotation.gtf, counts.matrix, fastq.reads,
        genome.fasta, genome.index.hisat2, genome.index.star, measurement.adapter_content,
        measurement.duplicate_rate, measurement.genome_length, measurement.library_prep,
        …twelve more…
```

That list is `candidates.for_field` returning **the entire vocabulary**, sorted by name
(`packages/mendel-forge/src/mendel_forge/candidates.py:37-42`). For `produces[0].type_id` on a
module whose output port is literally called `fa`, produced by `SAMTOOLS_FAIDX`, the answer is
`genome.fasta` — and the interface offers `measurement.rrna_fraction` with exactly equal
prominence.

**No amount of layout fixes this.** A denser table renders an unhelpful question faster.

### 1.2 Alphabetical order puts the answer wherever the alphabet puts it

`for_field` already computes a `note` per candidate — *which contracts already carry this type* —
and then **sorts by name anyway**. The one ranking signal in the system is computed and discarded.

### 1.3 Three screens are three filters on one axis

`Sources` and `Contracts` are the same query at different stages of one object's life:

| Screen | The object | Its axis |
|---|---|---|
| Sources | a tool a source can read | `undrafted` → `drafted` → `landed` |
| Contracts | a tool that landed | `matching` / `unverifiable` / `drifted` |
| Queue | an unanswered question *on* a draft | open / answered |

A tool moves **Sources → draft → Queue → land → Contracts**. Both list screens even carry the
same `Facets` component with the same docstring, written twice without anyone noticing what that
was saying.

**Queue is the exception and survives.** It is per-*question*, not per-*tool*: one draft holds
eleven decisions, so it is one row in a tools list and eleven items in a queue. Walking decisions
fast with the keyboard is a different job from browsing tools, and a browse list is bad at it.

### 1.4 Nothing anywhere says what any of it means

There is no glossary. The interface uses **contract, role, type, measurement, drift, hole,
band, proposal** without defining one of them. The operator co-designed this system and cannot
read its interface, which is the plainest possible statement of the problem.

`why open` on each hole is genuinely good — it explains the *epistemics* of the question — but it
is byte-identical across all seven `type_id` holes, so it reads as boilerplate by the second one.

### 1.5 `suggested` is plumbed end to end and nothing ever sets it

**The single most useful thing the walk found**, because it makes §4 cheap.

`OpenQuestion.suggested` exists on the type, crosses the API, is keyed on by `aggregate()`,
is sorted on by the queue's ordering, is highlighted by `Question.tsx:128`, and drives the
**Confirm vs Ask** label in `QueueRow.tsx:48`. Every layer is built.

`grep -rn "suggested\s*=" packages/` returns **five hits, all of them in tests**
(`test_aggregate.py`, `test_band_order.py`). `_ask()` in `questions.py:146-157` does not pass it.
So in production it is `None` on every question, which means:

- `QueueRow`'s **"Confirm" branch is unreachable** — every hole-derived row says *Ask*
- `Question.tsx`'s suggested-highlight never renders
- `aggregate()` keys on `(subject, None)` and the sort's `q.suggested is not None` is always
  `False`, so the *Ask before Confirm* ordering the comment describes is a no-op

**The whole ranking feature is one producer away from working.** Everything downstream of it was
built, tested in isolation, and left without an input.

### 1.6 One bug found in passing

`priority_because`'s hole description is `what: a value for priority_because` — a placeholder
where a question should be. `assemble.py:232` calls `_hole()` with `why=` but no `what=`, so it
falls through to `assemble.py:92`'s `what or f"a value for {field}"`. Every other hole has a real
one, and `assemble.py:86`'s own comment complains about exactly this string.

## 2. What the research says

Three patterns, from three tools that solved this at different scales.

- **Vercel — progressive disclosure.** Surface *the one metric that answers "is everything
  okay?"* first; let people drill in on demand. Their deployments-list redesign went **denser**
  and grouped environments *with* statuses.
- **Linear — density with no chrome.** ~36px rows, keyboard-first.
- **Grafana — colour-coded state plus a count per state**, and the count is the drill-down.

And the line that indicts the current Contracts screen directly:

> every element needs to earn its pixel space by helping someone make a decision or take an action

Today's contract row is 57px tall and spends it on `status | id | roles`. `roles` helps nobody
decide anything.

## 3. The shape

**One `Tools` page. A status board on top, a dense list below, the queue as a band above both.**

```
┌─ NEEDS YOU ──────────────────────────────────────────────────────┐
│ ▌1 drifted    ▌11 questions on 1 draft            walk them →    │
└──────────────────────────────────────────────────────────────────┘

  REGISTRY                                   checked 03:00 · in 12h
  ██████████░░   10 matching · 2 unverifiable · 0 drifted
  ▪▪▪▪▪▪▪▪▪▪▪▪   ← one cell per contract

  CATALOGUE                              12 landed · 1 drafted · — known
                                                              ↑ #77

  ┌ filter ─────────────┐  [all] [undrafted] [drafted] [landed] [drifted]
  │ samt▏               │
  └─────────────────────┘
  ────────────────────────────────────────────────────────────────────
   ● nf-core/samtools/sort      alignment.bam → alignment.bam    ok
   ● nf-core/samtools/index     alignment.bam → alignment.bai    ok
   ◐ nf-core/samtools/faidx     11 open                   answer →
   ○ nf-core/bedtools/sort      —                          draft →
```

### 3.1 The board answers one question

*Is everything okay?* — which for this product means **does the registry still agree with its
sources, and is anything waiting on me?** Nothing on the board is a list; every figure is a count
that links to the filter that produces it. The cell strip is one cell per contract, so the whole
registry's agreement is one glance and stays one glance at any size.

### 3.2 The list row carries what a decision needs

Not `status | id | roles`. **What it consumes → what it produces**, and its state. That is what
tells you whether a contract is the one you want, and it is the field the current row omits
entirely while spending 180px on `roles`.

### 3.3 The total is `—` until it is true

`Catalogue.known` is `None` today, because discovery reads `vendor/modules/` and can only see 13
tools (**issue #77**). The board renders `—`, not `13`. An absence is not a zero — the same
discipline as `pipeline_pins: None` and `Pipeline.ai.available: []`.

Expected real scale once #77 closes: **~1,400 nf-core + ~200 pegi3s ≈ 1,600.** The board's shape
does not change at that size; the list gains virtualisation and the filter becomes load-bearing.
**Write the trigger down**: above ~200 rows the list must virtualise, and that number goes in a
test rather than in this sentence.

## 4. The change that actually matters: narrow the candidates

**Everything in §3 is layout. This is the feature.**

`candidates.for_field` must rank, and it already holds the evidence to do it:

1. **The port name.** A port called `fa`, `fasta`, `bam`, `bai`, `gtf` names its own type in 24 of
   30 shipped ports. Match the port name against type-id segments.
2. **What contracts already carry.** `for_field` computes this as a `note` and then throws the
   ordering away. A type used by eleven contracts is a better guess than one used by none.
3. **The module's own text.** `meta.yml` describes each output in English; the excerpt is already
   quoted into the question.

The output is not a shorter list — **it is a ranked one with the top candidate suggested**.

**And the wiring is already there** (§1.5): `OpenQuestion.suggested` crosses the API, orders the
queue, highlights the candidate and switches the row label from *Ask* to *Confirm*. Nothing in
production assigns it. This section is therefore not "build a ranking feature" — it is **write
the producer for a consumer that already exists**, which is a far smaller change than the
surrounding redesign and should land first, on its own, before any pixel moves.

**This is measurable, and the number already exists.** The forge's prompt search took a local
model from 69% to 88% on hole-filling, and two of the three fixes were *the question never said
what it was about* and *the evidence was not readable*. Ranking is the same class of fix applied
to the human path. **The acceptance test is: for the 13 vendored modules, the correct `type_id`
is the top-ranked candidate in ≥80% of holes** — measured against the contracts already in the
registry, which are the ground truth for exactly these modules.

**It stays deterministic.** Ranking is arithmetic over declared data, not a model call. Invariant
2 is untouched: the forge still proposes and a human still approves.

## 5. Help, as a first-class surface

Three pieces, in order of value.

1. **A glossary.** Eight words — contract, role, type, measurement, drift, hole, band, proposal —
   each with one sentence and a link to the reference page. Reachable from `?` anywhere, and from
   the word itself where the interface uses it.
2. **Every screen explains itself when empty.** `Empty` exists and takes `title` + `next`; today
   the copy is *"Nothing here. Clear the facet to see every contract."* — which explains the
   filter, not the screen.
3. **The first `type_id` question shows `why open`; the rest collapse it.** Identical rationale
   seven times is noise. Show it once per *kind* of question, expandable after.

## 6. What this is not

- **Not a new visual language.** No new token, no new colour. The tiers' amber and coral and the
  certainty strokes are the language; the board uses them.
- **Not the landing page.** That comes last, once these screens are worth pointing at. The
  operator's instruction, and they were right: the sign came before the shop.
- **Not #77.** The board is designed so #77 landing changes a number from `—` to `1,600` and
  nothing else.

## 7. The order this must be built in

**Ranking first, layout second, help third.** Written down because the reverse is the tempting
order and it is wrong: a denser board over unranked candidates is a faster way to render an
unanswerable question.

| # | What | Why here |
|---|---|---|
| 1 | **The `suggested` producer** (§4) | The consumer is already built (§1.5). Smallest change, largest effect, and it is measurable against the 12 landed contracts as ground truth before anything visual moves. |
| 2 | **`what` for `priority_because`** (§1.6) | One line, and it is a question with no question in it. |
| 3 | **Merge Sources + Contracts into `Tools`** (§3) | Needs `GET /api/tools`; the two listings cannot be joined client-side without two round trips. |
| 4 | **The status board** (§3.1) | Sits on the merged page. Depends on 3. |
| 5 | **Help and the glossary** (§5) | Independent of 1–4 and can be done in parallel by anyone. |
| 6 | **The landing page, revisited** | Last. It points at these screens, so it cannot be designed before they exist — the mistake 3B made. |

Step 1 has an acceptance number and the rest do not, which is deliberate: it is the only one
whose success is a measurement rather than a judgement.

## 8. Open questions

- **Does `Forge` survive as a nav item?** With one Tools page and a Queue, the workspace row
  (`Builder` / `Forge`) and the section row collapse into each other. Probably: `Comeni Labs |
  Tools · Queue | Builder (soon)`.
- **Where does the registry lookup live now?** Deleted with the nav box in 3B. It should hang off
  a type id you click — and the Tools row now shows type ids, which is the natural host.
- **Is `roles` worth a column anywhere?** It is what routing matches on, so it matters to the
  resolver and is nearly meaningless to a person choosing a tool. Suggest: on the module page,
  not in the list.
