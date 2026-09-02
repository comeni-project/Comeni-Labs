# 2026-08-17 — the forge, Phase 2: a model fills the holes

The third entry today. [`2026-08-17.md`](2026-08-17.md) handed Plan 2 over for redesign;
[`2026-08-17-the-forge.md`](2026-08-17-the-forge.md) reported Phase 1 and asked the fifth-door
question. This one answers it and reports Phase 2, executed end to end.

## Where things stand

**`mendel-ai` exists, and the forge can call a model.** Fourteen tasks, all run. `make verify` is
green. `mendel-ai` is the second entry in `IMPURE_PACKAGES`; `test_no_pure_package_imports_an_impure_one`
is unmoved, because the new arrow is `mendel-forge → mendel-ai` and both are impure.

The loop is unchanged at six steps — `discover → draft → show → fill → verify → land` — because
a model fill **is** a fill: `forge fill <draft> --model <id>`.
[`docs/guides/driving-the-forge.md`](../../guides/driving-the-forge.md) §4 is that step with
real output; `ARCHITECTURE.md` §10 is the description against the types;
[`the spec`](../specs/2026-08-17-forge-phase-2.md) is why each part is shaped that way.

**No counts in this entry.** `make check` counts the tests, `make residue` counts guard coverage,
`len(DeclaredKind)` counts the kinds. Two numbers in `CLAUDE.md` were stale for three plans
because nothing counted them (A71, A72), and this file does not add a third.

## The fifth-door question, answered

**There is no door 5**, and `DOORS` and `tests/test_egress.py` did not change — which is the
evidence rather than the claim.

`docs/design/clinical-data-protection.md` §4.2 has always stated what the egress boundary
tracks: *free text enters at exactly one door*, and the question for anything else is whether it
is downstream of it. Read that way the four doors are **one path** — prompt, goal, build,
pipeline, publish. `PromptRequest.prompt` is the taint source; `AmbiguityRequest` is closed
vocabulary because it is downstream of it; `ErrorCategory` exists because Nextflow's stderr
carries work directories and filenames.

The forge is not on that path. It has no prompt, takes no `Goal`, writes no `pipeline.yml`. It
reads vendored modules and registry files — public data — and produces registry files a build
later consumes. `AiPoint` corroborates it **without being changed**: invariant 3 declares three
runtime AI points and the forge is not one.

So what changed is prose that had lost §4.2's qualifier: `CLAUDE.md` invariant 14,
`ARCHITECTURE.md`, and §4.1 of the design doc. The forge spec's §10.3 keeps its question and
gains its answer, because the question is what got this asked.

**The cost of answering it this way, stated rather than waved past.** Phase 1's handoff warned
that a carve-out is what future carve-outs cite. The argument that this is a *scope correction*
rather than a carve-out rests entirely on §4.2 predating the question — if that reading is ever
judged wrong, the thing to revisit is the wording, not the guard, because the guard never moved.

## What a fresh reader gets wrong

**"`mendel-ai` only does closed choice."** It did in the first draft of the spec, and that was
wrong twice — recorded in spec §4.3 rather than quietly replaced. It drew the boundary at
*choice versus generation* when the rest of the system draws it at **validated against a declared
shape**; and it was designed against the tier-4 ambiguity resolver, which is Plan 3, while the
next consumer is the rule drafter, which does not fit a list of options. The primitive is
`generate(instruction, shape, evidence)`; `choose_one`/`choose_many` are helpers over it.

**"The package cannot generate prose."** It cannot, *except* through `Choice.why`, which is free
text the model writes and the package returns — so a caller wanting prose can hand `generate` a
one-field shape and read the field. Contrived, visible in review, and **not prevented**. Claiming
"cannot" is the mistake `CLAUDE.md` records about invariant 1, sold as structural until A1 opened
a TCP socket out of allowlisted imports. Cost-raising, not a proof.

**"A model fill is a suggestion."** It lands as an answer, marked. `Filler.MODEL` and the model
id in `FilledValue.by` already reached `Provenance.drafted_by` through Phase 1's
`assemble._drafted_by`, so **no artifact schema changed at all**. The honesty is paid by display:
`forge show` prints `(filler, by)` beside every value — and it already did, which is why Task 12
became a test rather than a change.

**"`--no-ai` arrived."** It did not, and `CLAUDE.md` is corrected in two places. `--model` is
opt-in, so the forge's default *is* the no-AI lane — nothing to switch off, nothing to leave
accidentally on. `mendel build` has no AI path at all until Plan 3.

## The two defects the hand-run found, with every test green

Phase 1's handoff said to run the documented loop by hand before believing the tests. It earned
itself again, in the same shape: **both of these were invisible to a green suite.**

- **Every model-access failure reached the user as a traceback.** `NoModelError` and
  `ModelUnavailableError` were `RuntimeError`s, and the forge CLI catches
  `(OSError, KeyError, ValueError)` — the refusal contract `ops.py`'s own docstring states. They
  are `ValueError`s now.
