# 2026-09-06 — the forge runs, and everything that only broke when it did

**The Forge MVP is complete.** Thirteen tasks, and then a day of driving the loop with real
upstream data and a real model, which is where the interesting half of this entry comes from.

Read this before touching the forge. The tasks are in
[`2026-09-04-forge-mvp.md`](../../superpowers/plans/2026-09-04-forge-mvp.md); what follows is
what running it found, because **almost none of it was findable any other way.**

---

## What now works, measured rather than asserted

| | before | after |
|---|---|---|
| nf-core catalogue | 1 hand-seeded row | **2,062 real tools** |
| requests per sync | ~2,400, never completed inside one hour's budget | **2**, 10.4 s |
| requests to adapt one tool | ~700 | **2** |
| catalogue refresh | only when somebody pressed a button | hourly, and on startup |
| the AI worker | had never taken a job off its own queue | takes them, on a GPU, over the compose network |

The whole chain runs untouched from one HTTP call: sync → scaffold → the AI worker claiming the
job → `gemma3:12b` on an AMD card → the validation ladder → `review`.

**The deterministic half is the product's claim and it had never once been exercised.** Against
`nf-core:seqkit/fq2fa` fetched from real upstream it proves eight values — the exact container
digest, the include path, the arity, the process name, all `derived by nf-core` — and hands out
six typed questions addressed by **channel name**, each carrying what it asks, why it could not
be settled, its legal set, whether that set is exhaustive, a ranked suggestion where the
arithmetic is confident, and **the evidence it rests on**. `consumes.fastq.type_id` ranks
`fastq.reads` first with no model involved. `priority_because` correctly offers no candidate set
at all.

---

## The lesson, and it is one sentence

**A loop nobody has driven has as many defects as it has stages.** Nine were found in a day,
each by fixing the one before it and running again, and *not one* was visible to the 2,400-test
suite.

Two shapes account for almost all of them.

### One: a test that sets up more than its subject does

`_derive_and_write` is monkeypatched in every test that touches it, so nothing had ever watched
it lay out a directory. It passed neither `source=` nor the derived `Scaffold` to
`write_bundle`. The review page therefore answered **404 for every real adaptation**, and every
generation would have failed reading *no stored source*.

The review-page fixture called `workspace.save(Draft(...))` immediately before `write_bundle`,
under a docstring saying it laid things out *the way the jobs do*. **It was supplying the file
the job never wrote.** Ten tests passed over a page that 404s in production.

The same shape again: a guard written for the new `multiple` flag called the helper directly and
**passed with the call site deleted** — it proved the function worked and nothing about the hole
a model is handed. The scaffold golden caught what the named guard could not.

### Two: an all-or-nothing rule that throws away almost-complete work

Three separate places, each defensible alone, each costing a whole run:

- the generation loop returned `proposal=None` after exhausting its repairs, discarding a
  proposal that had answered four of six questions **and been validated** — and reporting
  `unresolved: 0`, because there was no proposal left to count against;
- `admit()` refusing was fatal, so one hallucinated hole id out of seventeen threw away 213
  seconds;
- two repairs produced byte-identical proposals — 135 of one run's 205 seconds spent learning
  that the model had already said what it had to say. At temperature 0 that is the expected
  case, not a surprise.

**`succeeded()` is `proposal is not None` and never meant *green*.** Conflating the two is what
discarded the work.

---

## Things that were two things wearing one name

**`workspace.load` and `read_draft`.** `save`/`load` address a draft by the name a person gave
it and write `<root>/<name>/`; an adaptation lives at `<root>/forge/<id>/`. Same argument type,
same return type, and **four call sites used the wrong one** — the review page, the generation,
the review chat, and the landing. Each failed a layer away from the mistake and each was found
only by driving the loop one stage further. A scan finds all four at once.

**Two notions of `required`.** `ScaffoldHole.required` is what a model and a page are told;
`Scaffold.is_complete()` is what `verify` and `land` enforce. They now read one constant.

**Two things called `Proposal`** — a whole model response, and one vocabulary entry a hole needs
declared. Both names are right in their own module; `render.py` is the one file that holds both
and aliases accordingly.

