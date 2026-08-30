# Plan 4 Phase 1 — `publishDir`, and a run that can show you its outputs

> **For agentic workers:** REQUIRED SUB-SKILL: use `superpowers:executing-plans`, driven by the
> operator's own session, task by task. **Do NOT use `subagent-driven-development`** — `CLAUDE.md`
> forbids farming out implementation. Tick each `- [ ]` as it completes, and where a step was
> carried out differently, tick it anyway and record the deviation in the execution table.

**Goal:** a finished run can hand you its outputs. Today it cannot: the emitted pipeline publishes
nothing, so results sit in `work/<hash>/` under names nobody can read, and three separate screens
have been blocked on that fact.

**Architecture:** one directive in `emit_config`, one *site* fact in Wiener's launcher, and one
endpoint that lists a directory Wiener already owns. **Mendel never learns a path** — it emits
`params.outdir = null` and a `publishDir` that reads it, exactly as it already emits
`params.input = null`; Wiener's `site_config()` supplies the value, exactly as it already supplies
`process.resourceLimits`. That parallel is not a convenience, it is the argument: *where the
outputs go* is a fact about a site, and a number in the artifact would make `mendel emit`
non-reproducible across deployments.

**Tech Stack:** Python 3.12 · Jinja2 · FastAPI · Nextflow.

**Design source:** the canvas annotations `impl-reuse`, `ov-blocked` and `rn-blocked`, each of
which names this independently. `rn-blocked` calls it *"the third screen it has blocked"*;
`ov-blocked` calls it *"the cheapest large win available and the move the loop has never had"*.

## Why this is first, and separate

It is backend-only, it is small, and it removes a caveat from both of the phases after it. Doing
it inside the Overview phase would mix a compiler change into a frontend phase — which is exactly
the shape `make verify` exists to catch, and exactly the shape that gets waved through by
`make check`.

## Global constraints

- **`make verify` is REQUIRED**, not `make check`. This phase changes `emit.py`, which
  `CLAUDE.md` names explicitly: *nothing outside `test_counts.py` runs a tool, so a flag that
  stops reaching one is invisible to every other test in the repository.* Budget ~2 minutes and
  Docker.
- **Golden files move.** Every emitted `nextflow.config` gains lines. Read the diff before
  committing it — that is the habit that caught the Jinja `{%- endfor %}` collision.
- **Determinism is a test.** Same `Goal` → byte-identical `.nf`. The new directive is a function
  of nothing except the pipeline, so it must not introduce an unordered set, a timestamp or a
  path. `IREdge.states`' `field_serializer` is the precedent for anything that serialises a set.
- **Invariant 15 is not at risk and say why in the code.** No *input* accepts a path. An emitted
  parameter defaulting to `null` is the same construction `params.input` already uses, and it is
  a placeholder the lab fills at run time. Write that comment where a reader will hit it.
- **`process.resourceLimits` is the precedent to follow literally.** `docs/design/wiener.md`
  §12 and `emit.py`'s own `_label_scope()` comment already state the rule: a cap is a *site* fact
  written by Wiener's launcher, never a number in the artifact. `outdir` is the same kind of fact.
- **`make client` after the route lands.** Never hand-edit `frontend/src/wiener/api/`.
- **Diagnostic codes:** if a refusal is needed, Wiener's band is `MW0001`–`MW0099` and `MW0001`
  and `MW0002` are taken. Declare it in `comeni_core/diagnostics.yml` and run `make docs`.

---

## Pre-execution notes — checked against the code on 2026-08-30

**P1-1 — `publishDir` is genuinely emitted nowhere.** A repository-wide grep returns exactly one
hit, `packages/comeni-core/src/comeni_core/spell/directives.py:54`, where it appears in the list of
directive names a setting is *allowed* to route to. So the vocabulary already permits it and
nothing uses it. That is the good case: no migration, no schema change.

**P1-2 — `emit_config()` takes one parameter and a test holds it there.** `execution-boundary.md`
§6 made the one-parameter signature the guard that stops per-target emission. **Do not add a
second parameter for an output directory.** The directive reads `params.outdir`; the value comes
from outside the artifact entirely.

**P1-3 — the natural home is the `process {` scope, beside the labels.** `_label_scope()`'s own
comment says *"nothing here depends on which steps this pipeline has"*, and neither does this: one
global `publishDir` keyed on `task.process` gives every process a directory named after itself,
which is nf-core's own `modules.config` convention and therefore quotable rather than invented.
A per-`withName` block would be one line per step and would say nothing the global one does not.

**P1-4 — Wiener already owns everything the endpoint needs.** `launcher.work_dir(run_id)` is the
run directory; `launcher.site_config(run)` already writes site facts into it and is already where
`resourceLimits` lives; and the run directory is bind-mounted at the **same absolute path inside
and outside** the container, which `CLAUDE.md` records as load-bearing. So listing published
outputs is a directory walk with no new mount and no new setting.

**P1-5 — the stub and test profiles set `params.*` and will set `outdir` too.** `emit_config`'s
`stub_data` and `test` profiles enumerate `entry_params(pipeline)` and assign each a pattern.
`outdir` is **not** an entry param and must not join that loop — it needs its own default inside
those profiles or a stub run publishes into whatever the working directory happens to be.

---

## Task 1 — the emitted pipeline publishes what it makes

**Deliverable:** `nextflow.config` carries a `publishDir` and an `outdir` parameter; the golden
files record it.

