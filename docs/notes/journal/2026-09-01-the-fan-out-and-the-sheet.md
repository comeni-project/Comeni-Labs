# The fan-out, the sheet, and four things a green suite could not see — Plan 5B, phases 4 to 5

*2026-09-01, later the same day. Four pull requests; the remaining thirty of the plan's seventy
boxes, plus a browser pass that was not in the plan.*

**This is the second entry for 2026-09-01.** Read
[`2026-09-01-a-channel-gets-a-name.md`](2026-09-01-a-channel-gets-a-name.md) first — phases 1 to
3, where a channel stopped being a property of a type. This one closes the defect that entry
carried and adds the samplesheet. The plan and its execution record are
[`../plans/2026-08-31-plan-5b-what-a-pipeline-takes.md`](../plans/2026-08-31-plan-5b-what-a-pipeline-takes.md);
the argument is
[`../specs/2026-08-31-what-a-pipeline-takes.md`](../specs/2026-08-31-what-a-pipeline-takes.md).

---

## What is true now

**The fan-out defect is fixed, and it was reproduced before it was fixed.** The previous entry
warned in bold not to point the spine at real multi-sample data. That warning is now spent: a
`RUN`-scoped channel emits as a **value** channel — `(…).first()` — so a reference is read once
per task rather than consumed once for the whole run. With two sample pairs `STAR_ALIGN` runs
twice.

The guard is a stub run over **two** sample pairs asserting the process ran twice, watched
failing against the old emitter. That shape was chosen in the plan and it earned itself: the
obvious alternative — a determinism test over the spine — passes on a one-sample fixture whether
the bug is there or not, which is the guard-that-proves-nothing this repository has now paid for
three times. `materialise_stub_data` writes `sampleA` and `sampleB` for the same reason; the old
one-pair fixture made N = 1, and N = 1 is what hid the defect.

**`Scope` has exactly two members and the third is refused in writing.** `RUN` and `SAMPLE`. A
`GROUP` — per-batch, per-lane, per-patient — is the one somebody will ask for, and the argument
against adding it now is in the type's own docstring rather than in a plan nobody will reread:
a third member is a grouping *key*, which is a column, which is the samplesheet's problem and
not the scope's.

**An aggregator sees every sample at once.** `cardinality: "*"` reaches the emitter as
`.collect()`, so MULTIQC produces one report rather than N. Fan-in and fan-out are the same
question asked in opposite directions and it would have been easy to answer only one.

**A channel's scope may be overridden, and the override is a decision.** `DraftChannel.scope`
carries a `Why`, because *this GTF is per-sample* is a claim about a laboratory's data that the
registry cannot know and that a reader must be able to challenge. It reaches the IR as
`IRChannel.scope: ResolvedValue | None`.

> **The egress guard refused the first two designs, and both refusals were right.**
> `IRChannel.scope: str` is a bare `str` on a payload — the thing invariant 14 forbids because a
> prompt fits in one. `IRChannel.why: Line` would have been the **fifteenth** free-text field,
> and the guard holds that list literally so that widening the boundary means editing a test
> that says *these are all the ways data leaves*. Reusing `ResolvedValue` costs nothing and adds
> no field: its `reason` and `axis_reason` are already entries 3 and 12.
>
> That is the guard doing the job it was built for, twice, against its own author.

**`params.input` has two meanings and an artifact now says which.** `InputForm` is `DIRECT` or
`SAMPLESHEET`. Two sample-scoped channels cannot both be a glob, so the input becomes a CSV that
`splitCsv(header: true)` parses into one row per sample — and the artifact declares the columns.
Wiener reads them out on upload (`input_shape`), the run sheet asks for a table rather than a
path, and `_materialise_tables` writes the CSV beside the run.
`frontend/src/build/Samplesheet.tsx` is the control.

**A samplesheet pipeline runs end to end under `--gate test`** — real containers, real public
data, `results/star_align/test.Aligned.out.bam`, named for the row's `sample` column, which is
the only place that name could have come from. That is the checkpoint, and `-stub-run` could not
have been it: a stub never reads its inputs, so a column wired to nothing is exactly as green as
one wired correctly. Two modules have already shipped that way.

---

## What was found by running it

**Three defects, and none of them had a test that would have caught it.** The pattern from W1 and
W2 repeating.

**A Groovy expression with a leading `+` truncated its own error message.** The duplicate-id
check printed `samplesheet has duplicate sample ids: ` with **no ids** — the one thing the
message exists to say. `nextflow lint` passed it. A continuation line beginning `+` is parsed as
a unary plus on a new statement rather than a concatenation, so the operand was evaluated and
discarded. The `+` goes at the end of the line now, and the guard runs Nextflow twice: once to
see the message, once to see the ids in it.

