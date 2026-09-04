# The forge gets a catalogue, a workflow and a scaffold that says what it guessed

*2026-09-04. Five commits on `main`, in the worktree `.claude/worktrees/forge-mvp`. Tasks 1–5 of
the Forge MVP plan, out of thirteen.*

The plan is
[`../../superpowers/plans/2026-09-04-forge-mvp.md`](../../superpowers/plans/2026-09-04-forge-mvp.md),
written by Codex, with an execution record under each completed task. **It was checked against the
code before execution and was accurate**, which is worth recording because it usually is not here
— every prior plan in this repository predicted at least one type that did not exist.

---

## What is true now

**The forge can say how big the world is.** Two adapters — `NfCoreAdapter` and `Pegi3sAdapter` —
sit on a `BaseSourceAdapter` that owns retry, conditional requests, evidence numbering, digests
and pagination. Before this, `Source.discover(root)` could only see modules *already vendored*,
so the catalogue's answer to *how many tools exist* was *thirteen*, which is the number we had
imported.

**PEGiS reads its own ontology.** `pegi3s/dockerfiles/metadata/` carries three files doing three
jobs, and the split matters: `dio.obo` is the hierarchical filter **vocabulary**, `dio.diaf` is
the many-to-many **assignment** table, and `metadata.json` describes each image. Nothing infers a
category from prose and nothing infers one with a model. `sources/dio.py` parses all three.

**A tool says whether it can be checked at all.** `supplies_tests` is per tool rather than per
source, because `metadata.json` carries `test_invocation`, `test_data` and `test_result` for some
images and not others — a command, an input, and an expected output. All three or it does not
count. `test_result` is also the only machine-readable output signal PEGiS publishes, and it is
now an `output_hint`.

**The workflow has somewhere durable to live.** Seven Postgres tables, one migration, and
`services/forge_state.py` as the only thing that moves an adaptation. Every transition is one
`UPDATE … WHERE id AND state AND row_version`, so a second browser tab and a duplicate ARQ
delivery both lose rather than overwrite. Every foreign key is `RESTRICT` and none is `CASCADE`:
archiving never deletes revisions, events, messages or invocation audit, and the way that stays
true is that there is no cascade to break it with.

**A scaffold is composed as values and written by one function.** `bundle.py` returns the whole
directory as `(path, text)` pairs and touches no filesystem; `workspace.py` writes them. That
keeps `tests/guards/test_forge_write_boundary.py` at exactly two allowed writers, and makes *two
scaffolds from the same digests are byte-identical* an equality of two tuples.

**A hole is addressed by the channel it is about** — `consumes.reads.type_id`, with
`/consumes/0/type_id` beside it. An index is not an identity: add a channel upstream and
`consumes[0].type_id` renames every hole after it, so a stored answer, a review citing it and a
repair pass pointing at it all come to describe a different port.

**`modulegen` no longer guesses.** It declared exactly one input and `path("*.out")` for a source
that proves neither. Both blocks carry `MF0011` now, `open_sections()` finds them, and `verify`
grew the rung that `SCRIPT_HOLE`'s docstring had claimed existed since forge phase 1.

**`comeni-ai` exists.** `mendel-ai` moved to `packages/comeni-ai/`, import name `comeni_ai`, with
`COMENI_AI_*` config and the `MENDEL_*` names as a deprecated fallback. `mendel-ai` is now a
one-file shim that re-exports the pre-rename surface and warns on import. The plan explicitly
ruled out the generic `ai-core` distribution name.

---

## The lesson of the day, and it repeated five times

**Two mechanisms that each fully answer one question, presented as defence in depth, are almost
always one mechanism and one decoration.** Five instances in three days:

| where | the pair | which half was carrying it |
|---|---|---|
| `SourceSnapshot.classified` | match on a classification's `id` **or** its `ancestors` | either — so neither defect could fail a test |
| `pegi3s.ALIASES` | an alias list beside an anchored `SEMVER` | `SEMVER` already rejected every alias |
| `forge_state.move` | compare `state` **and** `row_version` | `state` — deleting the version compare left all 17 tests green |
| `Workspace._inside` | a string check **and** a resolved containment check | `resolve()` strictly contains the string check |
| one active adaptation | a service refusal **and** a partial unique index | **both** — this one earns it |

**The test that separates an earning pair from a hiding one is to delete each half separately and
watch what fails.** The last row passes it: the service refusal produces a sentence naming the
adaptation already in flight, and only the index survives two simultaneous requests. Deleting
either brings down a different test.

`row_version` is the one to remember. Every stale case in the suite also carried a mismatched
*state*, so `expect` alone answered all of them and the version looked like belt and braces. The
case it actually covers is a state moved through and back — a reviewer opens a candidate, someone
else requests changes, a new revision returns to `review`, and the first tab holds the right state
and the wrong candidate. Pressing *Approve* there approves work it has never seen.
`test_a_tab_that_left_review_and_came_back_to_it_still_loses` was written after the revert and is
now the only test it is load-bearing for.

