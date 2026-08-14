# The guard ledger

**Append-only.** One row per guard, recording the day someone broke the code it watches and
watched it fail. A guard with no row here has not been shown to be able to fail, and a guard
that cannot fail is indistinguishable from one that works.

This file is [A14](2026-08-06-plan-1-to-1.7-audit.md)'s closure condition. A14 is critical and
open until every guard in `tests/` has a row — not every *test*: a guard is a test whose purpose
is to refuse something. Four instances were found in one day; the fifth, sixth and seventh were
found while writing the plan that closes them, which is why the rule is now in force from task
one of Plan 1.9 rather than scheduled as its last part.

**How to add a row.** Break the code under test — the smallest edit that reintroduces the defect,
not a deleted line of the test — run the guard, and paste what you saw. Then restore, and re-run.
Three questions have to be answered, in this order:

1. **Did it fail?** If not, the guard is inert. That is a finding, not a fix.
2. **Does the message name the defect?** A `KeyError` deep in a helper is a fail, not a pass:
   the next reader has to be led to the thing that broke.
3. **Did the revert reach the code the guard names?** A17's first reproduction landed in a
   function the runtime guard never calls, so the guard reported green about a probe that had
   never executed.

| date | guard | what was reverted | what happened | message |
|---|---|---|---|---|

## Round two, 2026-08-07 — seeded from the audit

