# Spec — closing round three (Plan 1.11)

**The design authority for Plan 1.11.** It closes the seventeen findings of the
[2026-08-10 round-three audit](../audits/2026-08-10-round-three-audit.md), A38–A54, four of them
critical. Where this spec and the code disagree, this spec wins; where it and the audit disagree,
the audit's *reproduction* wins — a fix that does not defeat the audit's own reproduction is not a
fix.

## What the audit found, in one paragraph

Round three was the first audit of Plan 1.10's surface. Seventeen findings fall into two shapes.
**A guard checks a string's *shape*, not its *content* (A44–A49):** consolidating everything into
one hand-editable `pipeline.yml` widened the set of strings that flow verbatim into generated
Groovy, and two of the marked types validate nothing. **A fact is computed and never carried to
where it is read (A50–A54):** the replay/upgrade/publish boundary computes drift, displacements
and overrides correctly and then drops them between producer and consumer. A38 stands apart: two
of three declared emission routes emit nothing, reopening issue #10 one level down.

## Principles that bind every task

These are not per-finding; they hold across the plan and a task that violates one is wrong even if
its own test passes.

1. **Reproduce, then fix, then re-reproduce.** Each task begins by running the audit's own
   reproduction and watching it misbehave, and ends by running it again and watching it refuse or
   behave. A fix with no failing reproduction beneath it is a hypothesis.
2. **Every restored or added refusal earns a guard-ledger row, reverted and watched.** This is
   A14's closure condition and it is the reason round three exists. A refusal that ships without a
   test that fails when it is removed is exactly the inert guard A14 names — round three found four
   of them. `docs/internal/audits/guard-ledger.md` gets a row per refusal, with the revert watched.
3. **`make verify`, never `make check` alone.** Every task here touches `emit.py`, `cli.py`,
   `pipeline.py`, `resolve.py` or `router.py` — the files `make check` waves through because
   nothing outside `test_counts.py` runs a real tool. `make verify` is the gate for every task.
4. **One finding, one task, one checkpoint.** Seventeen sequential tasks, each verified and paused
   at before the next. Corrections to this spec discovered during execution are recorded in the
   task's commit, as every prior plan in this repository has needed.
5. **Content-validation validates content; it never silently escapes.** Root C's discipline is
   *declare the kind and validate it*. A marked string that reaches generated Groovy is refused
   when malformed, not quietly rewritten — a rewrite hides the author's mistake and a refusal names
   it.

## The decided forks

The audit named a design choice at four findings. These are settled and are not reopened during
execution.

- **A38 — implement both dead routes.** `via: meta` and `via: directive` are wired into `emit.py`
  rather than deleted. The machinery exists (`_with_meta`/`_render_meta` for the meta map,
  `withName` blocks for directives), the enum and both public documentation tables
  (`ARCHITECTURE.md`, `pipeline-schema.md`) already promise them, and a contract that needs a
  directive is an ordinary thing. Deleting the capability to match the emitter would be the wrong
  direction.
- **A46 — `settings[].value` is the single source of truth.** It is the field the schema doc tells
  users to edit and the field `emit` reads. On load, a `value` that differs from what the recorded
  decision would produce **becomes** the `human_override` (source `HUMAN`); a `human_override` that
  contradicts `settings[].value` is a refusal in the `MD02xx` band. `decisions[].human_override`
  stops being independently writable.
- **A50 — `publish` does not re-resolve.** `publish` certifies the artifact on disk: it gates the
  emitted files, stamps the verdict, and re-resolves nothing. It needs no registry and no network,
  exactly as `emit` needs none. The legitimate "I edited my goal and want to publish the result"
  workflow runs through `emit` (which surfaces the edit via `MD0213`) and then `publish`; nothing
  is lost, and the entire class of "publish silently produced something the operator did not read"
  disappears rather than being merely reported. This is more than the audit's minimum one-line gate
  fix, and it is the correct one.
- **A40 — `MD0208` is built as part of A38.** Implementing `via: meta` opens the collision the spec
  originally wrote `MD0208` to refuse (a setting and a `Measurement.meta_key` both claiming one meta
  key; two `ext` settings on one key; two directives on one name). It is refused, not resolved by
  precedence, and it lands in the same task as the route that makes it reachable.

## The seventeen tasks

Ordered criticals-and-security-first, then by shared code so a later task builds on a settled
earlier one. Each row is one task. Severity is the audit's.

### Cluster 1 — content-validation (security)

| # | Finding | Sev | Fix |
|---|---|---|---|
| 1 | **A44** `test_data` reaches `nextflow.config` unescaped, executes at config-parse | crit | Render `test_data` through `_render_literal` (single-quoted, escaped), not raw double-quote wrapping; give `TestDataRef` an `AfterValidator` enforcing the URL-pinned-to-commit shape its docstring promises. Scope the escaping to lab-derived values, not the generated `${projectDir}` stub literals beside them. |
| 2 | **A45** `NfTemplate` validates only newlines; the text around `{value}` injects shell and Groovy | imp | Give `NfTemplate` a grammar: forbid bare `"` and backtick, allow `{value}` and an allowlist of `${meta.<id>}`/`${task.<id>}`, reject any other `${…}` body. Preserves the one real use (`'PL:{value}'`, `${meta.id}`). |

### Cluster 2 — emission routes