---

## Four other things that cost time

**A comment claiming a guard exists is worse than no comment — second instance.**
`modulegen.SCRIPT_HOLE` said *"`verify.py` raises the same code as a `Diagnostic` when it finds
this marker"*, and nothing in `verify.py` had ever looked at a generated module. `geometry.ts` was
the first. Before trusting a sentence like that, grep for what it names.

**A test that passes over an empty collection.** `test_migrations.py` compares `Base.metadata`
against rendered DDL, and `Base` alone does not populate that mapping — `mendel_api.models` must
be imported for its side effect. Without it every "for each table" assertion iterated nothing and
passed. What caught it was the one test reading the DDL *backwards*. That is `tests/README.md`'s
own rule arriving in a new place on the day after it was written down.

**Two defects found by printing a real derivation, not by a test**, which is why the goldens
exist: `assemble.DERIVED_FIELDS` maps the *fact* `process` onto the *field* `nf_process`, and
naming the fact after the field left a module plainly declaring `process FASTQC {` opening a hole
asking what it was called. And a PEGiS container **digest** opened a hole instead of settling one
— pinning by digest is the single axis on which PEGiS beats nf-core, which pins a mutable tag.

**A fixture-precedence bug, three times in two days.** A test handler that checks its on-disk map
before the per-test override silently ignores the override, and the tests pass for the wrong
reason. Whenever a fixture handler has two sources for one key, check the override first.

---

## What a fresh reader will get wrong

**`make check` does not exercise the forge's storage.** CI has no Postgres, so `test_forge_state.py`
and `test_forge_catalogue.py` skip — 50 skips in a green run. That is why the *rules* live in
`mendel_forge/workflow.py`, pure and always run, and only the storage is in `mendel-api`. To run
the skipped half:

```bash
DB_HOST_PORT=55432 docker compose up -d postgres
export MENDEL_DATABASE_URL=postgresql+psycopg://mendel:mendel@localhost:55432/mendel
cd packages/mendel-api && uv run alembic upgrade head
```

`DB_HOST_PORT` because a developer machine running any other project's Postgres already holds
5432, and `docker compose up` then fails on the bind rather than on anything to do with this
repository.

**The forge's durable state is in `mendel-api` by decision, not by drift.** It was put to the
operator when `models.py` went from four tables to eleven — seven of them the forge's — and the
answer was to keep it there. `models.py`'s discipline is that every table argues for itself in its
own docstring, and that is now carrying eleven arguments. The tables are namespaced `forge_*` and
the services are two files, so a later split stays cheap.

**Nothing has been looked at in a browser.** There is no forge UI on this branch yet; Tasks 10 and
11 build it. Every lesson this repository has recorded about screens — that guards are good at
behaviour and blind to appearance, that reading finds wrong strings and not wrong pictures —
applies unchanged and has not been paid yet.

**`ModuleSpec` is used by the *bundle*, not by the adapters.** A catalogue sync reads sixteen
hundred tools and has no business running a DSL parser over any of them, so a module's shape is
derived once, for the one tool being adapted. `ModuleSpec.of()` is the text entry point beside
`parse()` — one parser for conformance and the forge.

---

## What is next

Task 6 and Task 7: the prompt pack, the proposal renderer, and a separate AI worker on
`arq:queue:ai` with concurrency one.

**Task 6 is where the review chat has to be declared against the egress guard**, and that is the
thing to stop and think about rather than implement. Invariant 14 says pipeline data leaves
through four declared doors; `ForgeMessage.content` is free text written by a curator *and* by a
model, and it goes back to the model on the next turn by design — that is what makes a
conversation a conversation. `tests/guards/test_egress.py` holds `DOORS` literally, so widening
it means editing a test that says *these are all the ways data leaves*. The operator has asked
for the chat and it is in the plan; **what has not been decided is whether it is a fifth door, or
downstream of an existing one, or outside the prompt-taint path the way the forge itself is**
(decided 2026-08-17, `notes/specs/2026-08-17-forge-phase-2.md` §1). Do not widen `DOORS` without
putting that question in front of somebody.

**One gap left as drawn.** The plan's state diagram reaches `archived` only from `review`, so a
permanently failed adaptation — the tool was deleted upstream — is retryable forever and closeable
never. It is implemented as drawn and noted rather than widened, because widening a state machine
is cheap later and narrowing one is not. It is a real hole and it is the operator's call.

**A module testing system comes after the plan**, by the operator's decision. `supplies_tests`
and the `test_result` output hint are what it will key off; nothing more was built for it.

**`assemble.py` and `verify.py` were not rewritten**, and the plan says "refactor" both. Their
rules are measured — a port's name is asked *after* its type because a model answered `gtf` for
one and `genome.index.hisat2` for the other; a hole carries its own port's prose because
`star/align`'s output block buried the instruction. `bundle.derive` bridges to `assemble` through
an `Observation` and re-addresses the result. §0 of the plan says build the new surface beside the
old one, which is the argument, and the deviation is in the execution record either way.