**`MD0229` as specified refused every v5 artifact.** Twenty failures including `wiener-core`'s.
The rule was written as *two channels of the same scope*, which is the common and legal case; it
should have been *two channels reading one **parameter***. Caught by running the suite rather
than by reading the rule, which is the honest way to report it.

**The `test` profile is all-or-nothing, and that refusal is correct.** The first attempt at the
end-to-end checkpoint used a prebuilt STAR index; `genome.index.star` declares no `test_data`, so
the emitter refused a `test` profile at all — and the failure read like a samplesheet bug. It is
not. Building the index from a FASTA instead makes every input a public example. A partial test
profile would be worse than none, because it would run.

---

## The browser pass, which was not in the plan

**Four more defects, found by opening the pages.** Three were invisible to a suite that reads
text content — the blind spot Plan 4 phase 6 already recorded — and the fourth was a page that
did not know which run it was.

**A run page did not know which run it was.** `RunState.run_id` is what the *fold* learned from
an event, and it is `""` until the first one lands: every run between launch and its first task,
which is exactly the window somebody watches. `Run.tsx` passed it to every panel, so the overview
asked `/api/runs//overview`, took a 404, and drew it under a header reading `run ` with no id.

> **The tell was inside the same component.** `useTitle` already used the route id, so the
> browser tab said `Run bb22cc33` over a page that did not know. A field that is right in one
> line and wrong eight lines down is what a reviewer reads past.

The guard asserts the **URLs** rather than the rendering, and that is the whole of why it works:
the fixture mock answers any path, so a panel handed an empty id renders perfectly. Only the URL
has a hole in it. Watched failing, and the message names both broken requests —
`/api/runs//series` and `/api/runs//overview`.

**`make dev` served a registry from before Plan 5A, and `dev-refresh` said it had refreshed it.**
Two defects, and the second is worse. The dev clone was made once and never touched again —
`dev-refresh` existed and was not a dependency of `dev` — so every registry change in 5A and 5B
was invisible to the running stack. The symptom was a **blank builder**: a 422 on
`LayerManifest.kinds`, a field A4 had replaced with `layout:`, and the page drew its chrome
around no pipeline at all.

And the refresh reset to `origin/HEAD`, where the clone's origin is the submodule directory,
whose local `main` never moves because the superproject pins a *commit* and leaves the submodule
detached. So it fetched a branch that had not moved in days and printed *"dev registry
refreshed"*.

> That is `make drift` printing "skipped" over twelve edited contracts, in a new place: **a
> success message unconditional on whether anything happened.** It names the two commits now, so
> a refresh that moves nothing says so.

**The run sheet's footer collapsed to one word per line.** `SubmitPanel` expanded inside a
`justify-between` row, so the summary wrapped, Cancel overlapped it, and `lint: passed` fell off
the panel entirely.

**The board's "typical run" tile said "no run has finished" over a table of finished runs.** It
read a missing `p95_ms` as a missing run. Absent p95 and zero terminal runs are different facts.

---

## What a fresh reader will get wrong

**The scope override has no control on the canvas.** `DraftChannel.scope` exists, the resolver
honours it, the artifact records it with its `Why`, and **nothing in the builder sets it** — so
the samplesheet is reachable through the API and not through the browser. The backend half is
done and the front half is not, which is the shape that reads as finished in every test run.

**`run_id` on `RunState` still means what it always meant** and was not changed. It is the id the
*fold* learned, it is correctly empty before the first event, and `wiener-core` has no business
inventing one. What changed is that the page no longer asks it a routing question. The API
returning `run_id: ""` from an endpoint that 404s on an unknown id is still arguably a field that
can only mislead a client — that is a real question and it is **not** closed here, deliberately:
fixing it would have made the frontend guard pass either way.

**The runs screens have still not been checked past the overview.** Chrome's extension dropped
mid-pass. Console, Graph and Tasks were never opened. W2's checkpoints 3 to 6 remain owed and
this pass did not discharge them.

---

## What is next

**Plan 5B is complete** — both repositories, every suite green: `make check` at 1831 passed, the
frontend at 349 passed and 1 skipped, tsc and lint clean.

**The scope control on the canvas** is the smallest thing that turns a working backend into a
usable one, and it is what makes the samplesheet reachable by a person.

**Plan 4 phase 6 Task 6** is still owed: the chrome pass over the builder written up, and the
split/merge control clicked by a person. It has now been unclaimed across three entries, which
is itself worth noticing.

**Finish the runs pass** — Console, Graph and Tasks, against the artboards. On today's evidence
the yield is roughly one defect per screen opened, and every one of them was invisible to a
green suite.