- **A model id with no provider prefix escaped as `litellm.BadRequestError`**, with LiteLLM's own
  stderr banner above it. `LiteLLMTransport` caught the two shapes that had been *anticipated*,
  authentication and timeout. `MA0007` is the catch-all, and it quotes the provider's message
  verbatim rather than swallowing it. **A transport boundary that lets a third-party exception
  through reports somebody else's error message to our user.**

A third, smaller: `_CODE` in the CLI matched `MF` only, so an `MA` refusal printed no
`run: forge explain` pointer — and the reader who typed `--model` and got `MA0001` is exactly the
one who needs it.

## A process failure worth more than any of them

**`make check` was red for four tasks and I did not see it**, because I was grepping its output
rather than reading its exit code. `check`'s prerequisites run in parallel, so a lint failure in
`tests/test_no_live_model.py` (a Yoda condition, `SIM300`) scrolled past a
`grep -E "passed" | tail -2` that was faithfully reporting the test results underneath it.

Nothing was broken by it — one line, auto-fixable — and that is not the point. The point is that
**a filter tight enough to be readable is tight enough to hide a failure**, and the fix is to
check the exit code and only then filter for detail. It is the same family as A67: a guard whose
output nobody reads is a guard nobody is running.

## Corrections to the plan

Six, recorded because `notes/README.md` says to expect them.

1. **The absent-fact test asserted nothing.** It was written against `fastqc` guarded by
   `if not spec.reads_ext_prefix` — and `fastqc` reads `task.ext.prefix`, so the body never ran.
   It uses `samtools/index` now, plus an assertion that the fixture still lacks one.
2. **Block facts cited the block's *header*.** `emits` read `text: "output:"`, a real line
   teaching a reader nothing — the same defect one level down. `ModuleSpec` records a block's end
   too, and a block fact quotes what the block declares. **Found by reading the golden diff**,
   which is what the plan said to do.
3. **Every span ended in whitespace**, because a block match runs to the blank line before the
   next keyword. Trailing blanks are trimmed and the locator's range follows: `13-17` became
   `13-16`.
4. **`make docs` is the `--check` form**, not the regenerator. The plan says it regenerates; it
   fails instead. `uv run python tools/generate_diagnostics_doc.py` with no flag is the fix.
5. **`MA0005` was declared a task early.** The ownership guard caught it within the minute —
   declared in `diagnostics.yml`, emitted nowhere — which is the global constraint the plan
   states and the plan's own YAML block violated.
6. **The mid-batch-failure test exercised nothing.** Its fake counted *calls* rather than fills,
   so it depended on hole order and raised `IndexError` on a candidate-less one; and it ran
   against a scaffold with one fillable hole, where there is nothing for a provider to die
   *after*. It has a two-hole workspace now.

`isinstance(filler, HoleFiller)` also raises — `HoleFiller` is a plain `Protocol`. Rather than
decorate a Phase 1 port for a test's convenience, the test annotates and calls, which checks the
signature where `isinstance` would only have seen the method name.

## The guard

One new row in [`the ledger`](../audits/guard-ledger.md): `tests/test_no_live_model.py`, watched
failing, with the message it printed. `CLAUDE.md` had asked for it since before it could exist —
*"no test may call a live model"* was written when there was no model to call.

Two of its three tests exist because of A67: one asserts the matcher trips on text that should
trip it, one asserts the file list is not empty. That second one nearly earned itself
immediately — the plan's version rglobbed from the repository root, and `.venv` is inside the
worktree.

## What is next

**The rule drafter** ([`notes/README.md`](../README.md) row 16), then **Plan 3**. The argument
for that order is that each step shrinks the next one's job: the forge fills the registry, the
drafter fills tier 3, and tier 4 — which Plan 3's ambiguity resolver serves — is the fallback
from tier 3. Nothing currently authors a tier-3 rule.

`generate(shape)` is the surface the drafter needs and it is why the primitive is shaped that
way. Read spec §4.3 before changing it.

## What Phase 2 deliberately did not do

- **[#70](https://github.com/comeni-project/Comeni-Labs/issues/70)** — prose holes.
  `priority_because` is the one free-prose value that reaches a registry, and nothing can check
  it. A model is never asked about it, which is stronger than asking and discarding.
- **[#69](https://github.com/comeni-project/Comeni-Labs/issues/69)** — `AiProvenance.available`
  is hardcoded to `[]`, and `MD0225` refuses the first model-backed *build*. Untouched here
  because the forge writes registry files and not `pipeline.yml`; it is Plan 3's first task.
- **[#71](https://github.com/comeni-project/Comeni-Labs/issues/71)** — the three protection
  profiles are documented and implemented in zero lines. Found while looking for somewhere to
  add a `sealed` task, and larger than this phase. The spec's §3.6 originally asserted that
  `sealed` makes no forge model call, justified as "the profile table's logic applied straight" —
  which is the same analogy §1 rejects.
- **Conformance line numbers.** `ModuleSpec` records positions now and `MD01xx` does not use
  them. That change moves message text, golden output and the generated page, and it is worth
  more than the forge's share of it.