- [ ] Add `outdir = null` to the `params {` block in `emit_config()`, **after** the entry params
      so the entry-param loop stays untouched and the diff is one line in one place.
- [ ] Add a `PUBLISH_DIR` constant beside `RESOURCE_LABELS` in `emit.py`, with a docstring in the
      house style saying: it is a **convention** quoted from nf-core's `modules.config`, not a
      judgement; the directory is derived from `task.process` so it depends on no step; `mode`
      is `copy` because a symlink into a work directory that gets cleaned is a result that
      evaporates; and `params.outdir` is `null` in the artifact because **where outputs go is a
      site fact**, with `process.resourceLimits` named as the precedent.
- [ ] Emit it from `_label_scope()` — the same scope, above the labels, so a reader meets the
      publishing rule before the resource rules.
- [ ] Give `stub_data` and the `test` profile their own `params.outdir` default so a gate run
      publishes somewhere predictable rather than into the process's working directory.
- [ ] Regenerate every golden `nextflow.config`. **Read the diff.** Confirm it is additive, that
      nothing reordered, and that no path appears anywhere in the artifact.
- [ ] Add `test_the_artifact_never_names_an_output_directory` — assert `emit_config` output
      contains `outdir = null` and matches no absolute path. **Watch it fail** by hard-coding a
      default, and record the revert in [`../audits/guard-ledger.md`](../audits/guard-ledger.md).

**Verify:** `make verify`. The counts matrix must still pass — it runs a real tool, and a
misplaced `publishDir` is exactly the kind of change that keeps every unit test green while
breaking the one thing that executes.

---

## Task 2 — a run publishes into its own directory

**Deliverable:** Wiener supplies `outdir`, so a real run's outputs land somewhere Wiener can find
them.

- [ ] In `packages/wiener-api/src/wiener_api/services/launcher.py`, extend `site_config(run)` to
      write `params.outdir` pointing at `work_dir(run_id) / "results"`. It goes beside
      `_resource_limits()` and for the same stated reason — read that function's comment and
      match its argument rather than restating it.
- [ ] Create the directory at launch, next to where `workdir` is created, so a run that publishes
      nothing still has a directory rather than a 404 that reads as a missing run.
- [ ] Add `test_the_launcher_says_where_outputs_go` to `packages/wiener-api/tests/test_launcher.py`
      — assert the written `site.config` names a directory inside the run's own workdir and no
      other. **Watch it fail** by pointing it one level up.

**Verify:** `make check`, plus running one real pipeline end to end. This task is not done on
green tests: the whole point is a directory with files in it, and W1's and W2's lesson is that
five and six defects respectively were found by running it and none by a test written to pass.

---

## Task 3 — `GET /runs/{id}/results`

**Deliverable:** an endpoint that lists what a run published, and says honestly when there is
nothing.

- [ ] Add the route to `packages/wiener-api/src/wiener_api/routes/runs.py`, following the file's
      existing shape — a declared `ResultsOut` model, an `operation_id`, a one-line `summary`.
- [ ] It returns one entry per published file: the process that made it, the relative name, the
      size, the modification time. **Every field comes from the filesystem**; nothing is
      inferred, and nothing resolves anything (the 2026-08-19 audit's rule — no screen may touch
      the registry in a request).
- [ ] **Absent is not zero.** A run that has published nothing yet and a run that published
      nothing at all are different answers, and a run launched before this phase existed is a
      third. Distinguish them in the response rather than returning an empty list for all three
      — `rn-absence`'s rule, and `ProcessRow.reported_resources` is the shape to copy.
- [ ] Enforce `lab_id` the way every other query in `repository.py` does. That file's header
      says a filter you can forget is a leak, and this one hands back filenames.
- [ ] Paginate. A run with 5,000 tasks can publish more files than that, and W2's console was
      bitten by exactly this — it paged once at 200 and nobody noticed, because the largest run
      anybody had was five tasks.
- [ ] Add `test_results_are_scoped_to_a_lab` and `test_an_unpublished_run_is_not_an_empty_run`.
      Watch both fail.
- [ ] `make client` to regenerate `frontend/src/wiener/api/schema.d.ts`.

**Verify:** `make check`, and read the endpoint's answer for the real run from Task 2.

---

## Task 4 — record what changed

- [ ] Update `docs/design/wiener.md` §12 with the `outdir` site fact, beside `resourceLimits`,
      naming this plan and the date.
- [ ] Update `docs/reference/pipeline-schema.md` if `outdir` appears in a `pipeline.yml` — it
      should **not**, and if it does, that is a finding rather than a documentation task. Stop and
      say so.
- [ ] Add a line to `CLAUDE.md`'s current-state section: the emitted pipeline now publishes, and
      the directory is a site fact. Keep it to two sentences — that section is 156 lines because
      of paragraphs that were meant to be two sentences.

---

## Execution record

| Task | Carried out as written? | Deviation |
|---|---|---|
| 1 | | |
| 2 | | |
| 3 | | |
| 4 | | |

## What this phase deliberately does not do

- **No frontend.** Nothing renders results yet. The Overview's *Results ready* block is Phase 2
  and the run page's results view is Phase 5; `ov-blocked` says explicitly to ship the block
  *after* this exists rather than half-working, and this is that ordering being obeyed.
- **No `saveAs` renaming logic.** nf-core's `modules.config` does elaborate per-process renaming.
  A directory per process is the whole of what is quotable; anything cleverer is a judgement
  nobody has made.
- **No cleanup, retention or garbage collection** of published outputs. Real, and not this.
