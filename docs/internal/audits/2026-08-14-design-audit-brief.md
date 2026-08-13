# The design audit — the brief

**Not an audit. The instructions for one.** Written 2026-08-13, at the end of Plan 1.12, to be
run in a fresh session against `plan-1.12` (or `main`, once [#23](https://github.com/comeni-project/Comeni-Labs/pull/23)
and [#37](https://github.com/comeni-project/Comeni-Labs/pull/37) merge).

**This one is not like rounds one through four, and the difference is the whole point.**

Those rounds asked: *does the code do what it says it does?* They were right to, and they found
real things — arbitrary code execution, three defeated guards, a certifying verb that certified
nothing. But a codebase can pass every one of those checks and still be built on a design that
cannot deliver what it promised. **Eleven plans have been built on a design approved on
2026-08-02, on day one, before any of the types existed.** Nobody has since asked whether that
design is still the right one — only whether the code matches it.

This audit asks the other question:

> **Does the thing we built actually do what Mendel is for?**

## What it is being audited against

Two sentences, from `docs/design/mendel.md` §1 and `CLAUDE.md`:

> Comeni Labs exists to make pipeline construction **explainable and reproducible** rather than
> merely fast. […] in an age where AI leads, humans must still be able to follow.

> Same goal in → same pipeline out, and nothing was guessed silently.

Everything below is a way of asking whether the built system earns those. Not whether it is
elegant, not whether it is idiomatic — whether a biologist who did not write it can follow what
it decided, and whether the same question asked twice gives the same answer for the same reasons.

---

## The method

Rounds two through four ran on **revert and watch, not read**: break the code a guard protects
and confirm the guard fails. That protocol is not available here. You cannot revert a design
decision and watch a test go red — the design *is* what the tests were written against, so they
will all agree with it. A design audit run by reading is exactly the failure mode round one had.

So this audit gets its own discipline, and it is the reason the brief exists:

> **Build the artifact that should exist and cannot.**

Every finding must be demonstrated by producing something concrete, or by demonstrating that
something concrete cannot be produced. **Three admissible shapes**, and nothing else counts:

| Shape | What you must show | Example of the evidence |
|---|---|---|
| **(i) The claim breaks** | a real goal, contract or `pipeline.yml` where "same goal in, same pipeline out" or "nothing guessed silently" is false | two builds, a diff, and the value nobody can explain |
| **(ii) The claim cannot be stated** | a decision the design has **nowhere to record**, so the trace is silent by construction rather than by bug | the field that does not exist, and the reasoning it would have to hold |
| **(iii) The design cannot carry known load** | a change that is already committed to — Plan 2's three doors, v2's alternative aligners — and what it forces to be rewritten | the specific type or function that has to change shape, and why |

**"This would be cleaner" is not a finding.** Neither is "this file is long." `cli.py` is 747
lines and that is only a finding if you can name the work in it that belongs somewhere else *and*
show what breaks because it is there. Aesthetic judgement without one of the three shapes above
is noise, and this repository already has more findings than it has capacity to fix.

**Conversely: "the design holds here" is a result, and it must be demonstrated too.** An audit
that returns only problems is not more rigorous than one that returns none — it is less, because
nobody can tell what was actually examined. Say what you attacked and what survived, the way
round four's *Clean — attacked and held* section does.

### Two failure modes specific to this kind of audit

- **Rediscovering a known open question and filing it as new.** Issues [#1](https://github.com/comeni-project/Comeni-Labs/issues/1)
  (routing ties should ask a human), [#2](https://github.com/comeni-project/Comeni-Labs/issues/2),
  [#11](https://github.com/comeni-project/Comeni-Labs/issues/11) (the v1 module count),
  [#16](https://github.com/comeni-project/Comeni-Labs/issues/16),
  [#18](https://github.com/comeni-project/Comeni-Labs/issues/18) and the thirteen carried
  round-four findings (#24–#36) are **already known**. Reaching one of them independently is a
  *confirmation* and worth saying so — "the design audit arrived at #1 from the other direction"
  is useful. Filing it as a discovery is not.
- **Arguing with a decision that was made deliberately and recorded.** `docs/internal/README.md`
  and the journal record *why* each ordering and design call was made, usually with the argument
  against it written down. If you disagree, engage that argument — do not re-run it as if nobody
  had. Where a recorded reason has since stopped being true, **that** is a finding, and a good one.

---

## The four streams

Independent reviewers, **no session context**, each with its own finding-number block.

**Findings continue from A75. Blocks are pre-assigned** because round four had two reviewers
independently number a finding `A70` and one had to be renumbered by hand.

| Stream | Angle | Numbers |
|---|---|---|
| 1 | The claim, end to end | **A76–A89** |
| 2 | The compiler, as a compiler | **A90–A103** |
| 3 | The artifact as the interface | **A104–A117** |
| 4 | Load-bearing assumptions vs. what is left to build | **A118–A131** |

### Stream 1 — The claim, end to end

Take the product claim literally and try to break it with ordinary use, not with an attack.

- Build the spine. Change **one** thing in the goal. Is the `pipeline.yml` diff minimal and
  explainable, or does one edit move things nobody asked to move?
- Does **every** value carry a `why:` that a stranger could act on? Find a value whose reason is
  circular ("contract default for X" says who decided, not why), technically true and useless, or
  absent.
- **"Nothing guessed silently" is the sentence to attack hardest.** Where does a value arrive
  from ordering, from a fallback, from a default-of-a-default? A tier-2 "documented default" is
  only honest if a document exists — check that the citation behind a convention is real.
- The tier ladder itself: are the four tiers a real partition, or do some decisions not fit any
  of them and get assigned the nearest label? `ParamAsked` candidates are literally `[None]` —
  a tier-4 "ambiguity" with one fake candidate. Is that a tier-4 decision or a missing feature
  wearing a tier-4 costume?

### Stream 2 — The compiler, as a compiler

`mendel_compiler/` is 1,961 lines: `cli.py` 747, `emit.py` 390, `conformance.py` 351,
`modulespec.py` 192, `pipeline_file.py` 148, `gates.py` 99.

- **Is `emit` a compiler, or a template renderer with a growing pile of special cases?** The
  `via:` routes are a closed enum of three — `ext`, `meta`, `directive`. Is that a complete
  partition of "where a value can go", or three cases that happened to be needed? What is the
  fourth thing a tool needs that none of them expresses?
- **The nf-core assumption.** `ARCHITECTURE.md` §5a claims the design works for "a pegi3s image
  or an in-house process too", and that entry channels come from the vocabulary rather than the
  compiler for exactly that reason. **Test that claim by trying it**: write a contract for a
  module that is *not* nf-core-shaped — one that reads no `task.ext.args`, has no `meta` map, no
  stub block — and see how far it gets. If it cannot be expressed, the claim is false and the
  registry can only ever hold nf-core modules.
- `cli.py` is 38% of the compiler. `ARCHITECTURE.md` says "`cli.py` is the only thing that
  touches disk", which is a real justification for size. Is everything in there disk-touching,
  or has orchestration and policy accumulated where it is hardest to test?
- **Conformance as an FFI binding** (`docs/design/conformance.md`). Nine diagnostics check a
  contract against a vendored `main.nf`. Is that the right *depth* — what disagreement between
  contract and module can still pass all nine?

### Stream 3 — The artifact as the interface

`pipeline.yml` is the product. `docs/reference/pipeline-schema.md` is its spec.

- **Read it as a bench scientist.** Build the spine, open `build/pipeline.yml`, and ask whether
  a molecular biologist could follow what was decided and why. Where does it demand knowledge of
  Mendel's internals to read? That is the philosophy failing, and it is the most on-brief finding
  this audit can produce.
- **It is simultaneously a record and an executable input**, and A55 was the sharp end of that:
  `settings[].value` is documentation a human is invited to edit *and* a value that reaches a
  tool. Is that dual role sound, or does it need a boundary the design does not currently have?
  A55 was patched; the shape that produced it was not examined.
- Does the file read **one way**? Round two's root G was "a field that reads two ways". Find a
  second one, or establish there is not.
- `upgrade`, `replay`, `emitted:`, digests: does the lifecycle hold together as a *story a person
  can tell*, or as five mechanisms that each work? A70 was a verb certifying with no evidence,
  and it was found only because someone asked what publish actually promises.

### Stream 4 — Load-bearing assumptions vs. what is left to build

The design was approved before Plan 2 and v2 existed as code. This stream asks what breaks.

**Do this first, before anything else in this stream.** It is the highest-value single thing this
audit can do, and it is a shape-(ii) finding — *the claim cannot be stated*.

> **Take twenty real, abstract tier-3 rules from the literature. Try to write each one in the
> current rule format. Report what breaks.**

The format was designed against a registry holding **one** rule, and the domain is understood to
hold thousands. `docs/design/rule-tables-and-port-logic.md` §13 records three limits reasoned from
that single example — a literal-only `then`, a `when` that sees only measurements, and the
completeness problem over alternatives — plus the recommended repairs and their costs. **§13 is an
argument. Twenty rules would make it evidence**, and the ones that cannot be written are the
specification for the reform. Confirming, refuting or extending §13 against real rules is worth
more than any other finding in this stream. Issues [#38](https://github.com/comeni-project/Comeni-Labs/issues/38)
and [#39](https://github.com/comeni-project/Comeni-Labs/issues/39) hold the current state of it.

- **Plan 2 opens three of the four doors.** Read `docs/internal/plans/2026-08-02-mendel-ai-and-forge.md`
  (stale, and says so) against the types that now exist. Does the `AmbiguityResolver` port
  actually take a model? A56 just established that `Resolution.source` is a claim a resolver
  cannot be trusted to make — **what else in that protocol is trust-shaped?**
- **v2 breadth is alternative aligners** — which means routing ties become the common case rather
  than the exception. §13.4 argues this is issue #1 and the `when`-expressiveness question wearing
  one hat: `priority` is a purpose-independent scalar, so ranking alternatives silently prefers
  one, leaving them equal ties everything into tier 4, and only a complete `producer_of` rule is
  honest. **Attack that argument.** Is there a fourth state it missed? Is the "adding a contract
  can make the pipeline worse" consequence real — can you demonstrate it by adding one?
- **The registry is empty of everything except the spine.** Every contract in it is "a test
  fixture that happens to be true" (`CLAUDE.md`). The forge is supposed to fill it. Does anything
  in the design assume a small registry — routing cost, tie behaviour, digest scope, load time?
- `[None]` candidate lists, `ProfilePolicy` (does not exist), `sealed` blocking tier 4 (issue #2):
  what does Plan 2 have to invent that the current types leave no room for?

---

## What to read, and in what order

For a reviewer with no context. Roughly two hours before touching anything.

1. `docs/design/mendel.md` §1–3 — the philosophy, the claim, the v1 criterion. **This is the
   thing being audited against.** Everything else is evidence.
2. `CLAUDE.md` — the invariants, the tiers, the gotchas. Note that it is a *summary* and the
   journal is the handoff.
3. `ARCHITECTURE.md` — the five stages against real types. Written to be read before writing code.
4. `docs/reference/pipeline-schema.md` — the artifact, field by field.
5. `docs/internal/journal/2026-08-13.md`, then backwards as far as patience allows. It carries
   what was decided and, more usefully, what was *corrected* mid-flight.
6. **Then build something.** `make verify`, then `uv run mendel build --goal examples/rnaseq-goal.yml
   --out build/ --gate stub` and read the output. A reviewer who has not run it is reading fiction.

---

## Deliverable

`docs/internal/audits/2026-08-14-design-audit.md`, in the house shape: a findings table with
severity and verdict, one section per finding with its demonstration, and a **Clean — attacked
and held** section that is not optional.

It must end with one of three verdicts, stated plainly:

- **The design holds.** It can deliver the claim, and here is what was attacked to establish that.
- **It holds with named repairs.** These specific things must change, and here is what each costs.
- **It cannot deliver X.** Here is the part of the claim the current design cannot reach, and
  here is what a design that could would have to look like.

**The third verdict is admissible and must stay admissible**, or this is theatre. Eleven plans of
sunk work is a reason to ask the question carefully, not a reason to prefer a particular answer.
Equally: the first verdict is a real possible outcome and must not be treated as a failure to
find anything.

## Scope boundaries

- **This does not reopen the A14 loop.** A14 is carried by decision (2026-08-13,
  `docs/internal/README.md`). This audit's findings shape **Plan 2**, or they justify a design
  change before Plan 2 — they do not create a Plan 1.13 of guard repairs.
- **Do not re-audit the guards.** Rounds one through four did that four times, and Plan 1.12
  just closed the last criticals. If a guard is *structurally* incapable of protecting what it
  claims — a design finding, shape (ii) — that is in scope. "This guard could be stronger" is not.
- **Do not audit the toolchain.** Verified 2026-08-02 and not re-litigated since; `CLAUDE.md`
  says so explicitly.
- **The registry's emptiness is not a finding.** It is the forge's job and is known
  (`CLAUDE.md`, *Emptiness and deadness are different problems*). Whether the *design* assumes a
  small registry **is** a finding — stream 4 has it.

## Running it

Four reviewers, independent, no session context, one stream each. **Give each its number block
explicitly in the dispatch**, and expect at least one to hit a session limit and need relaunching
— two did in round four, and both completed after the reset.

**Re-verify every reviewer claim first-hand before recording it.** Round one had a claim with a
right conclusion and a wrong mechanism; round four had reviewers raise findings that did not
reproduce. A finding not reproduced by the synthesiser is marked PLAUSIBLE and is a hypothesis,
not a result.

The synthesiser holds one lens no stream does: **the philosophy question.** After the four
streams land, read the whole thing as the biologist in `docs/design/mendel.md` §1 — the one who
can get a plausible pipeline out of a chat window in minutes and has no basis for judging it.
Is Mendel visibly better than that chat window *for them*, or only for us? That is the question
the product claim exists to answer, and no individual stream will ask it.