| # | Finding | Sev | Fix |
|---|---|---|---|
| 3 | **A38** `via: meta` and `via: directive` are validated, recorded, and emit nothing | crit | Implement both in `emit.py`: meta settings merge into the channel meta map, directive settings emit `withName { <name> = <value> }`. Add a guard asserting every `Via` member emits observable output or is refused. |
| 4 | **A40** two writers for one destination concatenate silently; `MD0208` was never built | imp | Add `MD0208` to `diagnostics.yml` and refuse at load when two settings (or a setting and a measurement) write one meta key, one `ext` key, or one directive. Lands with A38 because A38 makes the meta collision reachable. |
| 5 | **A39** a non-templated `ext` key is `_render_literal`'d twice, carrying literal quotes | imp | Append the raw value in the non-templated branch and let the single `_render_literal` at the join quote it, as the templated branch already does. |

### Cluster 3 — the tier-4 round trip

| # | Finding | Sev | Fix |
|---|---|---|---|
| 6 | **A46** a tier-4 answer has two homes; `emit` and `upgrade` read different ones | crit | `settings[].value` is authoritative (see forks). On load, reconcile: a differing `value` becomes the `human_override`; a contradiction is refused. One writable field. |
| 7 | **A52** a duplicate decision key silently discards a human override (`setdefault`) | imp | Refuse a duplicate decision key at load, as a `Pipeline` validator beside `MD0212` — the `ReplayResolver` docstring already calls a duplicate corruption. |
| 8 | **A47** `mendel emit` silently erases a recorded gate verdict | imp | `stamp(out, pipeline, gate=pipeline.gate)` — carry the verdict through a re-emit that changed nothing. |
| 9 | **A48** a `pipeline.yml` with no `goal:` loads and `upgrade` empties it at exit 0 | imp | Make `Pipeline.goal` a required field; refuse in the upgrade path when re-resolution yields zero steps from a non-empty previous. |
| 10 | **A49** a refused `emit` half-regenerates, then blames the user with `MD0214` | imp | Render both files in memory, then write both — a refusal leaves nothing behind, the posture `upgrade` already takes. |

### Cluster 4 — publish / upgrade / layers

| # | Finding | Sev | Fix |
|---|---|---|---|
| 11 | **A50** `publish` is `upgrade` with every brake removed | crit | `publish` certifies the on-disk artifact and does not re-resolve (see forks): gate the emitted files, stamp, never write in place, no registry. |
| 12 | **A51** rules and vocabulary displacements are recorded at load and dropped | imp | Carry `loaded.displaced` (all four kinds) into the IR/artifact rather than re-deriving from two in `resolve.py:70`; add one artifact-level test per `DeclaredKind`. |
| 13 | **A53** `upgrade --out` protects only the source directory | imp | Refuse `--out` when the target already holds a different `pipeline.yml` (absent `--force`); add relative/`..`/symlink cases to the identity test so `.resolve()` is watched. |
| 14 | **A54** a resolver may claim `source: HUMAN` and empty `needs_review()` | min→imp | Make `HUMAN` non-assertable through the port: derive it from `record.human_override` (the only evidence a human touched anything), or add a `Pipeline` validator requiring every `why.source: human` to have a matching non-null `human_override`. |

### Cluster 5 — diagnostics, tests, docs

| # | Finding | Sev | Fix |
|---|---|---|---|
| 15 | **A41** `MD0200` is published but unemittable; its real failure blames the *goal* | imp | `Param.via`/`Setting.via` are required with no default, so a missing `via:` surfaces today as a raw Pydantic "Field required" wrapped in the wrong noun. **Emit `MD0200`**: catch the missing-`via` case at contract load and raise `MD0200`'s declared message rather than letting Pydantic's error escape — the published code becomes reachable rather than retired, because its helpful text is exactly what the user needs. Separately, correct "this goal is not valid" to name a *contract* when the fault is in one. Touches issue #18's territory but is not its census. |
| 16 | **A42** six live refusals and two byte-identical-emission properties have no test | imp | Add an emission test per untested refusal (`MD0215`, `MD0201` at emit, `MD0204` one-line, the two-settings name-sort, the process-scope dedup) and a guard-ledger row each. The two-settings sort is the one the emitter's own docstring predicted would be missed. |
| 17 | **A43** documentation disagrees with the code in seven places | min | Correct the counts (25 codes, `MD0208` now exists after task 4), the door-4 payload in `clinical-data-protection.md` (`Pipeline`, not `PublishBundle`), the named-but-absent `test_publish_bundle_is_typed`, `CallArg.empty_width`'s omission from the schema doc, and issue #18's stale raise-site numbers. |

## What "done" means

- Every one of the audit's reproductions, re-run, now refuses or behaves.
- `make verify` green after every task.
- Every refusal added or restored has a guard-ledger row with the revert watched.
- No critical finding survives — the fix-then-re-audit loop's exit criterion. A14 closes when the
  ledger has a watched row for every guard in `tests/`, which tasks 3, 4, 6, 7, 9, 11, 13, 14 and 16
  each move toward.
- A round-four audit is still owed: A14's loop exits on *no critical surviving*, not on an empty
  audit, and this plan adds a large surface of its own. The narrowed-scope passes round three did
  not run (`test_purity.py`, `test_purity_runtime.py`, invariant 11's four-kind stacking) and A36
  remain for it.

## Out of scope, deliberately

- **Issue #18's full error-surface typing** (`MD0300`–`MD0399`, 79 raise sites). Task 15 touches its
  edge — `MD0200` and one misattributed message — but the census is its own plan.
- **The `sealed` tier-4 block** (issue #2, Plan 2's `ProfilePolicy`). A54 makes `HUMAN` honest so
  that block can trust it later; it does not build the block.
- **Anything AI-shaped.** Plan 1.11 stays in the pure packages; no new dependency, no network.