Recorded by the two round-two reviewers under
[the brief](2026-08-07-round-two-brief.md). These are summarised from
[the audit's *Clean — attacked and held*](2026-08-07-round-two-audit.md) section rather than
re-run, and are marked as such: they are inherited evidence, not evidence this ledger watched.

| date | guard | what was reverted | what happened | message |
|---|---|---|---|---|
| 2026-08-07 | `test_audit_regressions.py` A3 | the path-shaped parameter refusal | 7 parametrised failures | names the value and the field |
| 2026-08-07 | `test_audit_regressions.py` A5 / A15 (`param:`) | the overlay displacement record | failed | names both layers |
| 2026-08-07 | `test_ports.py` A8 | `_PicksLast` / `_PicksFirst` port choice | failed under both fixtures | the two-fixture design is correct |
| 2026-08-07 | `test_audit_regressions.py` A9 | the symlink refusal in `layers.load` | failed | names the link |
| 2026-08-07 | `test_audit_regressions.py` A10 | contract `extra="forbid"` | failed | names the key |
| 2026-08-07 | `test_audit_regressions.py` A11 | the duplicate-param refusal | failed | names the param |
| 2026-08-07 | `test_registry_drift.py` (`8dbde51`) | the drift comparison | failed | the former A14 instance, now able to fail |
| 2026-08-07 | `test_generated_types.py` | `.pyi` completeness | failed | names the missing symbol |
| 2026-08-07 | `test_conformance.py` M0101 | the process-name check | failed | names the contract |
| 2026-08-07 | `test_resolve.py`, `test_router.py` | invariant 8's tie handling | 7 failures across two files | names the tie |
| 2026-08-07 | `test_purity.py` | a plain `import socket` in a pure package | failed | names the file and the import |
| 2026-08-07 | `test_digest.py` forgery | `_hex(name.encode())` → `name` | **12 passed** | **inert — this is A21**, closed by Part F |

## Plan 1.9

| date | guard | what was reverted | what happened | message |
|---|---|---|---|---|
| 2026-08-07 | `test_egress.py` positive leaf rule (A2) | nine probes added one at a time to a real payload | each failed | see Plan 1.9 Task A2 |
| 2026-08-07 | `test_purity.py` / `test_purity_runtime.py` (A3) | `ctypes` removed from the banlist and the watch list | both failed, naming the file | the first reproduction landed in `entry_params()`, which the runtime guard never calls — **3 passed** on a probe that had never run |
| 2026-08-07 | `test_layered.py` (B1) | `min(origin[k] …)` → `max` in `DELETE_GROUP` | **nothing failed** | the reduction can never differ; it is now an assertion |
| 2026-08-07 | `test_audit_regressions.py` A23 | `stack()` stops recording displacement for a replaced key | failed | `assert [] == [('strandedness', 'lab-registry', 'comeni-registry-examples')]` — names the key and both layers |
| 2026-08-07 | `test_audit_regressions.py` A23 (single layer) | `stack()` records a displacement for every arriving key | failed | `Left contains 4 more items, first extra item: Displacement(kind=MEASUREMENTS, key='n_samples', winning_layer='comeni-registry-examples', displaced_layer='comeni-registry-examples')` — a layer displacing itself reads as absurd, which is the point |
| 2026-08-07 | `stack()`'s `origin[key] != layer.index` | dropped the condition | **nothing failed** | it can never be false — a repeat inside one layer raises first. Now an assertion, like the `min`/`max` above |
| 2026-08-07 | `test_audit_regressions.py` A24 | vocabulary displacements never reach `Layers.displaced` | failed | `assert [] == [('fastq.reads', 'lab-registry', 'comeni-registry-examples')]` |
| 2026-08-07 | `test_audit_regressions.py` A35 (`add_states`) | the merge replaces the state set instead of extending it | failed | the A35 blame message itself fired — `layer 'lab-registry' replaced the declared states of 'fastq.reads'` |
| 2026-08-07 | `test_audit_regressions.py` A35 (blame) | `layers.load` re-raises `UnknownStateError` unjoined | failed | `assert 'lab-registry' in "'trimmed' is not a declared state for 'fastq.reads'; allowed: ['phix_removed']"` — which is the misdirection, verbatim |
| 2026-08-07 | `test_audit_regressions.py` A25 | — (new guard) | failed before the fix | `AttributeError: 'PipelineIR' object has no attribute 'displaced'` |
| 2026-08-07 | `test_lockfile.py` layer drift | positional layer comparison → compare the name *sets* | failed | `assert any("layer stack changed" ...)` against `['layer lab has changed…', 'layer comeni-registry-examples has changed…']` — it reports drift, but the wrong drift, which is what a name-keyed comparison always does |
| 2026-08-07 | `test_audit_regressions.py` A22 | `router.route` builds the step from `registry.layer_of` instead of the pin | failed | `assert 'comeni-registry-examples' == 'lab-registry'` — the artifact asserting the opposite of what happened, which is A22 verbatim |
| 2026-08-07 | `test_audit_regressions.py` A22 (the type) | `RouteStep.from_layer` gets its `= None` default back | failed | `DID NOT RAISE ValidationError` — the guard is the type; without a test the revert would have been invisible, since the one existing call site passes the field |
| 2026-08-07 | `test_audit_regressions.py` A26 (`.yaml`, nested) | `_files` back to `glob("*.yml")`, one level | failed, 5 tests | **message quality: poor.** `RuleValidationError: No contract declares a parameter named 'seq_platform'. Parameters that do exist: (none)` — a cascade three steps from the cause. `test_layered.py`'s own `test_files_are_found_recursively_and_yaml_counts` names it exactly, which is why the mechanism has its own tests |
| 2026-08-07 | `test_audit_regressions.py` A26 (residue) | `_every_file_is_claimed` skips every file | failed | `DID NOT RAISE ValueError` |
| 2026-08-07 | `test_marks.py` identifier | `isascii()` dropped from `_is_identifier` | **nothing failed on the first pass** | the narrowing was untested *and* unjustified; both fixed — two unicode cases added, and the docstring now says the refusal is deliberate rather than a claim about Groovy, which does allow them |
| 2026-08-07 | `test_marks.py` `Line` | `AfterValidator(_single_line)` removed | failed | `DID NOT RAISE ValidationError` on `"a\nprintln 'x'"` |
| 2026-08-07 | `test_audit_regressions.py` A34 (`nf_process`) | — (new guard: the field was a bare `str`) | failed before the fix | `DID NOT RAISE ValidationError` — reproduced first as an emitted `main.nf` carrying `println 'OWNED'` in the `include` and `process` blocks |
| 2026-08-07 | `test_audit_regressions.py` A27 (`_render_comment`) | the emitter passes `reason` through unrendered | failed | the smuggled line comes out as `println 'OWNED'` rather than `// println 'OWNED'` |
| 2026-08-07 | `test_audit_regressions.py` A27 (config) | `_render_process_name` accepts anything | failed | `DID NOT RAISE ValueError` |
| 2026-08-07 | `test_publish.py` A28 (`emitted`) | — (new field) | failed before the fix | `KeyError: 'emitted'` — the bundle carried no artifact at all |
| 2026-08-07 | `test_upgrade.py` A28 (verdict) | the verdict comes from `diff_ir` again | failed, 4 tests | including `assert 'the generated pipeline differs: nextflow.config' in '…'` on an `ext_args` edit the diff cannot see — A28 verbatim |
| 2026-08-07 | `test_upgrade.py` A28 (`emitted: None`) | `None` treated as "compare anyway" | failed | the bundle predating the record claimed identity, which is the `gate: None` distinction reopened |
| 2026-08-07 | `test_audit_regressions.py` A29 | `resolve()` stops calling `_declared_types` | failed, 3 tests | `DID NOT RAISE UnknownTypeError` — including through `mendel upgrade`, the verb whose goal comes from a stranger's bundle |
| 2026-08-07 | `test_audit_regressions.py` A16 (`EdgeRef`) | `AfterValidator(_edge_ref)` dropped | failed | `DID NOT RAISE ValidationError` on `PT-4471023.fastq.gz` as a source decision |
| 2026-08-07 | `test_audit_regressions.py` A16 (`ContractId`) | `AfterValidator(_contract_id)` dropped | failed | `DID NOT RAISE ValidationError` on `not-a-contract` as a producer decision |
| 2026-08-07 | `test_construction.py` A18 | the probe A18 was found with — `from … import DataProfile as _DP; _DP.model_construct(...)` in `resolve.py` | failed | `these construct one directly: packages/mendel-resolver/src/mendel_resolver/resolve.py:314` — names the file and the line |

## Part F — does the guard call its subject, or restate it?

One question per guard, asked of the fixture rather than of the assertion: **does the test
build its inputs by calling the code under test, or by writing down what that code does?**
A test that restates its subject is guarding its own copy of it, and the copy does not move
when the original does.

| guard | fixture built by | verdict |
|---|---|---|
| `test_digest.py` forgery | **restating** the entry format, twice over — the name half *and* the `_FILE`-tagged content half | **A21.** Fixed: `entry_hash` and `content_hash` are public and the forgery is built through both |
| `test_digest.py` the rest | calling `digest_of` / `digest_of_directory` and comparing two runs | calls its subject |
| `test_lockfile.py` | `Lockfile.of(...)` on a real resolved IR; drift asserted through `drift_against` | calls its subject |
| `test_registry_drift.py` | runs `tools/check_registry_drift.py` as a subprocess against two real trees | calls its subject — the strongest form here, since it is the tool itself |
| `test_generated_types.py` | runs `tools/generate_types.py --check`, and reads the *module's* public surface with `dir()` to assert completeness | calls its subject twice over |
| `test_conformance.py` | mutates real contracts and vendored modules, then calls `check()` | calls its subject |

Only the digest test restated anything, and it was the one already known to be inert. No
new findings above A36 from this sweep — recorded because a sweep that finds nothing is
only worth having if it says what it looked at.

| date | guard | what was reverted | what happened | message |
|---|---|---|---|---|
| 2026-08-07 | `test_digest.py` forgery (rewritten) | `_hex(name.encode())` → `name`, the A9-era fix | **12 passed** before the rewrite; **fails** after | `assert 'sha256:2396…' != 'sha256:2396…'` — the two digests are visibly identical, which is the finding stated as an assertion |
| 2026-08-07 | `digest.py` `_FILE` | `b"file\x00"` → `b""` | **nothing failed, 436 passed** | **new finding, recorded as A36** — a domain separator between one entry kind and nothing |
| 2026-08-07 | `test_audit_regressions.py` A31 | `_StrictLoader` stops noticing a repeated key | failed | `DID NOT RAISE DuplicateKeyError` on a contract carrying `priority: 0` and `priority: 999` |
| 2026-08-07 | `test_audit_regressions.py` A32 | `Ambiguity`'s `model_config` removed — the state it was found in | failed, 2 tests | `DID NOT RAISE ValidationError` on `extra=1`; the projection test failed alongside it |
| 2026-08-07 | `test_egress.py` projection totality | `type_id`/`required` removed from `AmbiguityRequest` | failed | `SourceAsked.type_id has nowhere to go in AmbiguityRequest, so a model behind door 2 would never be told it` |
| 2026-08-07 | `test_audit_regressions.py` A33 | `_choose`'s tier-4 reason back to `chosen by id order` | failed | `'chosen by id order' is contained here: re@0.6.10; chosen by id order` — **and the first version of this test asserted over an empty loop**, which is recorded in its docstring |

## Part I — the residue

Every test file with no row above, swept by reverting one guard in the code it watches. Nine
of ten probes failed loudly; the tenth is **A37**.

| date | guard | what was reverted | what happened | message |
|---|---|---|---|---|
| 2026-08-07 | `test_emit.py`, `test_runnable.py` | `_render_literal` stops escaping quotes and backslashes | 2 failed | `test_a_quote_in_a_value_does_not_break_or_escape_the_literal` |
| 2026-08-07 | `test_emit.py` | `_channel_name` stops replacing `.` and `-` | 3 failed | names the workflow block that stopped wiring |
| 2026-08-07 | `test_contract.py`, `test_alternatives.py` | `ModuleContract.load` skips `check_against(vocab)` | 2 failed | `test_rejects_contract_using_undeclared_state` |
| 2026-08-07 | `test_vocabulary.py` | `validate` accepts every state | 1 failed | `test_validate_rejects_undeclared_state` |
| 2026-08-07 | `test_measurement.py`, `test_profile.py`, `test_profiling.py` | `check` accepts every enum value | 2 failed | `test_an_enum_accepts_only_its_declared_values` |
| 2026-08-07 | `test_replay.py` | `_still_applies` always true | 3 failed | `test_a_record_whose_candidates_changed_is_not_replayed` |
| 2026-08-07 | `test_port_alternatives.py` | only the first alternative is tried | 3 failed | `test_the_second_alternative_routes_when_the_first_cannot` |
| 2026-08-07 | `test_ir.py`, `test_resolution_applies.py` | `needs_review()` returns `[]` | 2 failed | `test_needs_review_lists_only_required_items` |
| 2026-08-07 | `test_lockfile.py` | `layer_name` ignores the manifest | 1 failed | `test_two_layers_sharing_a_name_do_not_collapse` — note `test_registry_layer.py` did *not* catch it; the row is honest about which file did |
| 2026-08-07 | `test_registry.py`, `test_pinning.py` | `producers_of` drops priority from its key | **nothing failed — 441 passed** | **A37.** The fixture's higher-priority contract also sorted first by id, so the two orderings agreed. Fixture fixed; the revert now fails two tests |

**Still without a row**, and honestly so: `test_counts.py` (the slow lane — reverting inside
it means a Docker run per probe, and it is the only test of the v1 criterion, so it is the
one place where "watched failing" costs minutes rather than seconds), `test_end_to_end.py`,
`test_conformance_cli.py`, `test_goal_location.py`, `test_ir_profile.py`, `test_modulespec.py`,
`test_spine_contracts.py`, `test_rules.py`, `test_gates.py`, `test_measurement_types.py`,
`test_ir_provenance.py`. Several of these were exercised incidentally by probes above —
`test_end_to_end` and `test_runnable` fail under most of them — but *incidentally* is not
*recorded*, and this ledger's whole point is the difference.

**A14 therefore does not close with Plan 1.9.** Saying so is the same call Plan 1.8 made and
it was right then too.

## Plan 1.10 — the pipeline file

Not a sweep. These are guards that were **watched failing in the ordinary course of the
work**, which is the cheapest kind of row to earn and the kind this ledger most wants: no
probe was written, the change itself broke them.

| date | guard | what broke it | what happened | message |
|---|---|---|---|---|
| 2026-08-09 | `test_diagnostics_registry.py` | a row hand-edited in `docs/reference/cli.md` | 1 failed | `test_the_generated_table_is_current` (Task 2, recorded then) |
| 2026-08-09 | `test_egress.py` | a bare `user_note: str` planted two levels down inside `EmittedFile` | 1 failed | `test_no_payload_carries_an_undeclared_string` (Task 4) |
| 2026-08-09 | `test_construction.py` | `_DP` / `_P` aliased constructions in a pure package | 2 failed | both sole-constructor tests (Task 4) |
| 2026-08-09 | `test_construction.py` | `Pipeline(version=1)` added to `pipeline_file.py`, the file whose `model_validate` is exempted | 1 failed, naming the line | the exemption is per **spelling**, not per file, so the narrowed allowlist still bites |
| 2026-08-09 | `test_audit_regressions.py` (A11) | `Step`'s `MD0212` duplicate-setting validator landing | 1 failed | A11's own fixture builds the duplicate the validator now refuses — the guard was retargeted, from *the emitter survives one* to *one cannot be constructed* |

### A guard that passed for the wrong reason

`test_a27_prose_reaching_the_pipeline_file_is_refused_at_materialisation`, written this task,
passed on its first run and should not have. It smuggled a multi-line `reason` through a
binding on `nf-core/samtools/sort`, which declares `params: []` — so `_settings` dropped the
binding before `Why` ever saw the prose. Nothing was being tested.

Two things came out of it. The test now uses a contract that declares a param, and the reason
it passed is itself a finding: **`_settings` drops a binding whose contract declares no such
param, silently.** That is recorded at the site and left to Task 9, whose subject is exactly
this one level up.

It is the same shape as A21 — a guard that restates its subject instead of calling it — and it
is the argument for this ledger existing: a green test says nothing until somebody has seen it
red.

### Task 7 — the slow lane earns a row

`test_counts.py` has been in the residue list since Plan 1.9, on the honest ground that
reverting inside it costs a Docker run per probe. Task 7 paid it once.

| date | guard | what was reverted | what happened | message |
|---|---|---|---|---|
| 2026-08-09 | `test_counts.py` | `featurecounts`' `min_mqs` route removed — `params: []` restored | 1 failed, ~40s | `test_a_resolved_setting_reaches_the_tool`, printing the whole command line: `featureCounts \` with an empty `${args}` |

Reverting the **route** rather than the assertion is the point. Changing `-Q 0` to `-Q 9`
would prove only that the string comparison runs; removing the contract's route proves the
guard watches the mechanism it names. That distinction is A21 in one sentence.

The two older rows in this file remain unearned — `test_the_spine_produces_a_counts_matrix`
and `test_featurecounts_ran_with_the_strandedness_that_was_measured` were not individually
probed, and this row does not cover them.

### Task 8 — three probes, and a mechanism that was never watched at all

| date | guard | what was reverted | what happened | message |
|---|---|---|---|---|
| 2026-08-09 | `test_audit_regressions.py` | `_still_open` drops the `source is not HUMAN` clause | 1 failed | `test_an_answered_setting_leaves_needs_review_and_appears_in_overrides` |
| 2026-08-09 | `test_audit_regressions.py` | `_still_applies` restores the membership check on a `[None]` domain | **4 failed** | starting with `test_a_human_override_on_a_parameter_is_replayed_at_all` |
| 2026-08-09 | `test_audit_regressions.py` | an override collapsed to `Tier.STRUCTURAL` — the *wrong* fix, not the absent one | 2 failed | `test_an_override_keeps_the_tier_it_displaced`, naming the tier |

The third probe is the one worth copying. Reverting a fix asks "does the guard notice it is
gone"; applying the **plausible wrong fix instead** asks "does the guard notice it is wrong",
which is the question a reviewer actually has. Collapsing a human override to tier 1 is what
a reasonable person would write, and it fails here for a stated reason.

### The mechanism nobody had watched

`human_override` on a parameter had never worked. `ReplayResolver._still_applies` checked
membership in a candidate list that is literally `[None]` for parameters, so every override
was discarded, counted as newly asked, and the answer thrown away.

Nothing caught it because every existing replay test used producers or sources, which have
real candidate lists. The parameter case had unit tests for `_chosen`, for `_still_applies`,
and for the record type — and none for the one path that carries a person's answer to a
parameter end to end. **Coverage of the parts is not coverage of the path**, which is the
same lesson as A8: a `DecisionRecord` can state a choice the pipeline did not make, and only
a test that follows the value all the way sees it.

### Task 9 — and a rule that shipped inert

| date | guard | what was reverted | what happened | message |
|---|---|---|---|---|
| 2026-08-09 | `test_replay.py` | `stale` merged back into `fresh` | 5 failed | including the pre-existing `test_a_record_whose_candidates_changed_is_not_replayed`, which had been asserting the merge |
| 2026-08-09 | `test_upgrade.py` | `MD0203` downgraded from a refusal to a warning | 2 failed | `test_an_orphaned_override_refuses_and_names_the_code` |
| 2026-08-09 | `test_audit_regressions.py` | `MD0216` back to a silent drop | **nothing failed — 523 passed** | see below |

**`MD0216` shipped inert, and the probe is the only reason anyone knows.** The refusal was
written, `make verify` was green, and reverting it broke nothing at all: no test covered the
rule. A guard was then written, the probe repeated, and it fails now.

This is A14's finding arriving on the same afternoon as A14's ledger row, in code written by
whoever wrote the row. It is worth recording plainly rather than quietly fixing, because the
lesson is not "remember to write a test" — the rule *had* tests around it, three files of them,
and 523 passed over a change that removed it. The lesson is that **green is not evidence**, and
the only thing that distinguishes a guard from a decoration is somebody having seen it red.

**Two tests that passed for the wrong reason, both found by `MD0216` itself.** Both A27 tests
hung their smuggled value on a `nf-core/samtools/sort` binding, and that contract declares
`params: []` — so the value was dropped before anything looked at it, and neither test asserted
what its name said. `MD0216` refusing is what surfaced them: the fixtures started failing, and
the reason they failed was that they had never worked. A guard catching *another test* is the
cheapest audit there is.

### Task 10 — four probes on the verb surface

| date | guard | what was reverted | what happened | message |
|---|---|---|---|---|
| 2026-08-09 | `test_upgrade.py` | `_frozen_against_moved_contracts` returns `[]` | 1 failed | `test_a_replayed_value_frozen_against_a_moved_contract_is_reported` |
| 2026-08-09 | `test_upgrade.py` | `--dry-run`'s early return removed, so it writes | 4 failed | starting with `test_dry_run_writes_nothing` |
| 2026-08-09 | `test_upgrade.py` | the in-place refusal on `upgrade --out` removed | 1 failed | `test_upgrade_refuses_to_write_into_the_directory_it_read` |
| 2026-08-09 | `test_publish.py` | `_refuse_a_divergent_directory` removed from `upgrade` and `publish` | 2 failed | both `MD0213` and `MD0214` on the door with no undo |

`test_publish.py` and `test_upgrade.py` were both in the residue list; both have rows now.

### Task 11 — the egress guard was not watching the door it was given

| date | guard | what was reverted | what happened | message |
|---|---|---|---|---|
| 2026-08-09 | `test_egress.py` | roots collected from `vars(egress)` again, not `DOORS` | 2 failed | `test_every_door_is_walked_by_the_checks_below`, naming the door |
| 2026-08-09 | `test_conformance_cli.py` | `_dead_ext_routes` removed from the check | 1 failed | `test_md0108_a_prefix_route_on_a_module_that_ignores_it_is_refused` |
| 2026-08-09 | `test_egress.py` | `Pipeline` back to a plain `BaseModel` | 2 failed | `test_the_publication_payload_is_frozen` |

**The first row is the finding, not the probe.** `_payload_types()` had always collected its
roots by scanning `vars(egress)` for `EgressPayload` subclasses. That was correct while every
payload lived in that module, and it silently stopped being correct the moment the publication
payload moved to `comeni_core.pipeline`: the guard walked three doors out of four, and the one
it dropped was the door with no undo. Ten tests passed.

Nothing was leaked — the payload had only just been swapped — but the shape is the one this
ledger exists for. A guard that derives its subject from *where a type happens to live* rather
than from *the declaration of what it guards* stops guarding without failing. The roots come
from `DOORS` now, and a new test asserts every door is in the walked set, so the same move
cannot be silent twice.

With the guard actually looking it immediately found four undeclared `str` fields on the new
payload. That is the cost of the hole stated precisely: not a leak, but four fields that had
crossed into the payload without anyone examining them.

## Round three, 2026-08-10 — the first sweep over Plan 1.10's surface

Run under [the round-two brief](2026-08-07-round-two-brief.md), narrowed by the operator to clean
code and documentation-against-behaviour. Every row is a **real removal of the condition**
followed by the full fast suite (`pytest -m "not slow"`), then restore. Findings are
[A38–A43](2026-08-10-round-three-audit.md).

Rows that caught, and named the right thing:

| date | guard | what was reverted | what happened | message |
|---|---|---|---|---|
| 2026-08-10 | `test_audit_regressions.py` | `MD0216`'s orphaned-setting refusal | 1 failed | `test_a_binding_with_no_declared_param_refuses_instead_of_vanishing` |
| 2026-08-10 | `test_audit_regressions.py` | `MD0212` duplicate setting on a step | 1 failed | `test_a11_a_duplicate_binding_is_refused_before_it_can_reach_a_compare` |
| 2026-08-10 | `test_pipeline_file.py` | `MD0212` duplicate **step id** (the other half) | 1 failed | `test_two_steps_sharing_an_id_are_refused` |
| 2026-08-10 | `test_pipeline_file.py` | `MD0207` version refusal | 1 failed | `test_a_newer_version_is_refused` |
| 2026-08-10 | `test_pipeline_file.py` | `MD0211` channel params vs expression | 1 failed | `test_channel_params_disagreeing_with_its_expression_is_refused` |
| 2026-08-10 | `test_routes.py` | `MD0204` template must mention `{value}` | 2 failed | `test_a_template_must_mention_the_value` |
| 2026-08-10 | `test_routes.py` | `MD0204` template forbidden off composing routes | 1 failed | `test_a_template_is_illegal_where_the_route_takes_one_value` |
| 2026-08-10 | `test_routes.py` | `MD0205` `via: ext` without a key | 1 failed | `test_ext_requires_a_key` |
| 2026-08-10 | `test_routes.py` | `MD0205` key on a non-`ext` route | 1 failed | `test_a_key_on_a_non_ext_route_is_refused` |
| 2026-08-10 | `test_routes.py` | `MD0209` illegal directive name | 2 failed | `test_an_unknown_directive_is_refused` |
| 2026-08-10 | `test_runnable.py` | `_render_literal`'s Groovy quote escaping | 1 failed | `test_ext_args_is_escaped_like_any_other_literal` |

Rows that **stayed green** — these are [A42](2026-08-10-round-three-audit.md), and they are a
different shape from A14's inert guard. In each the refusal is **live and correct**; there is
simply no test over it, so a deletion is invisible.

| date | guard | what was reverted | what happened | message |
|---|---|---|---|---|
| 2026-08-10 | *(none)* | `MD0215` — input names exactly one of `source`/`channel` | **542 passed** | — |
| 2026-08-10 | *(none)* | `MD0201` — substitutable-class refusal in `emit` | **542 passed** | — |
| 2026-08-10 | *(none)* | `MD0204` — a template is one line (`marks.py`) | **542 passed** | — |
| 2026-08-10 | *(none)* | `ext.args` fragments name-sorted (`emit.py:226`) | **542 passed** | — |
| 2026-08-10 | *(none)* | process scope `sorted(set(blocks))` (`emit.py:279`) | **542 passed** | — |

**The last two rows are the ones to read.** `_ext_scope`'s docstring predicts exactly this —
*"With one setting that sort is unobservable, which is exactly why a test carrying one cannot see
a sort bug — and byte-identical emission depends on it"* — and no test with two settings on one
step was ever written. Invariant 10 rests on an ordering the suite cannot observe.

**A probe of mine was invalid and is recorded rather than deleted.** The first `MD0207` attempt
changed the message from `MD0207:` to `MD0207x:` and stayed green, and I nearly filed it. The
refusal is guarded; the probe was wrong, because `test_a_newer_version_is_refused` asserts
`"MD0207" in err` and `MD0207x` contains that substring. The transferable lesson is question 3 in
this file's own instructions — *did the revert reach the code the guard names* — and the smaller
one is that **a substring assertion on a diagnostic code does not pin the code**.

### Round three, second sweep — the replay/upgrade/publish boundary (A50–A54)

Two more inert guards, both found by the third cold reviewer and re-run here. Both are the
producer-with-no-consumer shape: the fix they attest to exists, but nothing observes its removal.

| date | guard | what was reverted | what happened | message |
|---|---|---|---|---|
| 2026-08-10 | *(none)* | `resolve.py:70` — drop `*measurements.displaced` (the A23 fix) | **542 passed** | — |
| 2026-08-10 | *(none)* | `cli.py:187` — `args.out.resolve()` → plain `==` (the A53 guard's real work) | **542 passed** | — |

The first is A51: `layers.load()` records displacements for all four kinds and `resolve()` reads
two, so the A23 fix can be undone with a green suite — its tests assert on `load().displaced` and
never on the artifact. The second is A53: the "never in place" guard's `.resolve()` is doing all
the work and no test exercises a second spelling of the same path.

**Not added as a normal caught row, but recorded:** `_still_applies`'s `[None]` special case *is*
guarded — reverting it fails five replay tests. That is the parameter-override fix from Plan 1.10,
and it is the one piece of this subsystem with a guard that watches its subject.

## Plan 1.11 — closing round three (A44–A54 fixes)

Each refusal added by the fixing plan, reverted and watched failing before the fix was committed.

### A44 — test_data escaped and validated

| date | guard | what was reverted | what happened | message |
|---|---|---|---|---|
| 2026-08-10 | `test_emit.py` | `_render_test_data` back to raw double-quote | 1 failed | `test_render_test_data_escapes_like_a_literal` |
| 2026-08-10 | `test_marks.py` | dropped the `_test_data_ref` validator | 5 failed | `test_test_data_ref_rejects_an_injection[...]` |

**Trap recorded, again.** `git checkout <file>` to restore after the probe reverted the
*uncommitted fix*, not just the probe — exactly the 2026-08-08 journal warning. Re-applied by
edit. Use a script that restores only the probed lines, or commit the fix before probing.

### A45 — NfTemplate grammar

| date | guard | what was reverted | what happened | message |
|---|---|---|---|---|
| 2026-08-10 | `test_marks.py` | grammar neutered to the old newline-only check | 6 failed | `test_nf_template_rejects_injection[...]` |

Restored from memory, not `git checkout` (the A44 trap). The residue char-class and the
`${meta.x}`/`${task.x}` interpolation check are one guard; reverting either alone would leave
the other catching a subset, so both were removed together and all six injection shapes returned.

### A38 — via: meta and via: directive emit

| date | guard | what was reverted | what happened | message |
|---|---|---|---|---|
| 2026-08-10 | `test_pipeline_file.py` | `_directive_scope` skips every setting | 1 failed | `test_via_directive_reaches_nextflow_config` |
| 2026-08-10 | `test_pipeline_file.py` | `_meta_injection` not applied in `_calls` | 1 failed | `test_via_meta_reaches_the_channel_meta_map` |
| 2026-08-10 | `test_emit.py` | completeness set narrowed to `{Via.EXT}` | 1 failed | `test_every_via_member_emits_or_is_refused` |

The emitted Groovy was validated in real Nextflow 25.10.4, not only asserted: `nextflow config
-profile test` parses the directive block (exit 0) and `nextflow lint` accepts the meta-injection
`main.nf`. The completeness guard's honest probe is a *missing* member (`{Via.EXT}`), not
`set(Via)` — the latter is tautological and stays green.

### A40 — MD0208, two writers for one destination

| date | guard | what was reverted | what happened | message |
|---|---|---|---|---|
| 2026-08-10 | `test_pipeline_file.py` | `Step._no_two_writers_for_one_destination` disabled | 1 failed | `test_two_ext_settings_on_one_prefix_are_refused` |
| 2026-08-10 | `test_pipeline_file.py` | Pipeline meta-vs-measurement check disabled | 1 failed | `test_a_meta_setting_shadowing_a_measurement_is_refused` |

Two halves, one code. The ext half is A40's reproduction (two settings on `prefix`); the meta
half is the collision the spec named and Task 3 (A38) made reachable. The meta check is a
conservative global over-approximation — any measurement key present collides with a meta setting
of that name, no dataflow trace — because a false rename is cheaper than a silent overwrite of a
measured fact. A `test_two_ext_args_settings_still_compose` companion asserts the `args` family is
exempt, so the fix does not break composition.

### A46 — one writable home for a tier-4 answer

| date | guard | what was reverted | what happened | message |
|---|---|---|---|---|
| 2026-08-10 | `test_pipeline_file.py` | MD0218 contradiction refusal disabled | 1 failed | `test_value_and_human_override_may_not_contradict` |
| 2026-08-10 | `test_pipeline_file.py` | upgrade back to `previous.decisions` (not `replayable_decisions()`) | 1 failed | `test_editing_the_value_answers_for_emit_and_upgrade` |

Two halves. `settings[].value` is the single writable answer: the refusal (MD0218) rejects a
stored `human_override` that contradicts it, and `replayable_decisions()` derives the override
from the value so `upgrade` replays the same answer `emit` already reads. The sync fires only
where the value differs from the resolver's `chosen`, so a resolver's (or a future model's) own
answer keeps its review flag rather than being relabelled HUMAN.

### A52 — a duplicate decision key is refused

| date | guard | what was reverted | what happened | message |
|---|---|---|---|---|
| 2026-08-10 | `test_pipeline_file.py` | MD0219 duplicate-decision-key refusal disabled | 1 failed | `test_a_duplicate_decision_key_is_refused` |

`ReplayResolver`'s `setdefault` kept the first record and dropped a second's `human_override` in
silence — its own comment already called that corruption. Refused at load now, beside MD0212's
duplicate-step-id check.

### A48 — a pipeline.yml with no goal is refused

| date | guard | what was reverted | what happened | message |
|---|---|---|---|---|
| 2026-08-10 | `test_pipeline_file.py` | `Pipeline.goal` back to `default_factory=Goal` | 1 failed | `test_a_pipeline_with_no_goal_is_refused` |

Plan 1.10 Task 6 made `goal` keyword-only on `Pipeline.of()` for this reason, but the model field
kept its default and the model is what a hand-edited file loads through. Now required. Two tests
that constructed a bare `Pipeline()` were passing incidentally — `test_a4_...gate...` broke and was
fixed, and `test_egress`'s frozen check was passing for the wrong reason (construction failing
before the frozen assignment) and now passes a real goal.

### A49 — a refused emit leaves the directory untouched

| date | guard | what was reverted | what happened | message |
|---|---|---|---|---|
| 2026-08-10 | `test_pipeline_file.py` | emit back to write-main.nf-then-render-config | 1 failed | `test_a_refused_emit_writes_nothing` |

`emit_config` raises MD0201 on a non-substitutable value; writing `main.nf` first left the
directory half-regenerated, and the retry then refused with MD0214 — blaming the user for a
change emit itself made. Both files render in memory before either is written now.

### A50 — publish certifies the artifact on disk and re-resolves nothing

| date | guard | what was reverted | what happened | message |
|---|---|---|---|---|
| 2026-08-10 | `test_publish.py` | publish routed back through `upgrade`'s re-resolution path | 1 failed | `test_publish_does_not_re_resolve_against_the_installed_registry` |

`publish` shared `upgrade`'s block, so it re-resolved against whatever `--registry` was installed
— an overlay could swap the pipeline, erase the human overrides, and stamp a gate on a result
nobody read, at the door with no undo. It now branches early like `emit`: it needs no registry,
refuses a directory that diverged from its `pipeline.yml`, gates the files on disk, and stamps the
verdict. **A design consequence:** publish no longer re-runs conformance, because conformance is a
property of a contract against its module and publish reads no contracts. That guarantee relocated
to `build`, where it always ran; `test_conformance_guards_the_door_at_build_since_publish_no_longer_re_resolves`
records the move.

### A51 — displacements of all four kinds reach the artifact

| date | guard | what was reverted | what happened | message |
|---|---|---|---|---|
| 2026-08-10 | `test_pipeline_file.py` | `resolve()`'s `displaced` back to `[*measurements.displaced, *registry.displaced]` | 2 failed | `test_a_vocabulary_displacement_reaches_the_artifact`, `test_a_rules_displacement_reaches_the_artifact` |

A23/A24 gave measurements and vocabularies a `Displacement`, but `resolve()` assembled
`PipelineIR.displaced` from measurements+contracts alone, so an overlay `vocabularies/` (the one
kind that rewrites emitted Groovy verbatim) or `rules/` block reached the published artifact
recording nothing — the A23 fix was untested at the artifact and half-inert. `RuleTable` now
carries its own `displaced` list like the other three kinds, and `resolve()` reads all four off
its arguments, so completeness is a property of the arguments rather than of the caller.

### A53 — `upgrade --out` refuses another pipeline's directory

| date | guard | what was reverted | what happened | message |
|---|---|---|---|---|
| 2026-08-10 | `test_upgrade.py` | the in-place self-guard's `.resolve()` back to `==` | 1 failed | `test_upgrade_self_guard_sees_a_relative_out` |
| 2026-08-10 | `test_upgrade.py` | the different-digest `--out` refusal deleted | 1 failed | `test_upgrade_refuses_to_overwrite_another_pipeline` |

The in-place refusal only compared `--out` to the *source's* directory, and it compared
unresolved paths — a relative `--out` naming the source slipped through (the `.resolve()` was
never watched). And a `--out` holding some *third* pipeline was overwritten with no trace: its
overrides, digests and gate evidence gone. `upgrade` now refuses a `--out` whose `pipeline.yml`
has a different content digest than the one being upgraded, unless `--force`; a byte-identical
occupant (an idempotent re-upgrade) is still allowed, and an empty `--out` stays the normal case.

### A54 — `source: human` requires a matching non-null human_override

| date | guard | what was reverted | what happened | message |
|---|---|---|---|---|
| 2026-08-10 | `test_pipeline_file.py` | the MD0220 cross-check in `Pipeline._readable_and_unambiguous` | 1 failed | `test_human_source_requires_a_matching_override` |

`why.source: human` is what clears a tier-4 review, and `source` is declared vocabulary the
resolver sets — not proof. A resolver (a future `mendel-ai` adapter included) could return
`source=HUMAN` for a value no human saw and empty `needs_review()` by assertion. The artifact was
also internally inconsistent — the honest override path recorded `source: human` on the value with
`human_override: null` on the decision (resolve.py never wrote the override back), which is the
same inconsistency read as a bug. Two changes close it: `resolve()` records `human_override` on the
`ParamDecision` whenever `resolution.source is HUMAN`, so the decision carries the evidence; and
`Pipeline` refuses (MD0220) any `source: human` setting without a matching non-null override.

### A41 — a contract that fails to load is blamed on the contract, not the goal

| date | guard | what was reverted | what happened | message |
|---|---|---|---|---|
| 2026-08-10 | `test_pipeline_file.py` | the missing-`via` catch in `ModuleContract.load` (`_missing_via` re-raise) | 1 failed | `test_a_contract_missing_via_emits_MD0200_and_blames_the_contract` |

A `Param` with no `via:` is a real refusal — MD0200, the value reaches no tool — but Pydantic
reported it as a bare `Field required` on `params.N.via`, and the CLI wrapped every
`ValidationError` as "this goal is not valid": the one file the operator did not write, blamed for
a contract author's omission. `load` now re-raises the missing-`via` case with its code and the
contract named, and the CLI wrapper blames "contract" rather than "this goal" for any
`ModuleContract`-titled validation error. Other `ValidationError`s (`nf_process`, `nf_include`,
the model-level route checks) are left untouched, so their tests keep asserting exactly what they did.

### A42 — the round-three refusals that had no watched revert

A42 named guards that fired in no test. Each is reverted and watched below. Two were already
covered and are noted rather than duplicated: **MD0204's multi-line template** is the `NfTemplate`
grammar, watched by the A45 row (Task 2, `test_nf_template_*`); and **MD0201 at build** (a
non-substitutable value in a contract) rides `test_routes.py`'s route checks.

| date | guard | what was reverted | what happened | message |
|---|---|---|---|---|
| 2026-08-10 | `test_pipeline_file.py` | `StepInput._exactly_one_source` (`MD0215`) neutered to `if False` | 2 failed | `test_a_step_input_naming_both_a_source_and_a_channel_is_refused`, `..._neither_...` |
| 2026-08-10 | `test_pipeline_file.py` | `_ext_scope`'s `sorted(step.settings, key=name)` → declaration order | 1 failed | `test_ext_args_fragments_emit_name_sorted_whatever_the_setting_order` |
| 2026-08-10 | `test_emit.py` | `_process_scope`'s `sorted(set(blocks))` → `sorted(blocks)` | 1 failed | `test_a_contract_used_by_two_steps_emits_its_process_block_once` |
| 2026-08-10 | `test_pipeline_file.py` | `_ext_scope`'s `if not substitutable(...)` (`MD0201` at emit) neutered | 1 failed | `test_a_refused_emit_writes_nothing` |

The `ext.args` name-sort had two redundant sorts — one at materialisation (`_settings`), one at
emit (`_ext_scope`) — so an end-to-end build could not watch either alone: whichever you revert,
the other re-sorts. The test reverses a materialised step's settings by hand and calls `_ext_scope`
directly, which is the only place the emit-time sort is observable. Likewise the process-block
dedup needed one contract in two steps, stood in for by the same step twice.

## Round four, 2026-08-11 — the guards themselves, and the last file with no row

Run under [the round-two brief](2026-08-07-round-two-brief.md), findings
[A55–A69](2026-08-11-round-four-audit.md). Two kinds of row: probes that **caught** (recording the
last test file that had no row, `test_pipeline_totality.py`, so A14's file-level residue is now
exhausted), and probes that **stayed green** — the four guards defeated this round, which are
findings, not fixes.

### Caught — `test_pipeline_totality.py` earns its rows

The last file in Plan 1.9's residue list without a row. Four guards; three are sound.

| date | guard | what was reverted | what happened | message |
|---|---|---|---|---|
| 2026-08-11 | `test_pipeline_totality.py` | `ModuleRef.container` dropped (the schema-draft failure its docstring names) | 1 failed | `LockedContract.container` — names the exact field, the `sealed`-profile one |
| 2026-08-11 | `test_pipeline_totality.py` | a stale `NOT_CARRIED` entry (`PipelineIR.nodes` added back to `Pipeline`) | 1 failed | `test_nothing_is_excused_that_is_actually_carried`, naming the field |
| 2026-08-11 | `test_pipeline_totality.py` | `StepInput.states` `list` → `frozenset` with no serializer | 1 failed | `test_no_field_of_pipeline_is_a_frozenset`, naming it |
| 2026-08-11 | `test_pipeline_totality.py` | a `ModuleContract` field added to `ModuleRef` | 1 failed | `test_pipeline_holds_no_registry`, naming it — and `test_egress.py` caught it too |

### Stayed green — the four guards, defeated (A55–A67)

Each is a **real reintroduction** of the property the guard names, followed by the full fast suite,
then restore. These are the round-four criticals and importants; they are recorded here as A14's
whole point — a guard that stays green over the defect it exists to catch is inert.

| date | guard | what was reverted | what happened | finding |
|---|---|---|---|---|
| 2026-08-11 | `test_egress.py` | a `@computed_field` returning PHI-shaped text on `PromptRequest` | **15 passed** — crosses door 1 | A57 (critical) |
| 2026-08-11 | `test_egress.py` | a `@model_serializer` returning three undeclared keys on `PromptRequest` | **15 passed** | A57 (critical) |
| 2026-08-11 | `test_purity.py` | a pure file calling `yaml.unsafe_load` on a `!!python/object/apply:os.system` document | **1 passed**, and it executes | A58 (critical) |
| 2026-08-11 | `test_purity_runtime.py` | a real watched socket opened inside `layers.load` (before the hook arms) | **2 passed** | A59 (critical) |
| 2026-08-11 | `test_purity.py` | `from importlib import import_module as _load` + `urllib.request` in `gates.py` | **1 passed** | A60 (important) |
| 2026-08-11 | `test_construction.py` | `_P = Pipeline; _P.model_construct(...)` in `pipeline_file.py` | **2 passed** | A62 (important) |

The positive controls — spelling `socket`/`Pipeline`/`DataProfile` directly, a bare `str` or `dict`
leaf on a payload, a fifth `DOORS` entry, a watched socket inside `resolve()` — all **fired and
named the defect**, recorded in the audit's *Clean — attacked and held*. The findings are the gaps
between what the positive controls catch and what these probes carry: a serialisation hook, a
third-party capability, an unwatched stage, an aliased name.

### Standing on the unmodified tree (no revert needed — A64, A66)

Two findings reproduce with no probe: `AmbiguityRequest` and `EmittedFile` carry newlines and paths
through bare-`str` `Mark`s (A64), and `Emitted`'s nested evidence is mutable after review because
`frozen` is one level deep (A66). A guard that never has to be reverted to show the gap is the
cheapest finding there is, and neither is guarded at all.

### A68 — the totality guard's own imprecision

`test_pipeline_totality`'s main guard checks field *names* in a flat set. `ModuleRef.digest` removed
→ **4 passed** (`EmittedFile.digest` supplies the name); `Displacement.winning_key` removed → **4
passed** (`Displacement` is carried verbatim, so the field leaves both sides at once). 47 of 78
fields (60%) are compared against themselves. The row above records the three guards in that file
that *are* sound; this records that its headline guard is not.

**A14 does not close.** The file-level residue is exhausted (`test_pipeline_totality.py` was the
last), but four critical findings survived — which is A69: the residue was the wrong measure.

### Lifecycle relaunch — A70, a guard that goes silent on a supported state

| date | guard | what was reverted | what happened | finding |
|---|---|---|---|---|
| 2026-08-11 | `test_publish.py` divergence guard | `emitted:` block stripped from `pipeline.yml` (archived/hand-authored state) + `main.nf` replaced with an unrelated workflow | **`gate preview: PASS`, exit 0** — the bogus `main.nf` certified and its digest stamped as emitted | A70 (important) |

Not a revert of a line — a revert of a *precondition*. `_refuse_a_divergent_directory`'s `MD0213`/
`MD0214` both short-circuit when `pipeline.emitted is None`, and no test covers that path. With the
`emitted:` block **present**, the same corrupted `main.nf` is refused with `MD0214`
(`test_publish_refuses_a_hand_edited_main_nf`) — so the guard's efficacy depends entirely on a field
a hand-authored file legitimately lacks. Publish is the door with no undo.

## Round four fixes (Plan 1.12)

Every guard this plan writes, reverted and watched. `MD0216` shipped inert in Plan 1.10 because
its refusal was written, `make verify` was green, and nothing covered it — so a fix without a
watched revert is a fix nobody has evidence for.

### A55 — a resolved value executing as Groovy

| date | guard | what was reverted | what happened | verdict |
|---|---|---|---|---|
| 2026-08-13 | `test_a_raw_ext_value_cannot_smuggle_groovy` | `Setting._a_raw_ext_value_cannot_be_groovy`'s `substitutable` clause replaced with `and False` | **FAILED** — `DID NOT RAISE ValidationError` | live |
| 2026-08-13 | `test_the_closure_branch_is_unreachable_from_a_raw_value` | `_ext_scope`'s `if not substitutable(...)` short-circuited with `if False and …` | **FAILED** — `DID NOT RAISE ValueError` | live |
| 2026-08-13 | end-to-end, the audit's own attack | nothing — run against the *fixed* tree | `mendel emit` exit **2**, `MD0221`, `/tmp/A55_PROOF` absent | fix confirmed |

Two layers on purpose, and each was watched alone. The load-time validator is what protects a
shared `pipeline.yml`; the emit-time refusal is what stops the emitter depending on a validator
having run, which `model_construct` skips — that is **A62**, still open and carried.

The third row is the one that matters most: the audit reproduced A55 by editing `settings[].value`
to `${['sh','-c','id > …'].execute().text}` on a `key: prefix` setting and running `mendel emit`.
Re-run against this tree, it is refused before emission and no file is written.

**Two guards that did *not* need reverting, recorded because absence of a probe is not absence of
a check:** `test_an_ordinary_raw_ext_value_still_loads` and
`test_an_unanswered_raw_ext_value_still_loads` are over-refusal guards. The second is load-bearing
— `value: null` is an unanswered tier-4 setting, and an earlier draft of the validator that did not
skip `None` refused the shipped spine at load. Invariant 6 says tier 4 is flagged, not fatal.

### A method note, learned the expensive way on 2026-08-13

**Do not undo a probe with `git checkout <file>` while the fix is uncommitted.** It restores the
file to HEAD, which is the *pre-fix* state — the probe and the fix are removed together, and the
tests then pass for the wrong reason. The A55 validator was wiped exactly this way and had to be
re-applied. Revert a probe by replacing the string you inserted, or commit the fix before probing.

This is the same family as Plan 1.11's wrong-worktree near-miss: the verification command ran
happily against a tree that did not contain the work.

### A58 — `yaml.unsafe_load` on the purity allowlist

Three spellings reach the same capability, so there are three probes. The check resolves the
*module* behind a local name rather than matching the text `yaml.`, because a spelling-matched
check is what A60 is.

| date | guard | what was reverted | what happened | verdict |
|---|---|---|---|---|
| 2026-08-13 | `..._cannot_name_an_unsafe_yaml_loader` | `"unsafe_load"` dropped from `BANNED_ATTRIBUTES["yaml"]` | **FAILED** — 3 of 3 loader tests | live |
| 2026-08-13 | `..._an_aliased_yaml_loader_is_caught_too` | `modules.get(node.value.id, "")` → `node.value.id`, i.e. match the spelling | **FAILED** — `import yaml as y` walked past | live |
| 2026-08-13 | `..._the_strict_loader_is_the_one_exemption` | `and not exempt` removed from the attribute route | **FAILED** — and `test_pure_packages_import_nothing_impure` failed with it | live |
| 2026-08-13 | `..._a_loader_imported_as_a_bare_name_is_caught` | (written after the implementation, see below) | **FAILED** before the route existed | live |

The third probe failing the *whole-repo* scan as well is the useful part: it shows the exemption
is load-bearing rather than decorative, and that `yaml_strict.py` really is the only file naming
a loader. `mendel-compiler` only ever calls `yaml.safe_dump`, so the ban needed no second
exemption — a stronger result than the plan assumed.

**One branch was written inert and removed rather than shipped.** The bare-name route
(`from yaml import unsafe_load`) was first written with an `if not exempt` guard copied from the
attribute route. Probe C showed that branch is unreachable — `yaml_strict.py` uses the attribute
form — so it was a condition no file could take. That is precisely `MD0216`'s shape from Plan
1.10, caught this time by probing rather than after the fact, and the route is now unconditional.

### A method note on probing, learned twice on 2026-08-13

**Restore from a file copy, not by reversing the string edit.** Probe B replaced
`modules.get(node.value.id, "")` with `node.value.id`; reversing that replaced the *first*
occurrence of `node.value.id` in the file, which was the unrelated `dotted = …` line, and left
the scan silently wrong while the suite still ran. `cp` the file aside before probing and `cp` it
back. This is the second shape of the same lesson as the A55 row's `git checkout` note: the
verification ran happily against a tree that was not what anyone thought it was.

### A59 — the runtime hook did not watch the stage that reads stranger files

| date | guard | what was reverted | what happened | verdict |
|---|---|---|---|---|
| 2026-08-13 | `test_a_real_build_opens_no_socket_and_spawns_no_process` | `__import__('socket').socket().close()` inserted before `layers.load`'s `return` — the audit's own probe | **FAILED** — where round four recorded `2 passed` on the identical probe | live |
| 2026-08-13 | `..._the_watched_region_covers_the_stage_that_reads_stranger_files` | `state["armed"] = True` moved back below `layers.load` | **FAILED** — `layered.py`, `yaml_strict.py` and `layers.py` absent from the covered set | live |
| 2026-08-13 | composed A58 + A59 | `import yaml` + `yaml.unsafe_load(...)` inside `layers.load` | **FAILED** — caught statically by A58's rule, in the stage A59 now watches | live |

The first row is the finding, reproduced and closed: the same probe that was invisible to round
four now fails the guard.

**The coverage assertion is the row that matters for A14.** Moving one arm line is two minutes of
work and silently reversible — the next person who needs a fixture loaded before arming moves it
back and nothing says so. Asserting *which pure files executed under the hook* is what makes the
region non-narrowable, and probe 2 is the evidence that assertion is not inert. A69 is the same
lesson at a different scale: measure the thing, not a proxy for it.

**`import` could not serve as the coverage signal**, which the plan had assumed it would. Every
module is imported above the arm line on purpose — a hook cannot be uninstalled, so importing
under it would attribute the standard library's own start-up to us — so no import event fires
inside the region at all. `open` is the right signal for the opposite reason: the stage A59 found
unwatched is precisely the stage that reads files somebody else wrote.

### A method note: a probe must be runnable, not merely present

The composed A58+A59 probe was first written as a bare `yaml.unsafe_load(...)` inside
`layers.py` — and the scan reported **green**. That looked like a gap in A58's fix for about a
minute. It was not: `layers.py` does not import `yaml`, so the probe would have raised
`NameError` before reaching anything, and a check that fired on it would have been firing on a
name that cannot resolve. Adding the `import yaml` the real attack needs, the scan refuses it.

The lesson generalises past this file. **A probe that cannot execute proves nothing in either
direction** — green does not mean the guard is weak, and red would not have meant it was strong.
Round three's `MD0216` was a refusal nothing exercised; this is its mirror image, a probe nothing
could run. Both look like evidence and are not.

### A57 — the egress guard reasoned about annotations, not about the dump

| date | guard | what was reverted | what happened | verdict |
|---|---|---|---|---|
| 2026-08-13 | the whole file, seven rules | `@computed_field` returning a patient path added to the **real** `PromptRequest` | **FAILED** in three rules at once — the leaf allowlist, the bare-`str` rule and the free-text marker | live |
| 2026-08-13 | `test_no_payload_replaces_its_own_dump` | `@model_serializer` returning `{"prompt": …, "site": "/mnt/phi/site-4"}` on the real `PromptRequest` | **FAILED** | live |
| 2026-08-13 | `_serialised_hints` | reverted to returning `model_fields` only | **FAILED** — the computed-field test | live |

Round four ran both probes against the unmodified tree and got **15 passed** for each. The dump
in the first probe is unchanged by the fix — `{"prompt":"count genes","context":"/data/patients/…"}`
still crosses if you ship it — but it can no longer do so *quietly*, which is the whole claim
this file makes.

**Two routes, two different shapes, and the asymmetry is the finding's real content.** A computed
field has a return annotation, so it goes through the same leaf check as a declared one — that is
`_serialised_hints`, and six rules now ask it. A `@model_serializer` replaces the dump wholesale
and leaves *no* per-key annotation to check, so nothing can be asserted about its contents and the
only enforceable rule is that a payload may not define one.

**One rule deliberately kept `model_fields`:** `test_every_ambiguity_field_can_cross_the_door`
asks whether each ambiguity field has somewhere *to go*, and a computed field is not a
destination — nothing can be assigned to it. Widening it would have been a mechanical change that
made the rule quietly wrong, which is worth more than the consistency it would have bought.

### The `FREE_TEXT_FIELDS` comment (round four's uncounted caveat)

Not a probe — a correction. The comment above that set read "Exactly two fields may carry it" over
a set of **seven**. It had been wrong for three plans, and it is the same drift family as A33 in
`CLAUDE.md` invariant 14. The number is now deliberately *not* repeated in prose: a count beside a
literal set is two sources of truth, and only one of them executes.

### A56 — a resolver certifying its own answer as human

| date | guard | what was reverted | what happened | verdict |
|---|---|---|---|---|
| 2026-08-13 | `test_a_resolver_cannot_certify_its_own_answer_as_human` | the evidence check dropped — `honoured = resolution.source is HUMAN`, i.e. A54's behaviour | **FAILED** — `needs_review()` empty and `human_override='nefarious'` recorded | live |
| 2026-08-13 | `test_a_replayed_override_backed_by_its_record_is_still_honoured` | (the over-correction guard) | **FAILED** during development, before the CLI threaded `prior` | live |

**The second row is not decoration.** The first version of this fix cut the honest path along
with the dishonest one: `mendel upgrade` demoted a genuinely replayed override and re-flagged a
question a person had already answered — issue #10's shape, a mechanism that runs and changes
nothing. Three A46/A54 regression tests caught it. A guard against over-refusal earns its place
whenever a fix is a refusal.

**What the fix actually establishes, stated honestly.** `Resolution.source` is still a field any
resolver can set to anything; nothing here makes a resolver truthful. What changed is that the
*evidence* now arrives through a different argument than the claim — `resolve(prior=…)`, from the
caller's records — so no single object supplies both. A hostile *caller* is out of scope, and
always was: the caller is our own CLI.

An unbacked claim is **demoted, not refused**. Invariant 6 asks that tier 4 stay flagged, and
demotion restores exactly that; raising would let a broken adapter halt a laboratory's build,
trading a denial of service for a guarantee demotion already gives.

**`prior` defaults to empty, and that is the safe direction** — a verb that forgets it over-flags
rather than under-flags. A2's rule ("an optional guard is the guard the next verb forgets") argues
for making it required; the counter is that `build` legitimately has no records, so a required
argument would be `prior=[]` at every call site, which is a parameter nobody reads. Recorded
because it is a real trade and the next person may disagree.

### A70 — publish certifying an unchecked `main.nf`

| date | guard | what was reverted | what happened | verdict |
|---|---|---|---|---|
| 2026-08-13 | `test_publish_refuses_a_pipeline_with_no_emitted_record` | the `MD0222` branch short-circuited with `if False and …` | **FAILED** — publish certified the bogus `main.nf` at exit 0, as round four did | live |
| 2026-08-13 | end-to-end, the audit's own attack | nothing — run against the *fixed* tree | `mendel publish` exit **2**, `MD0222`; round four's run was `gate preview: PASS`, exit 0 | fix confirmed |
| 2026-08-13 | `test_emit_still_works_on_a_pipeline_with_no_emitted_record` | (over-refusal guard) | passes — `emit` restamps the record | live |
| 2026-08-13 | `test_upgrade_reports_a_missing_emitted_record_rather_than_refusing` | (scope guard) | passes — `upgrade` reports, does not refuse | live |

**The last two rows are the point of the task, not padding.** A refusal on the wrong verb is its
own defect: refusing in `emit` would leave an archived pipeline with no way forward at all, since
`emit` is the *cure* — it regenerates the files and restamps `emitted:`, after which `MD0213` and
`MD0214` mean something again.

**`upgrade` was left alone after reading the test that broke.** The first version of this fix put
`MD0222` on every verb sharing `_refuse_a_divergent_directory`, and
`test_a_pipeline_predating_the_record_says_so_rather_than_claiming_identity` failed. That test is
not an obstacle — it documents `upgrade` already answering this honestly, printing "predates the
emitted-artifact record" and never "byte-identical". The distinction that decides it is what each
verb *does* with the answer: `upgrade` produces a report a person reads, and `publish` stamps a
verdict onto the artifact itself. Only one is a claim about files nobody checked, and only one has
no undo. The scope test above exists so that asymmetry stays a decision rather than becoming an
oversight somebody "fixes" later.

**What A70 was not:** the reviewer was also asked whether A50's build-time conformance relocation
holds. It does — `build`, `upgrade` and `profile` all run `conformance.check` unconditionally
before emitting, and no genuinely-built pipeline reaches publish with unchecked contracts. A70 is
`main.nf` ↔ `pipeline.yml` correspondence, a different question, and A50 is not reopened.

## Plan 1.13 — closing the design audit's correctness findings

| date | guard | what was reverted | what happened | message |
|---|---|---|---|---|
| 2026-08-14 | `test_join.py::test_by_sample_emits_join` (A92) | `if arg.join is Join.BY_SAMPLE:` in `emit._argument`, so both branches combine | failed | `assert '.join(' in 'SAMTOOLS_SORT.out.bam.combine(ch_annotation_gtf.map { it[1] })'` — names the expression it got |
| 2026-08-14 | `test_audit_regressions.py::test_a125_…` | `tied = [c for c in ordered if rank(c)[:2] == best[:2]]` → `tied = ordered` | failed | `At index 0 diff: 'nf-core/hisat2/align@2.2.2' != 'nf-core/minimap2/align@2.28.0'` — names the contract that should not have been offered |
| 2026-08-14 | `test_audit_regressions.py::test_a126_…` ×2 | `ProducerAsked.key()` back to `f"{node_id}.{subject}"` | both failed | `assert ['minimap2_al...lignment.bam'] == ['producer:alignment.bam']`, and the legacy record stopped replaying |
| 2026-08-14 | `test_audit_regressions.py::test_a118_…` | `_computed_over(...)` → `None` in `_validate` | failed | `DID NOT RAISE RuleValidationError` — and the two negatives kept passing, which is the half that matters |
| 2026-08-14 | `test_purity.py` (unplanned) | nothing — `import re` was added to `mendel-resolver` for MD0300 | **failed unprompted** | `rules.py imports re, which is not on this package's allowlist` |

**`test_purity.py` failed without being reverted, which is the strongest evidence in this
table.** Nobody set out to test it: Task 4 needed `re` for `_computed_over`, and the allowlist
caught the addition on the next `make verify` and named the file and the module. That is a guard
demonstrating it is live in the course of ordinary work rather than under a staged revert — the
distinction A14 is about. The widening was then argued for in a comment beside the entry rather
than slipped in, which is what the allowlist exists to force.

**The A92 guard has two halves and only one of them is a revert.** The emitter half is above. The
other half is `test_two_samples_join_pairwise_and_combine_cross_products`, which runs Nextflow on
two samples and asserts `join` gives 2 correctly-paired outputs while `combine` gives 4 — it
carries the wrong branch as a parametrised case *on purpose*, so the two are proven to differ
rather than merely asserted to. That is not a revert-and-watch; it is the failing observation
itself, kept. It runs in 6s with no Docker, because the process it builds has no container.