**`_structure_only` stripped `description` at every depth**, including a *property named*
`description`. Any future field called `description` or `title` would have vanished from the
schema the model is shown, sending nothing and saying nothing. Inside `properties` and `$defs`
the keys are author-chosen names; everywhere else they are JSON Schema keywords.

---

## What the model did, and why it is an argument for the design

`gemma3:12b`, locally, on an 8 GB card:

| tool | holes | outcome |
|---|---|---|
| `seqkit/fq2fa` | 6 | answered 4, **correctly declined 2** |
| `falco` | 7 | answered 4 |
| `fastp` | 17 | invented a hole id on all three attempts |

**Structured-output reliability falls off with hole count**, and the failures were ours as often
as the model's:

- `roles` is `list[RoleName]` and `Answer.value` was a single `str`. *These two roles* had no
  expressible form, so declining was the least-wrong thing available. `ScaffoldHole.multiple`
  now says so, **derived from the contract field's annotation** rather than from a list that
  goes stale.
- The `roles` question says *every one of the 12 contracts declares exactly one role* — derived,
  and the fix for a measured failure where a model chose three. Put a bare *answer with: a list
  of values* beside it and a small model resolves the apparent contradiction by answering
  neither.
- `Proposal.module` was in the schema for a source that **may not author a module**. A field
  offered and forbidden is a trap, and it is what the model grabbed on fastp's first run.
- The dossier's section names — `identity`, `evidence`, `facts` — are id-shaped, and that is
  what it grabbed on the second.

**Twice the model declined and was right both times**, which is the honest headline. No role in
the closed vocabulary describes *convert FASTQ to FASTA*; no evidence in a tool's own README
supports a comparative ranking claim. Its unreliability stayed confined to a typed input and
never reached an artifact. Every gate refused correctly, every time, all day.

---

## Decisions taken

- **`priority_because` is not required** (#99). It failed two of `approval_refusals`' six
  checks, so **nothing could ever be approved, for any tool** — and it is `str = ""` in the
  schema with no contract in the registry carrying one. The hole still opens. What remains on
  that issue is where a justification for a ranking should come from: a comparative claim wants
  a cited paper, and nothing in a dossier carries one.
- **A model can propose a vocabulary entry** (#100). The mechanism existed —
  `scaffold.Proposal` documents `by` as *"the model id that proposed it"* — and only the CLI
  could reach it. `Analysis` has a third arm; `render.apply` routes it to `Scaffold.propose`,
  **never `fill`**, so the hole stays open and a person still moves the entry into
  `vocabularies/`. **No model runs a verb**: it returns a typed value and deterministic code
  performs the action, which is the inversion the whole product rests on.
- **`GET /rate_limit` lies for a fine-grained GitHub token.** It reported `used: 0, remaining:
  5000` while a real request in the same second returned `x-ratelimit-used: 5000` and a 403.
  That mis-diagnosis sent this session hunting a wiring bug that did not exist. **The
  `x-ratelimit-*` headers on a real response are the only honest source.**
- **Docker Hub caps anonymous paging at offset 0**, so the pegi3s namespace is 199 repositories
  of which 100 are reachable — and the adapter correctly refuses a short total rather than
  publishing two thirds of a catalogue. Wired for a credential, not yet exercised.

---

## What is next

**Not the loop — the model.** Everything from source to `review` runs; what is shaky is a 12B
local model on a seventeen-hole structured task. Wiring a stronger provider is a configuration
change by construction (invariant 13), and it is the single highest-value next step.

Then, in order: **approve → land → `mendel build`** on a candidate whose holes are all closed;
**request-changes → a second revision**, the one review verb never exercised; **the review
chat**, door 5, its own job and its own prompt, never run; **pegi3s**, which needs a Docker Hub
credential and unlocks module generation for a source that ships no Nextflow — the last untested
*kind* of adaptation; and **a browser**, because every screen so far is `curl` and headless
screenshots.

`tests/fixtures/guard-ledger.md` carries the reverts, with the message each one printed.
