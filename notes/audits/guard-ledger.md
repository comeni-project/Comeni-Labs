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

| 2026-08-14 | `test_egress.py::test_every_tier_four_question_can_actually_cross_the_door` | `candidates: list[CandidateRef]` → `list[ContractId]` | failed | `Input should be a valid string … input_value=None` |

**A129's revert is the clearest single result in this table, because of what did *not* fail.**
With the defect restored, both tests ran:

```
test_every_ambiguity_field_can_cross_the_door               PASSED
test_every_tier_four_question_can_actually_cross_the_door   FAILED
```

The pre-existing test compares field *names*, and names were never the problem — every field had
somewhere to go while two of the three question kinds could not get through on their **values**.
That is the shape A14 is about: a guard that cannot fail for the defect it appears to cover. Both
are kept. The name test catches a *new* field with nowhere to land, which is the quiet half of
A32 and still worth having; the new one catches a payload that cannot be built.

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

## Plan 1.14 — the explanation

| date | guard | what was reverted | what happened | message |
|---|---|---|---|---|
| 2026-08-14 | `test_upgrade.py::test_a_pipeline_written_before_a_schema_change_…` | `predates_schema` branch in `cli._check_directory` → `if False:` | failed | `assert "MD0213" not in err` — names the file it claimed was edited |
| 2026-08-14 | `pipeline_file.is_stale`'s `predates_schema` short-circuit | removed | **nothing failed — the guard was inert** | see below |
| 2026-08-14 | `test_upgrade.py::test_emit_does_not_call_a_schema_change_an_edit_either` | the same short-circuit, once the test existed | failed | `assert 'MD0213' not in '5 modules, …enerating.'` |

**An inert guard, found in code written the same hour, which is the whole of A14 in one row.**
Task 0 put the schema check in two places: `cli`'s `upgrade` branch and `pipeline_file.is_stale`.
Reverting the `is_stale` half changed nothing — `upgrade` returns at the `cli` branch and never
reaches it — so that half was protecting the `emit` verb, which nothing tested. Without it an
archived pipeline would be told it had been edited every time somebody regenerated it, **by the
one verb whose job is to cure exactly that**.

The lesson is not that the code was wrong; it was right and untested. It is that *writing* a
guard and *watching it fail* are different acts, and only the second one tells you which of them
you actually wrote. `test_emit_does_not_call_a_schema_change_an_edit_either` is the missing half,
and the row above it is kept as the record that it was missing.

| date | guard | what was reverted | what happened | message |
|---|---|---|---|---|
| 2026-08-14 | `test_pipeline_file.py::test_editing_a_value_and_leaving_its_reason_is_refused` (A104) | `for_value=value.value` in `_why` | failed | `assert code != 0` — emit accepted the edit again |
| 2026-08-14 | `test_publish.py::test_publish_refuses_to_certify_a_value_whose_reason_is_false` | the same line | failed | publish certified it at exit 0, which is A104 exactly |
| 2026-08-14 | `test_pipeline_file.py::test_emit_clears_the_gate_verdict_when_the_file_was_edited` | nothing — a walrus named `stale` shadowed the `MD0213` boolean | **failed unprompted** | `assert 'lint' is None` |

**The third row is not a revert either, and it is the useful one.** Writing `MD0223` as
`if stale := stale_reasons(pipeline)` shadowed a boolean read twelve lines below to decide
whether a `publish`ed gate verdict survives an edit — so an edited pipeline kept its
certification. Nobody staged that; an existing A47 guard caught it on the first `make verify`
after the change. Two unprompted catches in two plans (`test_purity.py` in 1.13, this in 1.14),
both from guards written for something else, is the argument for running the *whole* gate rather
than the tests you think you touched.
| 2026-08-14 | `test_runnable.py::test_an_asserted_fact_and_a_measured_one_are_distinguishable` (A80) | the asserted branch in `_meta_entry` reworded to `"measured"` | failed | `assert 'goal' in 'measured; signal et al. 2022 …'` — the artifact claiming a profiling run that never happened |
| 2026-08-14 | `test_upgrade.py` ×3 + `test_pipeline_file.py::test_a_schema_change_…` | nothing — `MetaEntry.why` was made required | **failed unprompted** | the committed v1 fixture stopped parsing, which is a required field breaking archived pipelines |

**A third unprompted catch, and this one came from a fixture rather than a guard.** Making
`MetaEntry.why` required is right for construction and wrong for *reading*: a document written
before the field existed cannot answer, and requiring it of one asserts that the provenance is
missing rather than that it was never recorded. The committed pre-1.13 pipeline caught that
within a minute of the change. The backfill says so in the file — *"provenance was not recorded:
this pipeline predates schema 2"* — and `test_a_v1_file_says_its_provenance_was_never_recorded`
pins the claim, because a migration that quietly invents a citation is worse than one that
refuses.

That fixture was committed an hour earlier for a different reason entirely (Task 0's digest
test). It has now caught a second, unrelated compatibility break. Committing it was the cheapest
thing in this plan.

| date | guard | what was reverted | what happened | message |
|---|---|---|---|---|
| 2026-08-14 | `test_runnable.py::test_every_positional_literal_says_why_it_is_that_value` (A81) | `because:` on samtools/sort's `literal: bai` | failed | `a positional literal must say why it is that value … nf-core/samtools/sort@1.21.0 input 2 = 'bai'` |

**The guard found a third literal the audit missed.** A81 named two — `SAMTOOLS_SORT(…, 'bai')`
and `STAR_ALIGN(…, false)` — because those are what the *shipped spine* routes.
`nf-core/hisat2/align` has one too (`save_unaligned`), and it only appears in a pipeline when
the measured read length is under 70 bp. Written as a sweep over `registry.all()` rather than
over the spine, which is why it counted three where a reviewer reading a build counted two.

`Why.reason` is a `Line`, so YAML's `>` folded scalar broke the build on its trailing newline —
*"contains a control character. This text is written into a generated file"*. That is an
existing guard doing its job on prose nobody had tried to put there before; the contracts use
`>-`.

| date | guard | what was reverted | what happened | message |
|---|---|---|---|---|
| 2026-08-14 | `test_runnable.py::test_the_ext_args_premise_survives_the_module_it_names` (A82) | STAR's `ext_args` back to the bare-string form | failed | `assert 'gzip' in 'declared by the contract with no stated reason'` |

**The revert degrades to a visible gap rather than to a wrong answer**, which is the half worth
recording. Dropping the premise does not restore the old sentence about TrimGalore; it produces
*"declared by the contract with no stated reason"* — greppable, honest, and obviously unfinished.
A compatibility path that invents a plausible reason would have passed this test and made the
artifact worse.

| date | guard | what was reverted | what happened | message |
|---|---|---|---|---|
| 2026-08-14 | `test_audit_regressions.py::test_a79_…` | `because()` back to taking the block's `cite` | failed | `assert 'Dobin' not in 'rule producer_of:alignment.bam matched {'read_length': '< 70'}: Kim …; Dobin …'` |
| 2026-08-14 | `test_egress.py::test_free_text_lives_only_where_declared` | nothing — `axis_reason` was added to two payload-reachable models | **failed unprompted** | `Extra items in the left set: ('Why', 'axis_reason'), ('ResolvedValue', 'axis_reason')` |
| 2026-08-14 | `packages/mendel-resolver/tests/test_rules.py` ×8 + `test_resolve.py` | nothing — `MD0301` was added | **failed unprompted** | eleven fixtures had no `because` or `cite` at all |

**The egress guard made the free-text count something somebody had to argue for**, which is
exactly what invariant 14's literal list is for. Two fields were added, taking the count from
seven to nine — the fourth time it has moved, and the fourth time by a *refactor* rather than by
a new kind of string crossing: this is one field splitting in two, same author, same source,
same door. `CLAUDE.md`'s count was updated with the reasoning rather than the number alone,
since that sentence is the one the invariant itself admits drifts (A33).

**`MD0301` failed eleven fixtures on arrival**, and that is the check having real negatives
rather than a problem. Each was a minimal rule written before a justification was required; all
eleven now carry one. The one in `test_resolve.py` was more interesting — it asserted the
block's `because` appeared in the row's `reason`, which is precisely the conflation A79 is, so
the assertion moved to `axis_reason` rather than being deleted.

| date | guard | what was reverted | what happened | message |
|---|---|---|---|---|
| 2026-08-14 | `test_audit_regressions.py::test_a76_…` | `from_layer=from_layer` on the tier-2 branch | failed | `tier 2 must say which layer documented it` / `assert None == 'acme-lab'` |
| 2026-08-14 | `test_audit_regressions.py::test_a128_…` | the `chosen.priority_because` fallback in `_choose`'s caller | failed | `assert 'nf-core/rnaseq' in ''` |

**Task 1 had already half-closed A76 without either of us noticing.** The finding is that a
value moving 0 → 30 produced a *byte-identical* `why:`; `Why.for_value` (Task 1) made the two
blocks differ before this task touched anything, so the `base.why != lab.why` assertion passed
on arrival. What was still broken is the part that matters to a reader: `from_layer: null` on a
value an overlay supplied, and a reason — `contract default for min_mqs` — that names the field
it is explaining rather than justifying it. Worth recording, because "the test passes" and "the
finding is closed" came apart here, and only writing the assertions separately showed it.

| date | guard | what was reverted | what happened | message |
|---|---|---|---|---|
| 2026-08-14 | `test_audit_regressions.py::test_a91_a_positional_parameter_…` | the `from_setting` branch in `emit._argument` | failed | `STAR_ALIGN(…, ch_annotation_gtf, null)` — the answered value vanishing, which is what `MD0224` refuses |
| 2026-08-14 | `test_emit.py::test_every_via_member_emits_or_is_refused` (A38) | nothing — `Via.POSITIONAL` was added | **failed unprompted** | `emit.py handles {EXT, META, DIRECTIVE}; Via also has {POSITIONAL}` |
| 2026-08-14 | `test_audit_regressions.py::test_a_binding_with_no_declared_param_…` | nothing — `samtools/sort` gained a param | **failed unprompted** | `the fixture needs a param-less one` |

**A38's tripwire is the best-designed guard in this repository and it proved it here.** It exists
so that adding a `Via` member forces a decision — wire it into `emit.py` or refuse it at load,
never leave it recording a value that reaches no tool. Adding `POSITIONAL` failed it immediately,
before any of this task's own tests existed. Updating it was a deliberate edit with a stated
reason rather than a widening.

**And a fixture that guards its own assumption caught a second thing.** `test_a_binding_with_no_
declared_param_refuses_instead_of_vanishing` asserts *"the fixture needs a param-less one"*
before using `samtools/sort` — which stopped being param-less the moment `index_format` became
routable. Naming the requirement instead of assuming it turned a confusing downstream failure
into one line.

**`MD0108`'s new meta arm refused a test fixture on arrival**, which is the check having real
negatives: A38's `via: meta` test routed an invented `tag` that featureCounts never reads —
precisely the deadness the arm exists to catch, and precisely where A91 hid. The fixture now
routes `single_end`, a key the module does read, with a goal that supplies no `paired`
measurement so the key is free.

| date | guard | what was reverted | what happened | message |
|---|---|---|---|---|
| 2026-08-14 | `test_upgrade.py::test_a77_…` and `::test_a111_…` | `_replayed_reason(record)` back to `record.reason` | both failed | the hand-written sentence replaced by *"selected the first of 1 candidates without judgement — please review"* under `source: human` |
| 2026-08-14 | `test_egress.py::test_free_text_lives_only_where_declared` | nothing — `override_reason` was added | **failed unprompted** | `('ParamDecision', 'override_reason')` |

**The tenth free-text field is the first that is not a refactor**, and the guard is what forced
that to be noticed and argued rather than absorbed. The nine before it are written by a contract
author, a rule author or the resolver; this one is written by *the person answering a tier-4
question*, in the artifact, after resolution — a new author at a new moment. The sentence in
`CLAUDE.md` claiming every increase had been a refactor was true when written and is now false,
so it was corrected rather than left to drift, which is A33's own lesson applied to A33's own
paragraph.

**Writing the test walked straight into A112**, before the task reached it. Setting
`why.source: human` by hand was refused by `MD0220` — whose message said *"set the decision's
human_override to the value"*, contradicting `pipeline-schema.md`'s *"it is not where you write
one"* two paragraphs above. The test could not be written correctly by following the diagnostic.
Both now say the same thing: edit `settings[].value` and the reason beside it, and leave `source`
alone.

---

## Plan 1.15 Task 0 — a contract declares the roles it fills (A119, A123)

| date | guard | what was reverted | what happened | message |
|---|---|---|---|---|
| 2026-08-15 | `test_roles_through_the_loader.py::test_a_contract_naming_an_undeclared_role_stops_the_build` | the `roles.check(...)` loop in `layers.load()` | failed | `DID NOT RAISE UnknownRoleError` |
| 2026-08-15 | `test_roles.py` ×4 (core) | the same loop | **nothing failed** | see below — this is the row worth keeping |
| 2026-08-15 | `test_roles.py::test_a_role_name_is_snake_case_on_a_contract` | `AfterValidator(_role_name)` on `RoleName` | failed | `DID NOT RAISE ValidationError` for `Alignment`, `ribo-depletion`, `2pass`, `_hidden`, `trailing_` |
| 2026-08-15 | `test_roles.py::test_a_vocabulary_cannot_declare_a_role_no_contract_could_name` | the `_role_name` call in `RoleVocabulary.kind()`'s `parse` | failed | `DID NOT RAISE` for a vocabulary declaring `Ribo-Depletion` |
| 2026-08-15 | `layers.py::_every_file_is_claimed` (A26) | nothing — `registry/roles/` was added before the kind was wired in | **failed unprompted** | `registry layer … contains roles/roles.yml, which nothing reads` |

**Two inert guards were found in code written the same hour, and one guard caught the author.**

**The `roles.check` loop was protecting nothing.** `packages/comeni-core/tests/test_roles.py`
called `RoleVocabulary.check` directly — four green tests proving the function works and proving
nothing about whether anything *calls* it. Deleting the loop from `layers.load()` left all four
green. `test_roles_through_the_loader.py` exists for that reason and for no other: it loads a
real layer stack through the real loader, which is the only thing that can fail when the call
goes away. Same shape as Plan 1.9's three, and as A14 generally.

**The `RoleName` validator was also inert**, and chasing it found a defect rather than just a
missing test. `RoleVocabulary.kind()`'s `parse` returned bare strings, so a vocabulary could
declare `Ribo-Depletion` — which loads — while every contract naming it was refused by
`RoleName`. A declaration nothing can legally use: legal, silent, useless, and the same family
as A122's rule that can never fire. Validating both sides is the fix; the asymmetry was only
visible because the validator was being reverted.

**`_every_file_is_claimed` failed unprompted and was right.** `registry/roles/` was added before
`RoleVocabulary.kind()` was wired into `layers.load()`, so its file was hashed into the layer
digest and read by nothing — exactly A26. Its message also named the four kind directories as a
literal, which would have been wrong the moment a fifth existed, so it now derives them from
`DeclaredKind`. Same reasoning as invariant 14's *"the guard's roots come from `DOORS` rather
than from what happens to live in `egress.py`"*.

**One revert was invalid and is recorded as such.** The first attempt at removing the
vocabulary-side validation cut the file mid-block and produced a collection error rather than a
test failure. A guard that "fails" because the module will not import has not been watched — it
was redone with valid syntax, and the row above is the valid one.

## Plan 1.15 Task 1 — the premise layer (A108, A120)

| date | guard | what was reverted | what happened | message |
|---|---|---|---|---|
| 2026-08-15 | `test_premises.py::test_an_asserted_fact_is_not_a_measured_one`, `…_a_human_override_is_evidence_of_the_same_quality_…`, `…_a_goal_declared_purpose_is_a_premise` | `origin=_BY_SOURCE[entry.source]` → always `PremiseOrigin.MEASURED` | **3 failed** | `assert <PremiseOrigin.MEASURED: 'measured'> is <PremiseOrigin.ASSERTED: 'asserted'>` |
| 2026-08-15 | `test_premises.py::test_nothing_may_declare_a_measurement_named_required_states` | the `_RESERVED in measurements.ids()` refusal | failed | `DID NOT RAISE PremiseError` |
| 2026-08-15 | `test_premises.py::test_required_states_is_present_and_empty_rather_than_absent` | writing the premise only when the goal named states | failed | `KeyError: 'required_states'` |
| 2026-08-15 | `tests/test_purity.py::test_pure_packages_import_nothing_impure` | nothing — `premises.py` imports `enum` | **failed unprompted** | `premises.py imports enum, which is not on this package's allowlist` |
| 2026-08-15 | `make types` (`tools/generate_types.py --check`) | nothing — `registry/measurements/purpose.yml` was added | **failed unprompted** | `profile.pyi is stale` |
| 2026-08-15 | `tests/test_registry_layer.py::test_the_layer_loads_from_its_new_home` | nothing — the same file | **failed unprompted** | `At index 2 diff: 'purpose' != 'read_length'` |

**The plan predicted the wrong outcome for its own guard, and the prediction was pessimistic.**
Step 5 said to collapse the provenance mapping, confirm the measured case still passes, and
confirm that *"no test fails — the asserted case has no guard yet, which is Task 8's."* Three
tests failed. That sentence was written against the four-test draft of this task; the corrected
version added the human-override and `purpose` cases, and each of them pins the asserted side
independently. **A stale prediction of inertness is the one kind that costs nothing to be wrong
about**, because the revert is run either way — which is the argument for running it rather than
reasoning about it, in the same shape as A14 itself.

**Two guards failed unprompted for the same one-line cause**, and the pair is the useful part:
`registry/measurements/purpose.yml` is *data*, and adding it broke a generated stub and a
literal list in a test. Neither is in `mendel-resolver`, and neither would have been found by
running the task's own test file. `make check` is what found them, which is the case for
running the whole gate on a change that looks confined to one package.

**`test_purity.py`'s allowlist did what its own comment asks of it.** `re` was added on
2026-08-14 with a written argument, and the comment beside it says the guard *"is supposed to
make an addition something somebody argues for"*. `enum` is the second such addition and got
the same treatment: `PremiseOrigin` is a closed vocabulary and every other one in this
repository is a `StrEnum`, so the alternative — bare string constants — would have made an
undeclared origin representable and would have cost `_BY_SOURCE` its totality. This is the first
time `mendel-resolver` has *declared* a vocabulary rather than read one from `comeni-core`,
which is why the entry was not already there.

**`tools/generate_types.py` had two line-wrapping forms and needed three.** `purpose`'s four
enum values make the return annotation 101 characters on a line of its own, so the fallback that
exists to keep the generated stub lint-clean produced a stub that failed `ruff check` — the
exact outcome its own comment names as the thing to avoid (*"a generated file that fails `ruff
check` is a generated file somebody edits by hand"*). Latent since the generator was written;
reachable only by declaring a measurement with long values. The third form wraps inside
`Literal[`, which has no length at which it stops working. **Shortening the declared values to
fit would have let a line limit edit the vocabulary**, which is why it was fixed in the tool.

**Task 0 residue, found by a test rather than by review.** `registry/registry.yml` still said
`kinds: [contracts, measurements, rules, vocabularies]` while `registry/roles/` sat beside it.
Nothing reads that field — `tests/test_registry_layer.py` pins it and nothing else — and that is
the point of it: it is the layer's account of itself to a stranger who opens the directory, and
a self-description that drifts is worse than none.

**`MD0302` shipped in Task 0 with no `diagnostics.yml` entry**, which the plan's own Global
Constraints require of every new code. It was invisible because `tests/test_diagnostics_registry.py`
validates codes passed to `Diagnostic(...)`, and `roles.py` raises a bare `ValueError` with the
code in the string — so the registry could not see it. Both `MD0302` and this task's `MD0303`
are declared now. The general case is issue #18, the half-declared error surface, and this is
one more instance of it: a code in an f-string is a code no registry knows about.

## Plan 1.15 Task 2 — a derived fact fills a gap and never overwrites (A122, R15)

| date | guard | what was reverted | what happened | message |
|---|---|---|---|---|
| 2026-08-15 | `test_premises.py::test_a_derivation_never_overwrites_a_measurement` | `if derivation.fact in premises: continue` in `_derive` | **nothing failed** | — this is the row worth keeping |
| 2026-08-15 | `test_premises.py::test_a_derivation_whose_row_would_match_still_never_overwrites`, `…_never_overwrites_an_earlier_derivation_either` | the same line, after the guard was strengthened | **2 failed** | `assert 'reverse' == 'forward'` |
| 2026-08-15 | `test_premises.py::test_a_derivation_with_no_rows_is_refused` | the `if not self.rows` refusal on `Derivation` | failed | `DID NOT RAISE` |

**The never-overwrite guard was inert, and the plan predicted it would not be.** Step 5 said to
delete the line and *"confirm `test_a_derivation_fills_a_gap_and_never_overwrites` fails on the
second assertion with `'reverse' != 'forward'`"*. It does not, and the reason is in the fixture
rather than in the code: R15's row is `when: {strandedness: absent}`, so once `strandedness` is
measured **the row fails its own predicate** and the never-overwrite rule is never reached. The
test was passing for a reason unrelated to what it claimed to check, which is the definition of
the thing A14 is about.

The plan's fixture had the same shape, so this would have been missed by following the plan
exactly and reading carefully. **Only running the revert finds it** — the third time in two
plans that the revert has caught code written the same hour, after Plan 1.14 Task 0 and Plan 1.15
Task 0.

**The replacement conditions on a different fact from the one it derives**, so the row matches
and only the rule stands between a measurement and a default. A second test covers derivation
against derivation, where `absent` cannot mask the same way.

**The rule was also written narrower than the plan specified, deliberately.** The plan has
`if fact in measurements.ids() and fact in premises`, scoping never-overwrite to *declared
measurements* — spec §3.1's wording. Dropping the first clause makes it never-overwrite-anything,
so two derivations of the same new fact resolve first-wins rather than last-wins. Last-wins would
make the answer depend on which file `stack()` reached first, which is invariant 10. First-wins
is also what `ReplayResolver` already does with duplicate keys, so this is one convention rather
than a second one. Task 11 should refuse the duplicate at load; until it does, the resolution is
at least not order-dependent.

### Task 2b — the aggregate half (R19, spec §3.2), after the operator's call on representation

| date | guard | what was reverted | what happened | message |
|---|---|---|---|---|
| 2026-08-15 | `test_premises.py::test_an_aggregate_over_a_scalar_reduces_to_that_scalar` | the scalar branch of `_aggregate`'s `values` | failed | `KeyError: 'cohort_max_read_length'` |
| 2026-08-15 | `test_premises.py::test_a_list_is_refused_where_the_measurement_is_not_per_sample` | the `not measurement.per_sample` refusal in `check` | failed | `DID NOT RAISE` |
| 2026-08-15 | `test_premises.py::test_a_derivation_declaring_both_rows_and_an_aggregate_is_refused` | covered by Task 2's `_can_fire` revert | failed | `DID NOT RAISE` |

**A scalar reduces to itself, and that is a decision rather than a convenience.** A per-sample
measurement written as one value is the claim that the cohort is uniform, so its max, min and
mean are all that value. Without the branch, `cohort_max_read_length` exists for a three-sample
profile and vanishes for a one-sample one — **a fact that appears and disappears with the shape
of the input is a fact no rule can be written against**, and the rule would fail by silently
not firing rather than by any diagnostic.

**The stub generator was wrong before it was stale, which is the more expensive of the two.**
`tools/generate_types.py`'s own header says *"stale costs autocomplete, never correctness"*, and
that guarantee held only while every measurement was scalar. With `read_length` declared
`per_sample`, `--check` passed — the file was current — while the overload it contained said
`int | None` for a value the loader accepts as `list[int]`. `--check` cannot see that class of
error at all: it compares the generated file against itself. Fixed in `_returns`, and the
fallback overload and the `Measured` declaration in the header were wrong in the same way.

## Plan 1.15 Task 3 — one predicate evaluator, and a row's tier is its text (A121)

| date | guard | what was reverted | what happened | message |
|---|---|---|---|---|
| 2026-08-15 | `test_predicates.py::test_a_row_testing_no_premise_positively_is_tier_2`, `…_present_earns_tier_3_and_absent_does_not` | `tier_of_row`'s `if expected != ABSENT` | **2 failed** | `assert <Tier.DATA_PROFILED: 3> is <Tier.CONVENTION: 2>` |
| 2026-08-15 | `test_predicates.py::test_an_unknown_predicate_is_refused_rather_than_ignored` | the `MD0305` raise, falling through to `return False` | failed | `DID NOT RAISE PredicateError` |
| 2026-08-15 | `test_predicates.py::test_a_comparison_against_a_cohort_is_refused_rather_than_raising_TypeError` | the `isinstance(actual, list)` refusal | failed | `TypeError` from `predicates.py:88` — which is the guard's own argument, printed |

**Revert C is the clearest evidence in this ledger of what a diagnostic buys.** Removing the
refusal does not make the comparison work; it makes it raise `TypeError: '>=' not supported
between instances of 'list' and 'int'` from inside the resolver, naming neither the rule nor the
fact nor the file. The guard exists to convert that into `MD0312`, which names the fact, says it
is a cohort of three values, and prints the `derives:` aggregate that would have been right.

**`present` and `absent` look like a pair and are not one**, and `tier_of_row` is where that
matters. `present` is a test on the data — something measured this — so a row conditioned on it
did tier-3 work. `absent` is a test on the *absence* of data, which is exactly the case with no
measurement behind it, so it is tier 2: value plus citation. Reverting the clause collapses both
into tier 3 and two tests catch it, which is the pair being genuinely two guards rather than one
written twice.

**`predicates.py` imports `Premise` under `TYPE_CHECKING` only.** `premises.build_premises` calls
`matches`, so a runtime import in the other direction is a cycle. Nothing in the evaluator reads
a premise beyond whether it exists and what its `value` is, so the annotation is the only thing
that needs the name — and stating that in the module docstring is what stops somebody
"fixing" the odd-looking import later.

**Task 2's inlined `_matches` is deleted rather than left beside this one.** Its own docstring
said Task 3 would replace it, and a second matcher that agrees today is the shape `_comparison`'s
docstring already warns about: *"two copies of this predicate is how a rule passes validation and
then fails to fire."*

## Plan 1.15 Task 4 — a decision names a role, and cannot collide (A119, A123, R20)

| date | guard | what was reverted | what happened | message |
|---|---|---|---|---|
| 2026-08-15 | `test_roles_through_the_loader.py::test_the_shipped_registry_loads_with_every_contract_classified` (+2, +10 errors) | `roles: [alignment]` deleted from `star-align.yml` | **3 failed, 10 errored** | `these contracts fill no role: ['nf-core/star/align@1.11.0']`, and `MD0306` breaking every build |
| 2026-08-15 | `test_rules.py::test_two_decisions_for_one_target_in_one_file_is_MD0309` | the `target.key() in seen` check | failed | `DID NOT RAISE RuleValidationError` |
| 2026-08-15 | `test_rules.py::test_a_rule_for_a_parameter_no_contract_declares_will_not_load` | the `MD0308` declared-by-every-filler check | failed | `DID NOT RAISE` |
| 2026-08-15 | `test_rules.py::test_a_decision_on_a_role_nothing_fills_is_refused` | the `if not fillers` check | failed | `DID NOT RAISE` |

**Task 0's open row is closed, and by more than the test that was written for it.** The ledger
recorded *"`test_roles.py` ×4 — nothing failed"* against the `roles.check` loop, because those
four tests called the function directly. Deleting `roles:` from one contract now fails three
tests in the loader file **and errors ten more**, because the shipped `implementation: alignment`
rule names STAR and STAR no longer fills that role — `MD0306` refuses the whole build. A role
declaration went from a field nothing consulted to one the rule table depends on, which is what
made the guard real rather than the guard being rewritten.

**`MD0309` and `stack()`'s duplicate-key refusal are not redundant and neither can see the
other's case.** `MD0309` is per *file*, caught in `parse`, and its message can name the file and
the key. `stack()`'s is per *layer*, across files, and is the one mechanism shared by every kind
— which is root B's whole point and why a per-kind exception type was not reintroduced here. Two
tests, one for each, with the argument written into both docstrings.

**A fixture went inconsistent the hour the check landed**, and this is the good version of that
event. `test_a_role_declared_only_by_an_overlay_satisfies_a_base_contract` *replaced* STAR's
`alignment` role with `long_read_alignment` to prove an overlay-declared role loads. That fixture
was fine while nothing read the role and became a contradiction the moment the rule table did —
so the test failed for `MD0306` rather than for anything it was about. Adding the overlay role
beside the base one is the fix, and the comment beside it says why, because the next person to
edit that line will reach for the substitution again.

**The shipped rule migrated at Task 4 rather than Task 11**, which the plan did not anticipate.
`DecisionTarget` changes incompatibly here, so leaving `registry/rules/rnaseq.yml` in the old
format would put `make check` red for seven tasks — and the Global Constraints say `drift` is the
only gate that may be red, for exactly the reason A14 gives: a gate red for unexamined reasons
trains everybody to ignore it. Migrating one block now costs nothing and keeps that rule intact.

**`make verify`'s slow tests are what proved the migration.** `test_counts.py` runs the spine on
real data and asserts featureCounts got the strandedness that was measured — so a role-keyed
lookup that silently stopped finding the aligner rule would show up there and nowhere else in the
686 tests. It passed, which is the evidence that `implementation:alignment` routes what
`producer_of:alignment.bam` used to.

## Plan 1.15 Task 5 — a step can be absent, and a convention cannot block routing (§8.2)

| date | guard | what was reverted | what happened | message |
|---|---|---|---|---|
| 2026-08-15 | `test_presence.py::test_removing_a_conventionally_required_state_still_routes` (+2) | `trimmed` moved back to `state_required` on `star-align.yml` | **3 failed** | `nothing produces fastq.reads with states ['trimmed']` — the finding itself, printed |
| 2026-08-15 | `test_presence.py` ×4 | the `absent_roles & set(c.roles)` filter in `route()` | **4 failed** | `TypeError`/`nf-core/trimgalore@0.6.10` still in the plan |
| 2026-08-15 | `test_presence.py::test_the_spine_still_inserts_trimming_when_no_rule_removes_it`, `test_spine_contracts.py::test_counts_matrix_is_reachable_from_raw_reads` | the conventional alternative in `InputPort.alternatives()` | **2 failed** | trimming absent from a pipeline no rule touched |
| 2026-08-15 | `test_presence.py::test_a_presence_absent_rule_removes_the_step_from_a_built_pipeline` | the `fired.value == "absent"` test in `resolve()` | failed | the step is still in `ir.nodes` |

**Revert A prints the finding.** `nothing produces fastq.reads with states ['trimmed']` is
exactly what a rule saying *"skip trimming"* produced before the split: not a shorter pipeline
but an unbuildable one. The guard's message and the audit finding are the same sentence, which is
the most useful thing a revert can produce.

**Revert C is the half that is easy to get wrong, and it fails loudly.** Removing the
*conventional* alternative from `alternatives()` does not merely stop the fallback — it deletes
trimming from every pipeline, including ones no rule touches, because the goal's raw `fastq.reads`
then satisfies the aligner directly and TrimGalore is never inserted. A conventional requirement
has to keep driving insertion, and `test_the_spine_still_inserts_trimming_when_no_rule_removes_it`
exists solely to pin that. It was written *before* the implementation for that reason, and the
revert confirms it is not decorative: it and the spine reachability test are the only two that
notice.

**The end-to-end test was added because the wiring was otherwise untested.** `presence_for` had
existed since Task 4 and nothing called it; `resolve()` calling it is a separate fact from the
method being correct. Four green tests over a role check no loader ran is exactly what Task 0
recorded, so the test goes through `resolve()` on a real layer stack with a real rule file.
Revert D — the one line in `resolve()` — fails it and nothing else, which is the point.

**`state_conventional_because`, not `state_required_because`.** The plan's file list names the
latter, and it would read as justifying `state_required` — the one field it is not about. The
distinction between the two fields is the entire content of §8.2, so a name that blurs them is
the wrong name. §4.7's rule applied to a field name rather than to a value.

**`presence: present` currently does nothing, deliberately and not silently.** It is the default
branch of a presence decision — *"absent below 50bp, otherwise present"* — where "present" means
leave routing alone, which is a real answer rather than a dead one. Forcing a step that routing
would not otherwise insert is a different feature, is spec §4.1's open half, and is carried.

## Plan 1.15 Task 6 — one decision may land on several tools (§4.2)

| date | guard | what was reverted | what happened | message |
|---|---|---|---|---|
| 2026-08-15 | `test_rules.py::test_one_decision_lands_on_two_tools` (+2) | `Decision.targets()` returning `[self.decides[0]]` | **3 failed** | the effect set is missing `param:alignment:star_ignore_sjdbgtf` |
| 2026-08-15 | `test_rules.py::test_both_targets_of_one_decision_are_validated` | `_validate`'s loop cut to `targets()[:1]` | failed | `DID NOT RAISE` for a second target naming an unfilled role |
| 2026-08-15 | `test_rules.py::test_two_decisions_cannot_both_land_on_one_target_across_files` | `_no_target_is_decided_twice()` | failed | `DID NOT RAISE` |

**A revert was applied to the wrong call site and reported a false result.** The first attempt at
the middle row edited `for target in decision.targets():` with a one-occurrence string replace,
and that string appears **five times** in the file — it hit `_no_target_is_decided_twice`, not
`_validate`. The run failed one test, which looked like a plausible outcome, and the row would
have been recorded as evidence for a guard that had never been touched.

What caught it was that the failure was the *wrong* test: the reverted line was supposed to break
"both targets are validated" and instead broke "two decisions cannot land on one target", which
is a different guard's test. **A revert whose failure does not match its prediction has not been
watched** — the probe that followed printed the real exception and its origin and showed
`MD0306` still firing from the untouched loop. Recorded because the near-miss is the useful part:
this is the second time in this plan that an apparently sensible revert result was not what it
appeared to be, after Task 2's inert never-overwrite guard.

**The composite stacking key opens A119 again, and the third row is where it is closed.** A
multi-target decision replaces as a whole, so its `stack()` key is the whole set — which makes a
second decision naming only *one* of those targets a different key. It stacks happily beside it
and both fire on that target. `MD0309`'s per-file check cannot see it, because they are in
different files; `stack()`'s per-layer check cannot see it either, because to it they are two
different keys. `_no_target_is_decided_twice` runs after assembly, which is the only place both
are visible at once.

The composite key was kept rather than abandoned because half a replacement is the worse failure:
an overlay redeciding one of two targets would leave the base layer's other target in force under
a justification the overlay never wrote.

## Plan 1.15 Task 7 — a decision exits at the tier its evidence earned (A113, A76, A128)

| date | guard | what was reverted | what happened | message |
|---|---|---|---|---|
| 2026-08-15 | `test_earned_tiers.py::test_a_tier_2_row_must_carry_a_citation` | the `MD0313` tier-2 citation rule | failed | `DID NOT RAISE RuleValidationError` |
| 2026-08-15 | `test_earned_tiers.py::test_only_one_candidate_is_not_a_forcing_constraint`, `test_pinning.py::…cannot_produce_what_was_asked` | the single-candidate branch back to `Tier.STRUCTURAL` | **2 failed** | `assert <Tier.STRUCTURAL: 1> is <Tier.CONVENTION: 2>` |
| 2026-08-15 | `test_earned_tiers.py::test_the_presence_of_a_forced_step_is_still_tier_1` | the consumer's `because` threaded into `_satisfy_port` | failed | `'alignment.bam' not in 'required by the pipeline'` |
| 2026-08-15 | `test_earned_tiers.py::test_a_step_the_goal_asked_for_says_so` | the goal loop's `because` | failed | `'the goal' not in 'required by the pipeline'` |
| 2026-08-15 | `test_earned_tiers.py::test_a_tier_states_its_own_review_level` etc. | `Why.review_level` returning `ReviewLevel.NONE` | **nothing failed** | — this is the row worth keeping |
| 2026-08-15 | `test_earned_tiers.py::test_the_artifact_states_the_review_level_beside_the_tier` | the same, after the guard was written | failed | `assert <ReviewLevel.NONE: 'none'> is <ReviewLevel.ADVISORY: 'advisory'>` |

**`Why.review_level` was inert in code written the same hour, for a reason worth naming.**
`ResolvedValue.review_level` has computed the same thing since Plan 1, so the test written for
Task 7 Step 5 — `assert selection.review_level is ADVISORY` — passed against a field that already
existed and said nothing about the new one. **The new field is on `Why`, which is the model
`pipeline.yml` is made of and the one a stranger opens**, and every test in the new file stayed
green when it was reverted.

The replacement builds a real `Pipeline` and reads `step.why.review_level` and
`step.presence.review_level`. This is the fourth inert guard this plan has found by reverting, and
the second where the reverted code and the test were written within an hour of each other.

**A113's split shows up in the artifact, which is where it was always going to matter.** The
sorter now reads:

```yaml
  why:
    tier: 2
    reason: uncontested — nothing else in this stack fills bam_sorting
    review_level: none
  presence:
    tier: 1
    reason: nf-core/subread/featurecounts@2.0.6 requires 'alignment.bam' here
```

Two questions that were one field, and the tier is what made the conflation visible: *"the only
contract that produces this"* claimed the inputs forced a choice, when what forced it was the
contents of the registry. Install a second sorter tomorrow and the same pipeline becomes a real
choice — which is the definition of a convention, not a structural constraint.

**`Step.presence`, not `Step.exists`.** The first name was a `Why` in a field that reads as a
boolean. The second matches `effect: presence` in the rule format, so the field a reader finds in
the artifact and the word they would write in a rule are the same word. `test_pipeline_totality`
is what forced the question — it keys on field *names*, so `exists` left `IRNode.presence` looking
uncarried.

**Three gates caught this task rather than one.** `test_pipeline_totality` found the missing home,
`test_a_schema_change_bumps_the_version` found the unbumped `SCHEMA_VERSION` (now 3), and
`test_a78_a_rule_row_that_justifies_nothing_is_refused` found that its own fixture had become a
`MD0313` case rather than an `MD0301` one — its `when: {}` row now exits at tier 2 and is refused
for a more specific reason. That last one is a fixture drifting under a new rule, which is the
same event Task 4 hit and is worth expecting once per task from here.

## Plan 1.15 Task 8 — a decision records the premise it rested on, version 3 (A108, A127)

| date | guard | what was reverted | what happened | message |
|---|---|---|---|---|
| 2026-08-15 | `test_resolve.py::test_tier_3_rule_sets_value_and_marks_advisory` | `premise=pin.premise` on a resolved **param** | **nothing failed** | — see below |
| 2026-08-15 | the same, after the guard was written | the same line | failed | `assert [] == [('strandedness', 'reverse', <PremiseOrigin.ASSERTED>)]` |
| 2026-08-15 | `test_pipeline_file.py::…states_the_premise_value_not_the_predicate` (+2) | `reason_line`'s premise clause | **3 failed** | `'read_length is 150' not in 'rule implementation:alignment: STAR's seed-and-extend…'` |
| 2026-08-15 | `test_pipeline_file.py::…records_the_premise_it_rested_on` (+5) | `_premises_read` recording nothing | **6 failed** | `assert [] == [('read_length', 150)]` |
| 2026-08-15 | `test_pipeline_file.py::…records_the_premise_it_rested_on` (+3) | the origin hardcoded to `measured` | **4 failed** | `assert <PremiseOrigin.MEASURED> is <PremiseOrigin.ASSERTED>` |

**Two paths carry a premise and only one had a guard.** A selection's premise travels through
`RouteStep.selection_premise` in the router; a param's travels through `Pin.premise` in
`_resolve_param`. Every test written for this task read `star_align.why` — a *selection* — so
reverting the param line left all of them green. The two are different code paths reaching
different fields, and a task that adds both needs a guard on both.

**One revert was invalid and is recorded as such.** Hardcoding the origin to
`PremiseOrigin.MEASURED` referenced a name `rules.py` does not import, so the module failed to
import and 46 tests **errored**. A guard that "fails" because the module will not load has not
been watched — the same finding Task 0 recorded, now twice in one plan. Redone with a literal
`"measured"`, which pydantic coerces, and the corrected row is the one above.

**The plan's field shape is unrepresentable, and the guard said so in three sentences.**
`premise: dict[str, Any]` beside `premise_origin: dict[str, str]` was refused by
`tests/test_egress.py` as a mapping, as an `Any`, and as a bare `str` key — `Why` is reachable
from door 4, publication, the door with no undo. One `PremiseRecord` carrying id, value and
origin is the better shape regardless: two parallel mappings can disagree about their key sets
and nothing would notice.

**What the artifact says now**, which is the whole point of the task:

```yaml
  why:
    tier: 3
    reason: 'rule implementation:alignment where read_length is 150, asserted, not measured:
      STAR''s seed-and-extend search is built for long reads…'
    premise:
    - id: read_length
      value: 150
      origin: asserted
```

It said `matched {'read_length': '>= 70'}` — a Python dict repr embedded in YAML with doubled
quotes, reporting the **predicate** and never the value. A reader learned the rule tested `>= 70`
and never learned that `read_length` was 150, or that nothing had measured it. Both forms ship:
the sentence for a person, the records for `ProfilePolicy` (issue #2). Shipping only the mapping
would have repeated, one level up, the exact defect this plan exists to fix.

## Plan 1.15 Task 9 — completeness is checked against the declared domain (A124)

| date | guard | what was reverted | what happened | message |
|---|---|---|---|---|
| 2026-08-15 | `test_rules.py::test_a_gap_in_an_ordered_domain_is_refused` (+2) | the `_check_exhaustive` call | **3 failed** | `DID NOT RAISE RuleValidationError` |
| 2026-08-15 | `test_rules.py::test_a_gap_in_an_ordered_domain_is_refused` | the interval comparison, always `None` | failed | `DID NOT RAISE` |
| 2026-08-15 | `test_rules.py::test_an_extensible_enum_still_needs_a_catch_all` | the `measurement.extensible` branch | failed | `DID NOT RAISE` |
| 2026-08-15 | `test_rules.py::test_an_enum_missing_a_value_is_refused` | the missing-values raise | failed | `DID NOT RAISE` |
| 2026-08-15 | `test_rules.py::test_rows_over_several_premises_are_not_checked_for_completeness` | `_sole_premise`'s `any(len(row.when) > 1 …)` clause | **nothing failed** | — the clause is unreachable |
| 2026-08-15 | the same test (+2) | `_sole_premise`'s `len(tested) != 1` guard | **3 failed** | `MD0311` refusing a legitimate two-premise table |

**An unreachable condition, found the same hour it was written.** `_sole_premise` read
`if len(tested) != 1 or any(len(row.when) > 1 for row in rows)`, and the second clause cannot be
true when the first is false: a row carrying two keys puts two facts in `tested`, so the length
check already catches it. Reverting it changed nothing. Deleted rather than kept as reassurance —
**an unreachable condition reads to the next person as a case somebody thought about**, which is
worse than its absence. Same shape as `stack()`'s `origin[key] != layer.index` in Plan 1.9, and
the fifth time this repository has found one by reverting.

The corrected revert, against the clause that does the work, refuses a legitimate two-premise
table and fails three tests — including one that exists only to pin that this is *out of scope*
rather than approximated.

**Six shipped fixtures were incomplete tables**, in four files. That is the largest fixture
consequence of any task in this plan, and it is the finding rather than an inconvenience: every
one of them was a rule that answered part of its premise's domain and demoted silently to tier 4
for the rest. `test_resolve.py`'s strandedness rule answered `reverse` and neither of the other
two declared values; three audit-regression fixtures tested `>= 70` with nothing below it.

**Completing them did not break the one test that needs a miss.**
`test_rule_miss_demotes_to_tier_4_and_flags` carries an *empty* profile, so every row fails its
own predicate whatever the table covers. A complete table and a miss are different things, which
is exactly the distinction `MD0311` exists to keep — and it was worth checking rather than
assuming, because a completeness check that made misses unreachable would have removed tier 4's
own test.

**The obvious fix would have been worse than the defect**, which is why the check reads the
declared domain rather than demanding a catch-all. A catch-all tests no premise positively, so it
earns tier 2 under `MD0313` — demanding one on every decision would have demoted the shipped
aligner rule's last branch from tier 3 to tier 2 and taken Kim et al. 2019 with it. A124 asking
for completeness and §6.1 asking for a premise are in tension, and the declared domain is what
resolves it.

## Plan 1.15 Task 10 — a param declares its domain, so a computed `then` is a type error (A118)

| date | guard | what was reverted | what happened | message |
|---|---|---|---|---|
| 2026-08-15 | `test_rules.py::test_a_then_outside_the_params_domain_is_refused` (+1) | the `domain is not None` branch | **2 failed** | `DID NOT RAISE RuleValidationError` |
| 2026-08-15 | `test_rules.py::test_a_then_outside_a_declared_range_is_refused` | `ParamDomain.refuse`'s maximum check | failed | `DID NOT RAISE` |
| 2026-08-15 | `test_rules.py::test_a_computed_then_on_an_undeclared_param_is_still_refused` | `_computed_over`, as though a domain replaced it | failed | `DID NOT RAISE` |
| 2026-08-15 | `test_rules.py::test_two_implementations_disagreeing_about_a_domain_fall_back` | `_domain_of`'s unanimity check, taking the first | **nothing failed** | — no fixture had two disagreeing domains |
| 2026-08-15 | the same, after the guard was written | the same | failed | `MD0300` refusing a value legal for the other implementation |

**The unanimity branch had no fixture that could reach it**, which is the sixth inert guard this
plan has found by reverting. Two implementations of one role declaring *different* domains for
one parameter is the case `_domain_of` exists to handle, and nothing in the tree had two — so
`return first` passed everything. The replacement adds a second quantifier declaring
`strandedness` as `[yes, no, reverse]` where featureCounts declares it as `0..2`, which is a real
disagreement between two real tools rather than a contrived one.

Taking the first would decide which contract is right by **load order**, in the one place where
getting that wrong refuses a legitimate rule rather than merely reordering output. Falling back to
the heuristic refuses less and invents nothing. Refusing the disagreement outright would be
stronger, needs a code of its own, and is carried rather than smuggled in.

**`_computed_over` is kept, and the third row is why.** Most contracts declare no domain — one of
the five shipped params deliberately declares none, because the list of sequencing platforms
cannot be enumerated — so retiring the heuristic would trade it for nothing. The negative that
keeps it honest survives too: `paired` is a declared measurement, so a substring test would refuse
`paired-end`, a legitimate value killed by a check nobody could disable.

**A fixture's `then: 99` became illegal**, which is the check working on its own test suite:
featureCounts' `-s` takes 0, 1 or 2, and the row-order fixture had been using 99 as an arbitrary
sentinel. It reads better as 2-then-1 anyway, since the point is that the *first* matching row
wins.

**And an overlay fixture had one value in common with the base again.**
`test_a_higher_layer_replaces_a_whole_decision_block` was repaired in Task 9 to discriminate on
three distinct values; narrowing the domain to 0–2 collapsed `forward` back onto the base's value.
Rotated, so all three differ. Twice in two tasks for the same test, which is what a fixture
carrying its discriminator implicitly costs.

**YAML 1.1 parses bare `yes` and `no` as booleans**, and htseq-count's actual spelling of
strandedness is `yes`/`no`/`reverse`. The fixture failed with *"Input should be a valid string,
input_value=True"* until they were quoted — a real trap for a contract author, so the quoting
carries a comment rather than looking like a style choice.

## Plan 1.15 Task 11 — the corpus wired in, the format retired, drift green (A75, issue #36)

| date | guard | what was reverted | what happened | message |
|---|---|---|---|---|
| 2026-08-15 | `test_rule_corpus.py::test_a_coded_refusal_tells_the_reader_how_to_read_it` (+1) | `_with_pointer` returning the message unchanged | **2 failed** | `'run: mendel explain MD0306' not in …` |
| 2026-08-15 | `test_rule_corpus.py::test_the_corpus_rule[R20]` | `EXPECTED["R20"]` set to a code nothing emits | failed | the expectation discriminates |
| 2026-08-15 | `test_rule_corpus.py::test_every_attempt_has_a_rewrite_…` (+1) | `rules/R11.yml` deleted | **2 failed** | a rewrite going missing is caught |
| 2026-08-15 | `test_rule_corpus.py::test_the_corpus_rule[R17]` | a rule file emptied to `version: 1` | **nothing failed** | — this is the row worth keeping |
| 2026-08-15 | the same, after the guard was rewritten | the same | failed | `R17 declares nothing, which is the dead-rule pathology itself` |

**A seventh inert guard, and it was in the test written to prove the format works.** The corpus
test asserted `loaded.rules.decisions or loaded.rules.derivations` — which the *shipped registry's
own rule* satisfies. Emptying a corpus rule file to `version: 1` left it green: the fixture
contributed nothing and the base layer answered on its behalf.

The first repair was also wrong. Counting entries and requiring the count to rise fails R01 and
R12, which legitimately **replace** the shipped `implementation:alignment` block — an overlay
replacing a base decision is invariant 11 working, not a defect. The assertion that holds is that
every key the rule *file* claims is in force **and the corpus layer is what decided it**, with the
keys read from the file rather than from the loader: asking the loader which keys it loaded and
then asserting it loaded them is a tautology.

**Two reverts that were not reverts.** Weakening `assert expected in str(caught.value)` to
`assert caught`, and `assert attempts == written` to `assert attempts or written`, both left every
test green — as they must, because weakening an assertion cannot fail unless what it asserts is
already false. **A revert has to break the subject, not the claim about it.** Redone against the
subject: a wrong expected code, and a deleted rewrite.

**And one attempted revert was rejected as invalid before it was recorded.** Renaming R01's role
consistently in both the rule and its target left the test green, and correctly: the property is
that the table agrees with the file, and a consistent rename keeps them agreeing. A revert that
does not contradict the property is not evidence about the guard.

**`check_registry_drift.py` could not see the fifth kind.** Its `KINDS` was the literal
`("contracts", "measurements", "rules", "vocabularies")`, so `roles/` was invisible — the check
would have reported no drift *because it was not looking*, with a green line to say so. Derived
from `DeclaredKind` now. **Third literal of this shape the repository has had to fix** in one
plan: `registry.yml:kinds` in Task 1, `_every_file_is_claimed`'s message in Task 0, and this.

**One edit landed in the wrong checkout.** The shell's working directory reset to the main
checkout after a `cd` into the registry repository, and the next edit went there. It was caught
by `make drift` reporting *"no drift: 27 shared files agree"* — impossible in the worktree, where
fifteen files differed — and reverted with `git checkout`. Recorded because the *symptom* was a
gate turning green, which is the one direction nobody investigates.

## Round four's carried findings, closed 2026-08-15 (issues #24–#36)

| date | guard | what was reverted | what happened | message |
|---|---|---|---|---|
| 2026-08-15 | `test_purity.py::test_an_aliased_dynamic_importer_is_caught` | the alias resolution before matching `DYNAMIC_IMPORTERS` | failed | an aliased importer obtained `urllib` with the scan green |
| 2026-08-15 | `test_purity.py::test_a_stdlib_transport_is_banned` ×6 | the six added prefixes | **6 failed** | `logging.handlers`, `poplib`, `imaplib`, `socketserver`, `multiprocessing`, `wsgiref` |
| 2026-08-15 | `test_construction.py::test_an_assignment_alias_is_resolved` (+2) | the assignment/subclass/fixpoint arms of `_aliases_of` | **3 failed** | `_P = Pipeline` denoted the class without an import-as |
| 2026-08-15 | `test_purity.py::test_every_package_is_classified` | a package name removed from all three lists | failed | a package the file has never heard of is one it is not guarding |
| 2026-08-15 | `test_egress.py::test_an_enum_with_a_missing_hook_…` (+1) | the `_missing_` check | **2 failed** | an open vocabulary passed as a closed one |
| 2026-08-15 | `test_egress.py::test_every_publication_payload_model_is_frozen` | `frozen=True` on the publication graph | failed | `Emitted.files[0].digest` reassignable after review |
| 2026-08-15 | `test_egress.py::test_a_declared_id_alias_refuses_free_text` ×9 | each new `AfterValidator` | **9 failed** | a patient identifier as a `node_id`, notes as a `state` |
| 2026-08-15 | `test_pipeline_totality.py::test_every_carried_field_is_where_it_says` | `ModuleRef.digest` deleted | failed | **A68's own reproduction**, which used to be green |
| 2026-08-15 | `test_pipeline_file.py::test_a_pipeline_defect_blames_the_pipeline_file` (+1) | the `_PIPELINE_MODELS` branch in `_blame` | **2 failed** | a `steps:` defect reported as *"this goal is not valid"* |

**Two findings the fixes produced, both from adding a validator to something that never had one.**

`Measurement.describes` was annotated `MeasurementId` and holds a **type id** — `fastq.reads` —
and nothing noticed because neither alias validated anything. A64's validators failed on the
first load. **Two declared aliases that accept the same strings are two labels**, and a label on
the wrong kind of value is exactly what invariant 14's *"a declared ID alias"* was meant to rule
out.

`Displacement`'s keys have now been broken by **two** borrowed aliases. Its docstring already
recorded the first: `list[ContractId]` until root C gave that a validator, at which point it
refused the synthetic keys `test_layered.py` stacks. It became `Subject`, and A64 gave that one a
validator too. Twice is the argument for its own alias, so `AnyKey` says what is true of every
kind's key and nothing more — no whitespace, no control character, not empty.

**A66 is scoped to the door it is about, and the scoping is the finding.** "Every payload model
should be frozen" is right for door 4 and wrong for door 3: `RepairRequest.ir` is handed to a
model *so that the IR can change*, and invariant 5 says repair patches the IR and re-emits.
Freezing the IR broke 109 tests, which is the resolver saying the same thing less politely. The
publication graph is frozen; `BUILDERS` names the five that are not, and a sixth cannot join them
quietly.

**A68's second reproduction is acknowledged rather than closed**, and that is the honest outcome.
Deleting a field from a type `Pipeline` carries *verbatim* is invisible to a totality check by
construction — the field is defined once and read once, so removing it removes the question along
with the answer. What that probe tests is "did somebody mean to delete this", which the tests that
*read* the field are where to ask. The 60% figure it reports is now 0% of what this file claims to
cover, instead of 60% of what it appeared to.

**A62's `model_copy` entry was added and then removed.** It does build an instance without
re-validating, but it is an *instance* method, so `<ClassAlias>.model_copy` — the only shape this
scan matches — is not valid Python. An unreachable entry reads to the next person as a case
somebody covered. Same call as Plan 1.15 Task 9's `_sole_premise` clause, and a test pins the
removal so it cannot be re-added without reading why.

**A69 closed by becoming countable.** Its complaint was that the residue was tracked per *file* —
46 of 47 covered, reading as nearly done — when the condition is per *guard*. `make residue`
counts it per guard, derived from the ledger and the test files rather than asserted in prose,
which is the same move `DeclaredKind` made for the kind count. `CLAUDE.md` states the method and
deliberately does not state the number.

## Issues #38 and #39, closed 2026-08-15

| date | guard | what was reverted | what happened | message |
|---|---|---|---|---|
| 2026-08-15 | `test_premises.py::test_a_transform_computes_a_fact_from_a_measurement` (+3) | the `transform` branch in `_derive` | **4 failed** | the chain never runs |
| 2026-08-15 | `test_premises.py::test_a_transform_rounds_to_its_declared_kind` | the coercion to `kind` | failed | `15.79` where an integer was declared |
| 2026-08-15 | `test_premises.py::test_a_transform_over_a_cohort_reduces_it_first` | the `MD0314` refusal | failed | arithmetic over `[150, 100]` |
| 2026-08-15 | `test_measurement_vocabulary.py` ×3 | the check weakened rather than the data | **nothing failed** | — see below |
| 2026-08-15 | `test_measurement_vocabulary.py::…declares_whether_a_tool_can_produce_it` | `assertion_only` removed from `strandedness.yml` | failed | nothing produces `measurement.strandedness` |
| 2026-08-15 | `Measurement._assertion_only_says_why` | `assertion_only_because` removed from `purpose.yml` | failed | `MD0315`, at load |
| 2026-08-15 | `test_measurement_vocabulary.py::test_every_measurement_cites_something` | `cite` removed from `genome_length.yml` | failed | a claim about the world with no source |

**A revert has to break the subject, not the claim about it — and this is the second time in
one day.** The first attempt weakened `if not measurement.assertion_only and …` to `if False`
and everything stayed green, as it must: weakening an assertion cannot fail unless what it
asserts is already false. The subject of these guards is the **registry data**, so the reverts
that mean anything edit a `.yml`.

**What issue #38 predicted, measured.** Five of the six measurements the registry shipped
cannot be measured by anything in it — including `strandedness`, which becomes featureCounts'
`-s 2` and is this repository's own worked example of the tier-3 mechanism working. That is not
a defect in any of them; it is exactly what the `sealed` protection profile exists to act on,
and it was written down nowhere a reader would find it. Each now says *why*, in terms somebody
can act on: measurable-and-not-vendored is a contract away, and not-measurable-at-all is a
research question.

**The flag alone would not have been enough**, which is why the reason is required. A reader
cannot tell "no tool exists for this" from "the tool exists and nobody has vendored it", and
those are different amounts of work. §4.7's rule applied to a boolean.

**Issue #39's shape is the argument, not the feature.** A `transform` is a chain of *named
unary operations with a literal operand*, left to right. There is no parser, no precedence, and
no way to reference a second fact — which is the one thing a general expression language would
buy and the thing that turns a rule table into a program.
`docs/design/rule-tables-and-port-logic.md` §13.2 asked for arithmetic without reintroducing a
solver, and this satisfies both halves. R02 and R03 in the corpus are what it is for, and they
load now.

**`math` joined `mendel-resolver`'s purity allowlist**, the third such addition and argued the
same way. Every function in it is a pure number-to-number map, which is the strongest form that
argument takes anywhere on the list. The alternative — hand-rolling `log2` from
`int.bit_length()` — was rejected because it is only correct for integers and `genome_length / 2`
is not one; a wrong number reaching STAR's `--genomeSAindexNbases` is the class of defect A118
is about.

## Issue #41 Task 1 — five packages by lifecycle stage

| date | guard | what was reverted | what happened | message |
|---|---|---|---|---|
| 2026-08-16 | `test_construction.py::test_data_profile_is_constructed_in_one_place` | nothing — `measurement.py` moved to `declared/` | **failed unprompted** | the two permitted spellings in `MeasurementRegistry.profile` reported as violations |
| 2026-08-16 | `test_purity_runtime.py` ×2 | nothing — `ir.py` and `layered.py` moved | **failed unprompted** | `…/comeni_core/ir.py` does not exist; `layered.py did not execute under the armed hook` |
| 2026-08-16 | `test_generated_types.py::test_the_committed_stub_matches_the_declarations` | nothing — `profile.pyi` moved | **failed unprompted** | `profile.pyi is stale` |
| 2026-08-16 | `test_architecture.py::test_every_path_architecture_names_exists` | a named path pointed at `comeni_core/nowhere/` | failed | names the path that does not exist |
| 2026-08-16 | `test_architecture.py::test_the_five_packages_are_all_named` | `comeni_core/spell/` renamed in the document | failed | names the package the document stopped mentioning |

**A67's shape, live, in the first task that could produce it.** `test_construction.py` exempts
named spellings *by path*, and `MeasurementRegistry.profile()` — the one validating constructor
— is one of them. Moving `measurement.py` into `declared/` made the exemption match nothing, so
the guard fired on the code it exists to permit. **That direction is the lucky one**: the same
rename in `PIPELINE_READERS` would have made an exemption *cover nothing* and the scan would
have gone quiet, which is the failure A67 describes and the one nobody investigates.

Four guards failed unprompted for one cause, and none of them was found by reading. `make check`
found all four in one run, which is the argument for running the whole gate on a change that
looks confined to import lines.

**A plan defect, corrected on execution.** Task 1 Step 6 says "run everything, expect PASS" and
Task 5 was to repair these paths. A task cannot end green if a later task fixes what it breaks,
so the path repairs moved into Task 1 and Task 5 keeps the guard-of-the-guard and the deliberate
reverts. Recorded rather than silently reordered.

**Ruff reordered a generated file.** `profile.pyi`'s imports came out unsorted after the
rewrite, and fixing the *file* would have been undone by the next `generate_types.py` run —
`make types` and `make lint` would have disagreed forever, each correct. Fixed in the
generator's header instead.

## Issue #41 Task 2 — `pipeline.py` was doing three jobs

| date | guard | what was reverted | what happened | message |
|---|---|---|---|---|
| 2026-08-16 | `test_construction.py::test_pipeline_is_constructed_in_one_place` | nothing — `Pipeline.of`'s body moved to `materialise.of` | **failed unprompted** | `these construct one directly: …/materialise.py:83` |
| 2026-08-16 | the same | `materialise.py` removed from `PIPELINE_ALLOWED` | failed | the same message |
| 2026-08-16 | `test_construction.py::test_the_only_caller_of_materialise_of_is_pipeline_of` | `from comeni_core.artifact import materialise` added to `pipeline_file.py` | failed | names the file that reached past `Pipeline.of` |

**The guard caught the split within the hour, which is the guard working.** Moving `Pipeline.of`'s
body out of the class's own module put the `Pipeline(...)` call outside `PIPELINE_ALLOWED`, and
the scan said so immediately rather than after the artifact had been wrong for a plan.

**The exemption is the file, not a spelling — and that moves the question rather than answering
it.** `materialise.py` *is* the materialisation, so exempting one spelling in it would be
pretending it is a reader that happens to need a constructor. What the file exemption gives up is
the assurance that nothing else reaches `materialise.of` and skips `Pipeline.of` entirely, so a
second guard holds that: the only importer of `materialise` may be `pipeline.py`.

**That second guard's first version was prose-matching and named three innocent files.** It
searched the file text for `materialise` and found `load.py`, `contract.py` and a package
`__init__` that mention materialisation in a *docstring*. A guard whose output is mostly prose is
a guard people stop reading, so it parses imports now. Recorded because the failing-first version
looked plausible — three plausible names is exactly how a bad guard survives review.

**`_no_flags_why` went to `materialise.py` and came back.** It is a *model default* —
`Step.ext_args` calls it in a `default_factory` — so it belongs with the model, and ruff's
`F821` said so before any test ran. The line between "builds a model" and "is part of a model's
declaration" is not where the section headings suggest.

## Issue #41 Task 3 — `rules.py` splits into format, table and validate

No guard failed and none was reverted, which is the honest entry: this is a **package
boundary** change and `rules/__init__.py` re-exports every name the nineteen importers use, so
nothing outside the package could observe it. The evidence is the whole suite passing with zero
callers edited, plus the three digests unmoved.

**Two constants moved between the split modules, and ruff found both before any test ran.**
`_GOAL_FACTS` went to `format.py` because both `table.check_premise_names` and
`validate._check_when` read it and it is part of what a `when` may name; `_ORDERED` went to
`validate.py` because only the validator asks whether a comparison is meaningful over a kind.
Neither placement was in the plan, and `F821` is what made the question concrete.

**`_comparison` and `_computed_over` are re-exported as `X as X` and left out of `__all__`.**
They are private and two test files reach them — `test_rules.py` for the comparison predicate,
`test_audit_regressions.py` for A118's computed-`then` check. The redundant alias tells ruff the
import is deliberate; the absence from `__all__` says it is still not public. Inventing public
names for them to satisfy a linter would have been the linter designing the interface.

## Issue #41 Task 4 — `cli.py` splits by what a verb does to a pipeline

| date | guard | what was reverted | what happened | message |
|---|---|---|---|---|
| 2026-08-16 | `test_conformance_cli.py` ×2, `test_end_to_end.py::test_output_is_identical_across_hash_seeds` | nothing — `cli` became a package | **failed unprompted** | `'mendel_compiler.cli' is a package and cannot be directly executed` |
| 2026-08-16 | `test_publish.py` ×2, `test_pipeline_file.py`, `test_audit_regressions.py` ×2 | nothing — `run_gate`'s callers moved | **failed unprompted** | the gate ran for real; `assert 0 == 1` |

**Two consequences the oracle could not have caught, and both are worth naming.**

**A package is not executable with `-m`.** Four tests run `python -m mendel_compiler.cli` — one
needs a subprocess because it sets `PYTHONHASHSEED`, the others want the real exit code — and
`cli/__main__.py` is what restores that. The console script in `pyproject.toml` points at `main`
directly and never reaches it, so **the entry point everybody actually uses was fine the whole
time**. A refactor can break an interface only the tests use, and that is not a reason to
dismiss it: `-m` is a documented way to run a Python package and something relied on it.

**Splitting a module moves the seam a test patches.** `monkeypatch.setattr(cli, "run_gate", …)`
patched a name nothing reads any more — `run_gate` is looked up in the module that *calls* it.
That is `CLAUDE.md`'s own gotcha arriving from the other side: *"import modules, not symbols,
where tests monkeypatch"* is advice to the code, and this is what it costs the test when the
module the code lives in moves.

**And one test needed two patches where one had done.** `test_a4_a_failed_gate_publishes_nothing`
builds and then publishes, and those verbs are now in different modules — `resolve_verbs` runs
the gate at the end of a build, `artifact_verbs` runs it when certifying a directory that
already exists. One `setattr` covered both while they shared a file, which meant **nothing
recorded that the gate is invoked from two places.** The split made a fact about the code visible
in a test that had been silently averaging over it.

## Issue #41 Task 5 — a guard that names a path must name one that exists

| date | guard | what was reverted | what happened | message |
|---|---|---|---|---|
| 2026-08-16 | `test_construction.py::test_every_exempted_path_names_a_file_that_exists` | an `ALLOWED` key pointed at the pre-move path | **2 failed** | names the path that exempts nothing, *and* the guard it stopped exempting |
| 2026-08-16 | the same | a `PIPELINE_READERS` key misspelled | **2 failed** | the same pair |
| 2026-08-16 | `test_purity.py::test_the_attribute_exemption_names_a_file_that_exists` | `ATTRIBUTE_EXEMPT_PATH` pointed at a path `yaml_strict.py` does not have | **3 failed** | the exemption covers nothing, and `yaml_strict.py` fails the rule it exists to satisfy |
| 2026-08-16 | `test_purity_runtime.py::test_every_required_frame_path_names_a_file_that_exists` | a required frame path pointed at the pre-move path | failed | *"requires files that do not exist, so it can only fail"* |

**Every one of the four failed *two* tests, and that pairing is the point.** The new guard names
the broken key; the old guard fails for a reason that reads like something else entirely. Before
Task 5 only the second half existed, so an operator would have seen
`test_pipeline_is_constructed_in_one_place` fail on code that has been correct for months and
gone looking in the wrong file.

**The runtime one is the exception, and it is the dangerous shape.** A required frame path that
names nothing makes the assertion **unsatisfiable** rather than unmet — it fails for a reason
that has nothing to do with coverage, so the message *"the watched region has narrowed"* is
false, and a reader debugging it is debugging the wrong thing. Its new guard is what says the
real reason.

**A67 is now closed in both directions.** Task 1 hit it live in the safe direction — an exemption
stopped matching and a guard fired on permitted code, which somebody notices. These four cover
the other direction, where an exemption covers nothing, the scan quietly finds less to check, and
the gate goes green faster.

## Issue #41 Task 6 — the working notes leave `docs/`, and links are checked

| date | guard | what was reverted | what happened | message |
|---|---|---|---|---|
| 2026-08-16 | `make links` | a link in `docs/README.md` pointed at `../notes-nowhere/` | failed, exit 2 | `docs/README.md -> ../notes-nowhere/` |
| 2026-08-16 | `test_architecture.py::test_no_document_or_tool_still_says_docs_internal` | `guard_residue.py`'s ledger path put back to `docs/internal` | failed | names the tool |
| 2026-08-16 | `test_architecture.py::test_no_document_or_tool_still_says_docs_internal` | a link in `docs/README.md` put back to `docs/internal/` | failed | names the document |
| 2026-08-16 | `test_architecture.py::test_no_document_or_tool_still_says_docs_internal` | `scanned = ()` — the roots emptied | **passed, then failed** | see below |
| 2026-08-16 | the same | a `docs/` link put back to `docs/internal` | failed | names the document |
| 2026-08-16 | the same | its skip filter put back to `set(path.parts)` | **passed** | — the proof it was inert |

**The new guard was inert when written, and the last row is how that was established.** Its skip
filter read `{".venv", ".git", ".worktrees", …} & set(path.parts)`, and **this repository's plans
are executed in `.worktrees/<name>/`** — so every path contained `.worktrees` and the scan
skipped the entire repository. It reported zero and passed, *including on the file that holds the
string it searches for*.

That is the same defect as `make drift`'s `REGISTRY ?= ../comeni-registry`, which resolved to
`.worktrees/comeni-registry` and printed "skipped": **a check written against the repository root
is a check that does nothing in the one place `CLAUDE.md` requires the work to happen.** Twice
now, in two plans, from two different authors of the same mistake. Skipping is by position under
`root` rather than by `path.parts`.

**And a tool's stale path survived the move with nothing to catch it.**
`tools/guard_residue.py` built its ledger path from segments — `ROOT / "docs" / "internal" /
"audits"` — which a `docs/internal/` text substitution cannot see, and `make residue` is not a
gate. The test above covers both spellings for that reason.

**`make links` was written and run *before* the move**, which is what makes its six-link report
afterwards attributable. A checker introduced after a repair can only confirm the repair somebody
already believed in.

**The guard scans named roots and asserts it reached them, because the first version could be
switched off by emptying one tuple.** It scanned everything under `root` and filtered `notes/`
out by exemption; setting `scanned = ()` — or, before that, any filter that happened to match —
left a scan of zero files reporting zero findings and passing. `assert len(paths) > 100` is what
makes the empty scan loud, and reverting the roots now fails with *"the scan reached only 7
files; it is not scanning"* rather than green.

**`notes/` is not scanned at all**, which is a scope decision rather than an exemption pile: the
record legitimately names things that no longer exist, and the row directly above this paragraph
says `docs/internal` correctly and for ever. Same reasoning as `make links`, which does not
check `notes/` either. Three files were exempted individually before this; two of them were the
record doing its job, and only `test_architecture.py` — which holds the string it searches for —
is a genuine exception.

| 2026-08-16 | `make docs` (`generate_diagnostics_doc.py --check`) | a heading hand-edited in `docs/reference/diagnostics.md` | failed | *"is stale — run: …"* |

**The edit was to the header, which the previous version could not have seen.** Until Task 7 the
generator spliced a table between `BEGIN`/`END` markers inside `docs/reference/cli.md`, and
`rendered()` read the surrounding text back out of the file it was about to compare against — so
everything outside the markers was equal to itself by construction. A hand-edited heading, band
table or explanatory paragraph was preserved and reported fresh. The whole page is generated now,
and the row above is that difference watched.

| 2026-08-16 | `test_a4_publishing_records_the_gate_that_actually_ran` | the `artifact_verbs` patch removed, with `nextflow` shadowed by a stub that exits 127 | failed | `assert 1 == 0` |

**This one was green locally for the wrong reason, and CI is what said so.** The `cli.py` split
moved `publish`'s gate call into `artifact_verbs`, and the test went on patching only
`resolve_verbs` — so `publish` ran the *real* gate. On a developer machine `nextflow` is on PATH
and the real gate passes, so `make check` was green; on CI it is not installed and the gate failed.
The sibling `test_a4_a_failed_gate_publishes_nothing` had already needed both patches, which is
what should have prompted checking this one.

**The revert above was watched under the CI condition rather than the local one**, by shadowing
`nextflow` with a stub that always exits non-zero. Running the whole fast suite that way found no
other test relying on a real Nextflow — the two in `test_gates.py` that fail under the stub are
correctly `skipif`-guarded and skip on CI, so the stub finding them is an artefact of
`shutil.which` seeing a file rather than a defect.

**The general shape, for the third time in this plan:** a check can pass because of something
about the machine it ran on. A67 is the version where a rename disables a guard; this is the
version where an installed tool does. `make check` being green is evidence about one environment.

## Issue #46 — the layer digest, after `registry/` became a submodule

| date | guard | reverted | result | message |
|---|---|---|---|---|
| 2026-08-16 | `test_digest.py::test_a_layer_digests_what_it_declares_and_not_what_git_leaves_beside_it` | `declared_entries` back to `path.rglob("*")` | failed | two digests differ |
| 2026-08-16 | `test_digest.py::test_a_symlinked_directory_is_refused_too` | the `root.is_symlink()` branch disabled | failed | no `ValueError` raised |
| 2026-08-16 | `test_digest.py::test_the_allowlist_did_not_make_the_digest_constant` | `registry.yml` dropped from the allowlist | failed | two layers with different manifests digest alike |

**The defect these were written for was found by comparing artifacts, not by a test.** Adding the
submodule put three entries beside the declared kinds — `LICENSE`, `README.md`, and a `.git`
*file* reading `gitdir: ../../../.git/worktrees/issues-43-46/modules/registry`. That path names
the worktree and the checkout location, so `digest_of_directory` — which walked `rglob("*")` —
made the **layer digest machine-dependent**. Two clones of the same pinned commit would pin
different digests, and `pipeline.yml` would record whichever machine ran the build.

**`make verify` was green the whole time**: 814 fast, 5 slow, 73 guards, no drift. Nothing in the
repository compares a digest across machines, and nothing compared `pipeline.yml` before and
after a change that was supposed to be a pure relocation. What caught it was building the spine
on both `main` and the branch and diffing the two artifacts — the same technique
`tools/refactor_oracle.py` used for issue #41, applied by hand a day after that tool was deleted.

**The closing check is stronger than the guards above**, and is worth repeating for any change
that claims to be a relocation: `pipeline.yml` built from the submodule is now **byte-identical**
to `pipeline.yml` built on `main`, layer digest included.

**The remedy is an allowlist, and the third row is why it needs its own guard.** Naming what a
layer *is* — `DeclaredKind` plus `registry.yml` — rather than listing what to skip means the next
thing a layer repository carries is covered without an edit. The failure mode of an allowlist is
that it covers too little and the digest quietly becomes constant, which is what row three
watches.

**One narrowing, recorded rather than absorbed:** a symlink outside a declared kind is no longer
refused. Nothing loads it and nothing digests it, so it cannot reroute a pipeline or move a
digest; A9's exploit was a symlinked *contract*, which lives under `contracts/` and is still
refused at both sites. A symlinked *kind directory* is still refused, and row two exists because
`is_dir()` follows a link — the allowlist written after A9 would otherwise have reintroduced it.

## Issue #46 — an unchecked-out submodule

| date | guard | reverted | result | message |
|---|---|---|---|---|
| 2026-08-16 | `test_registry_submodule.py::test_an_empty_layer_directory_names_the_submodule` | the refusal in `layers.load()` removed | failed | no `ValueError` raised |
| 2026-08-16 | `test_registry_submodule.py::test_a_layer_with_one_kind_is_not_mistaken_for_an_empty_one` | `any(` → `all(` | failed | a one-kind overlay refused as empty |
| 2026-08-16 | `test_registry_submodule.py::test_the_message_counts_the_kinds_rather_than_asserting_a_number` | the refusal removed | failed | no message to count in |
| 2026-08-16 | `make check`'s `registry-present` | `registry/` moved aside and replaced with an empty directory | **failed, in under a second** | the message below |

```
registry/ holds no registry data — it is a git submodule and was not checked out.

    git submodule update --init

'git clone --recurse-submodules' avoids this. See docs/guides/contributing.md.
```

**The last row is the one that mattered, and it is the hardest kind of state to test: one that
only ever occurs on somebody else's machine.** A contributor cloning without
`--recurse-submodules` gets a `registry/` that exists and is empty, so every path check passes
and the failure surfaces thirty-three times as missing contracts. The state was produced here by
hand — `mv registry /tmp/... && mkdir registry` — because otherwise the message would ship
unread, which is exactly A14's finding in its purest form.

**Two sites, one sentence.** `layers.load()` catches a direct `mendel build`; the Makefile
prerequisite catches `make check`, which is a contributor's first command and would otherwise
spend seventy seconds arriving at the wrong diagnosis.

**`any`, not `all`, and the second row is why that needs a guard.** An overlay carrying three
contracts and nothing else is the normal private-layer case; `all` would refuse every real
overlay while passing every test written against the public base, which has all five kinds.

| 2026-08-16 | `test_architecture.py::test_every_documented_clone_command_gets_the_submodule` | `--recurse-submodules` removed from README's quickstart | failed | names the file and line |

**It failed on its first run, before anything was reverted, and that is the point.** Issue #46's
prose was updated by hand and by grep, and two `git clone` lines survived both —
`docs/guides/contributing.md` and, worse, `docs/guides/getting-started.md`, which is the first
thing a stranger reads. Each would have handed a new user an empty `registry/`.

A guard that finds real offenders the moment it is written is a guard that was needed. Hand-fixing
prose finds the instances you thought of; the sentence a reader actually follows is elsewhere.

## A36 — `_FILE`'s domain separation, made checkable (2026-08-16)

| date | guard | reverted | result | message |
|---|---|---|---|---|
| 2026-08-16 | `test_digest.py::test_the_file_tag_separates_entry_kinds` | `_FILE = b""` | failed | *"the tag is empty, so it separates nothing (A36)"* |

**This is the assertion A36 said did not exist.** Round two set `_FILE` to `b""` and ran the whole
suite: 436 passed. A line that cannot be wrong reads exactly like a line that is untested, and
that is A14's thesis stated about one byte.

**The audit's option 1 — delete the tag — was priced out rather than argued down.** It said
changing `_FILE` is *"free today and expensive after the first lockfile a stranger holds"*.
`comeni-registry` is now published and tagged `v0.2.0`, and a layer digest is what a
`pipeline.yml` pins, so deleting the tag would move every layer digest in every existing artifact.
Option 3 — make the claim checkable — moves nothing, and is the only option that changes the tag's
status from asserted to tested.

**The second entry kind is invented in the test, not in the code.** Adding one to `digest.py` to
justify the separator would be building a feature to test a byte.

## Issue #49 — the loading stage refuses with a code (2026-08-16)

| date | guard | reverted | result |
|---|---|---|---|
| 2026-08-16 | `test_loading_diagnostics.py::test_MD0001_…` | `MD0001:` dropped from the message | failed |
| 2026-08-16 | `…::test_MD0002_…` | `MD0002:` dropped | failed |
| 2026-08-16 | `…::test_MD0003_…` | `MD0003:` dropped | failed |
| 2026-08-16 | `…::test_MD0004_…` | `MD0004:` dropped | failed |
| 2026-08-16 | `…::test_MD0005_…` | `MD0005:` dropped | failed |
| 2026-08-16 | `…::test_MD0006_…` | `MD0006:` dropped | failed |
| 2026-08-16 | `…::test_MD0007_…` | `MD0007:` dropped | failed |
| 2026-08-16 | `…::test_MD0008_…` | `MD0008:` dropped | failed |
| 2026-08-16 | `…::test_MD0009_…` | `MD0009:` dropped | failed |

**Two of these nine were green on their first run, before the codes existed, and the reason is
worth writing down.** `pytest` names `tmp_path` after the test that asked for it, so a refusal
quoting the layer path contains the literal string `MD0004` inside
`/tmp/pytest-of-…/test_MD0004_a_layer_contains_0/registry` — and `assert "MD0004" in message`
passed against a message with no code in it at all.

That is A68's shape exactly: **a guard comparing a name against itself.** `_refusal()` now scrubs
the layer path out of the message before returning it, so the assertion can only be satisfied by
a code the refusal actually carries.

**Every test also asserts the file name**, not only the code. Issue #49's whole complaint is that
a Pydantic error names a model class and a field path rather than a file; a code that named only a
model would be the same defect wearing a number.

**Six of the nine were existing refusals gaining a prefix**, not new logic — `MD0003` is A26's,
`MD0004` is A9's, `MD0009` is invariant 7's with A35's join. Only `MD0001` and `MD0002` are new,
and they wrap `kind.parse(path)` inside `stack()` because that is the one place every kind loads
through (invariant 11) and the only place the path is still in scope. `MD0005` is the refusal
issue #46 added yesterday as a bare `ValueError`.

## A130 — the artifact states that no model was consulted (2026-08-16)

| date | guard | reverted | result |
|---|---|---|---|
| 2026-08-16 | `test_ai_provenance.py::test_MD0225_…` | the `MD0225` block removed | failed |
| 2026-08-16 | `…::test_a_pre_ai_file_claiming_a_model_is_not_refused` | `== []` → `not self.ai.available` | failed |
| 2026-08-16 | `…::test_a_file_from_before_the_question_states_nothing` | `available: list \| None = None` → `list = []` | failed (two tests) |
| 2026-08-16 | `…::test_a_build_states_that_no_model_was_consulted` | `materialise` stops writing `ai=AiProvenance(available=[], used=[])` | failed (two tests) |

**The second and third rows are the finding, not ceremony.** `MD0225` refuses a value claiming a
model when the build says none was available — and the natural spelling, `if not
self.ai.available`, also fires on `None`, which means *"this file predates the question"*. That
would refuse every version-3 artifact for contradicting a statement it never made. `== []` is the
whole difference, and row two is what holds it.

Row three is the same distinction one level up: defaulting `available` to `[]` turns absence into
a statement, so an old file would load as *"somebody looked and nothing was wired"* when nobody
looked. **This is `MD0223`'s lesson (`for_value is None` means "written before 1.14", not
"disagrees") arriving in a second field**, which is why the spec called it out before the code
was written rather than after.

**Four totality guards caught the new model on the way in**, and each is a guard doing its job
rather than an obstacle: `SERIALISED_SHAPE`, the `Pipeline` field list, `_PIPELINE_MODELS` (so a
malformed `ai:` is blamed on the pipeline file rather than the goal), and the two
`set(raw) == {...}` assertions in `test_pipeline_file` and `test_publish`. A new section of the
artifact has to be declared in five places, and all five said so.

## Issue #48 — `MD0223` sees an answered tier-4 setting (2026-08-16)

| date | guard | reverted | result |
|---|---|---|---|
| 2026-08-16 | `test_pipeline_file.py::test_MD0223_sees_a_tier_four_setting_answered_by_hand` | the whole `#48` branch removed | failed |
| 2026-08-16 | `…::test_an_unanswered_tier_four_setting_is_not_flagged` | the `key in answered` condition dropped | failed, **and eleven others with it** |
| 2026-08-16 | `…::test_human_source_with_a_matching_override_is_accepted` | the `Tier.AMBIGUOUS` condition dropped | failed |

**Three conditions, three different tests, and none of them is decoration.** Dropping
`key in answered` turns the check into a nag that fires on every *unanswered* tier-4 setting —
which is correct output saying "please review" — and eleven tests failed, because that is the
state a normal build is in. Dropping the tier condition flags any pre-1.14 field. Dropping the
branch loses the finding.

**Two existing tests refused after the fix, and both were completing a premise rather than
absorbing a regression.** `test_human_source_with_a_matching_override_is_accepted` said *"the
value, the `human` source and the decision's override all agree — a person answered, and the
record proves it"* — while leaving `why.reason` reading *"no rule covered … please review"*. The
record did not prove it, and that is issue #48 stated as a docstring nobody had re-read.
`_with_override` in `test_upgrade.py` had the same shape: it claimed to answer *"the way a
reviewer would"* and answered half.

**The behaviour change is user-visible and is documented rather than left to be discovered.**
Answering a tier-4 question is now a two-part edit — `override_reason` in `decisions:`, and the
setting's own `why.reason` and `why.for_value` — and the one-part edit exits 2.
`docs/guides/driving-mendel.md` §6 was written when the one-part edit worked and now shows the
refusal and the cure.

## Release automation — the action pins (2026-08-16)

| date | guard | reverted | result |
|---|---|---|---|
| 2026-08-16 | `test_workflow_pins.py::test_every_action_is_pinned_by_commit_sha` | `@v7` in place of the SHA | failed, naming file and value |
| 2026-08-16 | `…::test_every_pin_carries_the_version_it_came_from` | the `# v7.0.1` comment dropped | failed, naming file and line |
| 2026-08-16 | `…::test_there_are_workflows_to_check` | — | asserts the scan reached ≥2 workflows and ≥8 `uses:` |

**The third row is not ceremony.** A scan that reaches nothing reports nothing and passes; that
is the defect `test_architecture.py` shipped with earlier the same week, and writing a second
scanning guard without the count assertion would have been repeating it four days later.

**Node 24 was verified by hand, not by this guard, and the docstring says so.** Checking a
runtime means fetching each action's `action.yml` from GitHub, and `make check` is deliberately
offline. At the pinned SHAs: `actions/checkout`, `actions/upload-artifact` and
`astral-sh/setup-uv` all declare `node24`; `nf-core/setup-nextflow` is a **composite** with no
runtime of its own, and both of its internals — its `subaction` and the `actions/setup-java` it
pins — are `node24` too. **That last pair is where the old warning actually came from**, and it
is the pair a check of the top-level workflow would never have looked at.

**One gap in the evidence, recorded rather than glossed:** the CI run showing zero deprecation
warnings was `ci.yml`, which never uses `setup-nextflow` — only `nightly.yml` does. The
composite's clean bill comes from reading its manifest at the pinned SHA, not from a run.

## `emitted_by` names the package that raises (2026-08-16)

| date | guard | reverted | result |
|---|---|---|---|
| 2026-08-16 | `test_diagnostics_ownership.py::test_every_locatable_code_is_owned_by_the_package_that_raises_it` | `MD0225` put back to `compiler` | failed, naming the code and both packages |
| 2026-08-16 | `…::test_the_unlocatable_codes_are_a_known_list` | a code with no raise site added to the registry | failed, naming it under `new:` |
| 2026-08-16 | `…::test_a_mention_is_not_an_emission` | the source list emptied | failed |
| 2026-08-16 | `…::test_the_scan_reached_the_sources` | the source list emptied | failed |

**The guard found twenty-three wrong labels on its first run, and every one said "raised in
comeni-core".** That uniformity is the diagnosis: `EmittedBy` had `compiler | resolver | forge |
api` and **no `core`**, so every code raised inside `comeni-core` — the declared-data loaders,
and `pipeline.py`'s validators — had to claim a package that does not raise it. A vocabulary that
cannot express the truth teaches people to lie to it, and it did: six of the nine codes added
four days earlier were wrong the same way, written by someone who checked the enum and found no
better option.

**The relabelled set was derived from the guard's own output rather than hand-copied.** A
twenty-three item list transcribed by hand is a list with a typo in it.

**Two forms of emission, and the second was nearly missed.** A first pattern matched only a code
leading a string, which put all nine conformance codes into `UNLOCATABLE` — where they would have
sat unexamined, because that list is *meant* to hold the ones nothing can see. They use
`code="MD0100"` on a `Diagnostic` object. Widening the pattern shrank `UNLOCATABLE` from fifteen
entries to one.

**`MD0202` is that one, and it is the only code with `refuses: false`.** It is printed as a
report line — `f"  MD0202  {line}"`, two spaces, no colon — because it tells a reader what was
carried forward rather than refusing anything.

**The colon is what separates a mention from an emission**, and that assumption has its own test
rather than living in a comment: `materialise.py` says *"which is exactly what `MD0223` is for"*
and must not count, while `artifact_verbs.py` writes `"mendel: MD0223: a value was edited"` and
must.

**Nothing published moved.** `docs/reference/diagnostics.md` is byte-identical after twenty-three
labels changed, because the generated page groups by `concern`. That is what made this a safe
repair rather than a churn of the public reference, and it was predicted in the spec before it
was checked.

## Packaging — a released package declares what it needs (2026-08-16)

| date | guard | reverted | result |
|---|---|---|---|
| 2026-08-16 | `test_packaging.py::test_every_workspace_dependency_carries_a_lower_bound` | `comeni-core>=0.1.0` → `comeni-core` | failed, naming package and requirement |
| 2026-08-16 | `…::test_no_workspace_dependency_carries_an_upper_bound` | `,<0.2.0` added | failed |
| 2026-08-16 | `…::test_there_are_packages_to_check` | — | asserts ≥3 manifests were found |

**Three of three were unbounded before this.** `mendel-compiler` declared
`dependencies = ["comeni-core", "mendel-resolver"]` and `mendel-resolver` declared
`["comeni-core"]`. In a `uv` workspace that resolves to the checkout and nothing is wrong; as a
released wheel it accepts *any* version, including one predating a type it imports. The defect
was invisible precisely because the workspace hid it, which is why it needed a test rather than
a reading.

**The cap guard is the less obvious half.** A cap on a package released from this same repository
is a promise to bump in lockstep — `mendel-compiler` pinning `comeni-core<0.3` means every
`comeni-core` minor release breaks the compiler until somebody edits a file. That is lockstep
wearing a different hat, and lockstep is the thing the operator rejected on 2026-08-16.

**`uv sync --locked` was run after the change**, so a lock needing regeneration is a change to
commit rather than a surprise in CI.

**Each package was built and tested alone** — two artifacts each, and 172 / 162 / 28 passing.
That is the claim per-package releases rest on, and it is cheap enough to check that assuming it
would have been the wrong trade.

## The release workflow (2026-08-16)

| date | guard | reverted | result |
|---|---|---|---|
| 2026-08-16 | `test_release_workflow.py::test_the_notes_are_extracted_before_the_build` | the build step moved above the notes step | failed |
| 2026-08-16 | `…::test_the_workflow_only_fires_on_a_package_tag` | `tags: ["*-v*"]` → `["*"]` | failed |
| 2026-08-16 | `test_changelog_section.py::test_a_missing_package_section_is_refused` | the `LookupError` replaced with `return ""` | failed |
| 2026-08-16 | `…::test_the_tool_exists` | — | see below |

**Three of the changelog tests passed before the tool was written**, because they assert a
non-zero exit and a *missing script* produces one. `test_the_tool_exists` is what closes that,
and it is the second time this week a test has been green for a reason unrelated to its subject
— the first was `assert "MD0004" in message` matching pytest's own `tmp_path` name.

**Both are the same mistake**: asserting on a signal that something *other than the code under
test* can produce. Worth naming as a class, because it is not caught by any amount of care about
the assertion itself — only by asking what else could satisfy it.

**The workflow's two tag checks are exercised without cutting a release.** Splitting
`comeni-core-v0.1.0` and comparing against `pyproject.toml` are the two steps that only ever run
on a tag push, and testing them by pushing a tag would mean publishing something to find out. The
shell parameter expansions are reproduced in Python and asserted against the real manifests.

**The `make check` decision is asserted rather than only commented.** The workflow gates on
`make check`, not `make verify`, because `verify` needs Docker and the slow lane and nightly
already covers `main`. The test requires the workflow to still mention `make verify` — so the
reason survives in the file where the decision was made, not only in a plan nobody re-reads.

## One source for a diagnostic code (2026-08-16)

| date | guard | reverted | result |
|---|---|---|---|
| 2026-08-16 | `test_diagnostics_registry.py::test_coded_refuses_an_undeclared_code` | the registry check removed from `coded()` | failed, with the near-miss test |
| 2026-08-16 | `test_diagnostics_ownership.py::test_every_emitted_code_is_declared` | one `coded("MD0001"` changed to `"MD9998"` | failed |
| 2026-08-16 | `…::test_every_declared_code_is_emitted` | a code added to `diagnostics.yml` that nothing emits | failed, naming it |
| 2026-08-16 | `…::test_every_code_is_owned_by_the_package_that_emits_it` | `MD0001`'s `emitted_by` set to `compiler` | failed |
| 2026-08-16 | `…::test_the_scan_reached_the_sources` | the emission pattern made to match nothing | failed |

**`coded()` is the runtime half and the scan is the static half, and neither is sufficient
alone.** `coded()` cannot fire until an error path runs, and a diagnostic's error path is by
definition the one that does not run in a green suite — which is A14's argument, arriving at the
one place in this repository that is *only* error paths. The scan runs always and knows nothing
about whether the code is reachable. Each covers the other's blind spot.

**The conversion itself was where the mistakes were, and there were three.** A regex left
unbalanced parentheses, because the messages are implicit multi-line concatenations and the
closing paren belongs after the *last* literal. `ast` column offsets are UTF-8 **bytes**, and
these files are full of em dashes, so slicing by character silently duplicated the tail of every
long message. And a `Constant` inside a `JoinedStr` matches the same test as the `JoinedStr`
itself, so seventeen messages got one replacement nested inside another.

**All three were caught by reading the diff of one file before converting the other sixteen**,
which is the step the plan insisted on and the only reason they were caught at all — every one of
them produced *syntactically plausible* output that a later `pytest` run would have blamed on
something else.

**`UNLOCATABLE` is deleted rather than emptied.** It held `MD0202`, and it existed only because
three emission shapes had to be matched by pattern. With one shape there is nothing to exempt —
the list was a symptom of the thing this change removes.

**The canary held.** `docs/reference/diagnostics.md` is byte-identical across seventy-eight
converted sites, and so is a built `pipeline.yml`. Nothing about what a code *says* moved, which
is the whole claim.

**A revert-and-watch loop left stale bytecode, and it cost twenty minutes.** Restoring a file
byte-for-byte can produce the same size and mtime it had before, so CPython reuses the cached
`.pyc` and the *reverted* code keeps running. `test_MD0001` failed against a message containing
`MD9998` while the source on disk plainly said `MD0001`.

Worth knowing for every future revert-and-watch, which is the method this whole ledger is built
on: **`find . -name __pycache__ -type d -exec rm -rf {} +` after a loop that restores files.** A
guard reported failing for the right reason and then reported failing for a reason that had been
undone, which is the least useful state a check can be in.

## A layer is files, not folders (2026-08-16)

| date | guard | reverted | result |
|---|---|---|---|
| 2026-08-16 | `test_declared_identity.py::test_a_vocabulary_may_declare_its_own_id` | the declared `id` ignored | failed |
| 2026-08-16 | `…::test_MD0010_a_declared_file_must_say_what_it_is` | the `declares:` check removed | failed |
| 2026-08-16 | `…::test_MD0012_a_vocabulary_must_declare_its_id` | the `id` requirement removed | failed |
| 2026-08-16 | `test_digest.py::test_a_layer_digests_what_it_declares_…` | — | **caught a live regression, see below** |

**One existing guard caught a real regression, and it is the most valuable row here.** Replacing
the digest's kind-directory allowlist with an extension allowlist swallowed `.github/ci.yml` into
the layer digest — a CI workflow is a `.yml`, and issue #46 had already established that hashing
what a *repository* carries beside a layer makes the digest depend on the checkout. Dot-prefixed
paths are excluded now, by the convention every tool shares.

**Three findings the plan did not predict, each a consequence of kind moving into the file:**

- **`kind:` was the wrong key.** `Measurement` already has one, meaning the kind of its *value*
  (`integer`, `enum`). The first implementation stripped it and broke every measurement in the
  registry. It is `declares:`.
- **A layer could swallow a nested layer.** With `stack()` globbing the whole layer, an overlay
  checked out *inside* the public registry would load as though it were the base layer's own
  files. A directory carrying `registry.yml` is now recognised as a layer of its own and skipped
  — `--registry` takes several roots, and nesting one inside another is an ordinary mistake.
- **`MD0005` refused a legitimately empty overlay.** A lab creates a layer before it has anything
  to put in it. Refusing only a *completely* empty directory keeps the unchecked-out-submodule
  case, which is what the code was written for, and lets the empty overlay through.

**`MD0003` is retired**, and this is the trade the spec named. It refused a `.yml` no kind read —
a misspelled `contract/` for `contracts/` — which was prevention *by construction*: the directory
was the file's identity, so a misfiled document was invisible and therefore refused. Now a file
declares itself and loads from anywhere, so there is no position left for it to be invisible in,
and the same mistake is caught as a missing declaration (`MD0010`). **A26 moved from detected to
prevented**, which is a better place for it, at the cost of a code that could not fire.

**The fixture sweep is the part worth warning about.** Roughly thirty test files build layers by
hand, and a first codemod patched them *by basename across every file* — so `a.yml` was labelled
a measurement in one test and a contract in another, and both labels landed on the same write.
The correct mechanism is one helper that derives the kind from the directory **at runtime**, and
it has to walk *ancestors* rather than the immediate parent, because `contracts/nf-core/fastqc.yml`
sits two levels below the directory that names it.

## comeni-registry#2, 2026-08-16 — the tool-grouping rule

**Guard:** `packages/mendel-compiler/tests/test_tool_docs.py`, the four grouping tests.

**Reverted:** `_tool_of`'s `key.split("/")[:2]` to `[:-1]` — "drop the last segment", which is
the rule a reader would guess and the one the ids do not support.

**What happened:** three of four failed. The messages name the defect rather than a helper:

```
assert [c.id for c in tools["nf-core/fastqc"]] == ["nf-core/fastqc@0.12.1"]
E   KeyError: 'nf-core/fastqc'

assert tool_docs._tool_of("sortmerna@4.3.6") == "sortmerna"
E   AssertionError: assert '' == 'sortmerna'
```

**Why it matters.** Contract ids are **not uniformly shaped** — `nf-core/star/align` has three
segments and `nf-core/fastqc` has two — so "drop the last segment" collapses every two-segment
nf-core module onto a single `nf-core` page, and reduces a one-segment key to the empty string.
The empty-string case is the sharper one: it would have produced a page named `.md` rather than
failing, which is the silent direction A67 is about.

`__pycache__` was cleared after restoring, per the bytecode note in the 2026-08-16 journal.

## comeni-registry#2, 2026-08-16 — sorted states in a generated page

**Guard:** `test_a_multi_state_port_renders_in_sorted_order`.

**Reverted:** `_states`' `sorted(states)` to `states`.

**What happened:** fails under every `PYTHONHASHSEED`, with a *different* order each time:

```
E  AssertionError: assert '`name_sorted...deduplicated`' == '`coordinate_...`name_sorted`'
E  AssertionError: assert '`indexed`, `...deduplicated`' == '`coordinate_...`name_sorted`'
```

**The guard had to be rewritten before it could fail, and that is the finding.** Its first
version rendered a real page twice and compared. It passed with the sort removed, because a
frozenset's order is stable *within one process* — and worse, hashing the page in three separate
processes also matched, because **no port in the registry carries more than one state** and a
one-element set has only one order.

So against real data the guard was inert. The second version constructs a four-state port in the
test, which is [A36](2026-08-14-design-audit.md)'s answer to the same problem — invent the case
the data does not yet contain, rather than assert a line cannot be wrong.

**Why it matters more here than for `IREdge.states`.** These pages are *committed*. An unsorted
set makes `comeni-registry`'s CI red on a machine whose seed differs from the one that generated
them, and green on the author's — a failure nobody can reproduce locally.

## comeni-registry#2, 2026-08-16 — `mendel docs --check`

**Guard:** `tests/test_docs_verb.py`, the four `--check` tests.

**Revert 1:** `if check:` to `if False:` in `_docs_verb`, so `--check` writes instead of
reporting. Four failed, including `test_check_writes_nothing` — the one that matters, because a
check which repairs what it measures reports success the second time it runs and can never fail
twice. That is `make drift`'s "skipped" wearing different clothes.

**Revert 2:** dropped the orphan clause alone (`if page.relative_to(out) not in pages` to
`if False`). Exactly one failed —
`test_check_refuses_a_page_for_a_tool_that_no_longer_exists` — which is the isolation worth
having: the orphan case is the direction nothing else catches. A contract is deleted, its page
is not, and the page goes on documenting a tool the registry no longer ships. Stale and missing
pages are both caught by the `wrong` list, so a single blunt revert would not have told the two
apart.

## comeni-registry#2, 2026-08-16 — a layer's files, judged relative to the layer

**Guard:** `packages/comeni-core/tests/test_layer_file_identity.py`.

**Reverted:** `_declared`'s `path.relative_to(root).parts` back to `path.parts` — the absolute
frame of reference it shipped with in `920fa2a`.

**What happened:** four failed, and the messages name the defect rather than a helper:

```
E  AssertionError: assert 0 == 37
E   +  where 0 = len([]) = declared_entries(PosixPath('…/.worktrees/some-plan/registry'))
E   +  and  37 = declared_entries(PosixPath('…/plain/registry'))

E  AssertionError: assert 'sha256:e3b0c...5991b7852b855' == 'sha256:32b33...ac4517844e935'
```

`e3b0c442…b855` is the SHA-256 of **the empty string**.

**Why it was invisible.** Every file in a layer under `.worktrees/` has a dot-prefixed ancestor
*somewhere above it*, so the filter matched all of them and the layer contained nothing. Hashing
nothing succeeds, so the digest was wrong in the silent direction (A67) rather than raising.
`CLAUDE.md` requires plans to execute in `.worktrees/`, so **every pipeline built the sanctioned
way pinned its layer to the empty digest**, and `make verify` was green throughout because
nothing compares a digest across two locations.

**This is the third appearance of one bug.** `test_architecture.py`'s first version filtered on
absolute path parts and skipped the whole repository. `make drift`'s `REGISTRY ?= ../comeni-registry`
resolved into `.worktrees/` and printed "skipped". Both are recorded above. This is the same
mistake in *production* code, and it also re-opened issue #46's machine-dependent layer digest by
a different route.

**Found by Task 6 of comeni-registry#2**, because `comeni-registry` is the first layer to carry
CI of its own — `.github/workflows/ci.yml` was read as a contract and refused with `MD0010`,
which is the *other* half of the same disagreement: `_files` had no dot-exclusion at all while
`declared_entries` had a broken one. One predicate now, so there is one answer to "what are a
layer's files".

**No published digest moves.** A layer at an ordinary path digested `32b33d94…` before this
change and does so after; only dot-directory checkouts were ever wrong.

## The forge, 2026-08-17 — only `land` writes to a registry

`tests/test_forge_write_boundary.py` is the whole-package half of invariant 2: a person approves,
and nothing writes to a registry automatically. Two guards were watched failing while the forge
was built; both are recorded here, with the third — the ownership guard's — recorded because it
fired *by itself*, without anybody arranging it.

| date | guard | what was reverted | what happened | message |
|---|---|---|---|---|
| 2026-08-17 | `tests/test_forge_write_boundary.py` | a `Path(...).write_text(...)` added to `mendel_forge/verify.py` | failed | names the file, the line and the method |
| 2026-08-17 | `tests/test_purity.py::test_no_pure_package_imports_an_impure_one` | a commented-out `import mendel_forge` appended to `comeni_core/__init__.py` | failed | names the offending path |
| 2026-08-17 | `tests/test_diagnostics_ownership.py::test_every_emitted_code_is_declared` | `coded("MF0002", …)` renamed to `MF9999` in `scaffold.py` | **passed before the fix, failed after** | names the undeclared code |
| 2026-08-17 | `packages/mendel-forge/tests/test_http.py::test_no_route_contains_a_branch` | an `if` added to the `/check` route returning the same value down both paths | failed | prints the offending route body |
| 2026-08-17 | `tests/test_no_live_model.py::test_no_test_file_names_a_live_transport` | `from mendel_ai.client import LiteLLMTransport` added to `packages/mendel-ai/tests/test_recorded.py` | failed | names the file, the line, the name, and what to use instead |

**The write-boundary message, verbatim:**

```
E  AssertionError: only land.py may write to a registry and only workspace.py may write a draft; these write somewhere:
E        packages/mendel-forge/src/mendel_forge/verify.py:61 .write_text
E  assert ['packages/me... .write_text'] == []
E    Left contains one more item: 'packages/mendel-forge/src/mendel_forge/verify.py:61 .write_text'
```

**The third row is the one worth reading.** `EMISSION` in the ownership guard matched `MD\d{4}`
alone, so every `MF` code was invisible to `test_every_emitted_code_is_declared` — an undeclared
`MF9999` passed. The blindness was **not symmetric**, which is why it did not survive: the other
direction, `test_every_declared_code_is_emitted`, compares the whole registry against the same
`MD`-only scan, so declaring the first `MF` code turned it red *falsely* within the minute. The
pattern is now `[A-Z]{2}\d{4}`, and `test_the_scan_sees_every_declared_prefix` checks it against
the registry's own prefixes rather than a hand-kept list.

**The live-model guard's message, verbatim:**

```
E  AssertionError: a test reaches a live model:
E      packages/mendel-ai/tests/test_recorded.py:74 names LiteLLMTransport
E
E    Use RecordedTransport with a committed fixture, or an injected fake.
```

**This guard is new in forge Phase 2, and `CLAUDE.md` had asked for it since before it could
exist** — *"no test may call a live model"* was written when there was no model to call, so
nothing enforced it. It is a name scan over the two transports that actually reach a provider,
and it carries the same standing as invariant 1's scan: **cost-raising, not a proof.** It cannot
see a transport built dynamically. What it catches is the thing that actually happens — somebody
reaches for the real transport because the fake was inconvenient — and it names the file, the
line and the alternative when it does.

Two of its three tests exist because of A67: one asserts the matcher trips on text that should
trip it, and one asserts the file list is not empty. A guard running over nothing goes green
*faster*, which is the direction nobody investigates.

**A fourth defect was found by reading a generated artifact rather than by any guard**, and it is
recorded here because that is the pattern issue #46 established. The first golden scaffold
written carried an **absolute** evidence locator —
`/home/<user>/…/.worktrees/forge-phase-1/vendor/modules/nf-core/fastqc/main.nf` — making the
golden file machine-dependent and putting the author's checkout path into every draft. Every test
was green. `test_no_locator_is_an_absolute_path` now holds it, but the guard exists *because
somebody looked at the file*, which is the same way `digest_of_directory` was caught.

---

## 2026-08-18 — `tests/test_egress.py`, door 2's new fields (Plan 2.5)

**Watched failing, twice, and one of the two failures was not staged at all.**

Plan 2.5 makes `Ambiguity` a subclass of `comeni_core.review.Question`, which gives it four
fields the forge had always carried on a `Hole`. Door 2's payload is asserted to be *the union
of what the `*Asked` types carry*, so the totality guard went red **on its own** at the re-base
commit (`4eefca3`) — no revert needed, and the plan predicted the message before the code was
written:

```
AssertionError: ParamAsked.what has nowhere to go in AmbiguityRequest, so a
model behind door 2 would never be told it
```

That is the guard forcing a decision into the open rather than letting it be skipped: *does a
tier-4 model call get the quoted source lines?* It was answered yes, and
`test_the_door_carries_what_the_forge_measured_a_model_needs` is the answer written as a test.

**The staged revert** deleted `evidence` from `AmbiguityRequest` and printed both halves:

```
AssertionError: ParamAsked.evidence has nowhere to go in AmbiguityRequest, so a
model behind door 2 would never be told it

AssertionError: evidence does not cross door 2, so a tier-4 model call is the
configuration the forge measured at 69%
```

The second message is the one worth having. A shape guard can only say *a field has no slot*; it
cannot say *and here is what it costs*. The forge's prompt search measured 69% → 88%, and two of
the three fixes behind that jump were "say what the question is about" and "make the evidence
readable" — so the guard cites a measurement rather than an opinion.

**What the allowlist extracted on the way through, unprompted.** Making `Excerpt` reachable from
a payload tripped three further guards in one run, and each demanded a real change rather than an
exemption: `locator` and `text` were bare `str` (now `Text`), and `Excerpt` was unfrozen (now
frozen, so what a reviewer read is what is sent). None of this was in the plan. It is what an
allowlist buys over a blocklist — A19, A20 and A30 were each a shape nobody had thought to
forbid, and this is the same guard catching a shape nobody had thought to *permit*.

### `test_the_candidates_still_bind` — the same day, and it is why `make residue` is a number

Plan 2.5 added one refusal-shaped test in `mendel-resolver` and the residue count went **up by
one**. The plan said it should not, so it was chased rather than accepted — which is the whole
point of A69 making the number derivable instead of asserted.

Reverted by setting `closed=False` on the `ProducerAsked` the router builds:

```
assert asked.closed is True
E   AssertionError: assert False is True
     where False = ProducerAsked(subject='producer:alignment.bam', …).closed
```

**What it protects.** `closed` is inherited from `Question` and a routing tie is genuinely a
closed choice — the answer has to be one of the tied contracts. The forge measured that opening
a closed field was the *worst* prompt configuration tested, six points below closing it, so a
build-path question that silently went open would be repeating a mistake already paid for.

**The message is honest but not ideal**: it says the value is wrong, not what that costs. The
egress guard above does better because its assertion carries the 69% figure in its own message.
Written down as the difference between a guard that reports a fact and a guard that reports a
consequence.

---

## `test_an_input_fed_by_an_entry_channel_is_not_unmet` — 2026-08-23

**Reverted:** `_has_entry_channel(port, layers)` in `mendel_resolver/validate.py::_check_ports`,
replaced with `if True:` so every unwired input reports `MD0506`.

**What it printed:**

```
E       AssertionError: ['MD0506: align.reads has no wire and its type declares no entry channel',
                         'MD0506: align.index has no wire and its type declares no entry channel',
                         'MD0506: align.gtf has no wire and its type declares no entry channel']
E       assert 'gtf' not in {'gtf', 'index', 'reads'}
```

**What it protects.** The half of the unmet check that is not about edges. `star/align.gtf`
arrives from `params.gtf` and has no incoming wire; a check reading only edges marks it unmet and
is wrong about every entry channel in the pipeline. **Plan 3C shipped exactly this defect** —
a hollow *unmet* dot on a satisfied input — and caught it by eye rather than by test, which is
why this guard exists before the canvas can draw one.

**The message reports a consequence, not just a fact**, which is the standard the egress guard
set two entries above: it names the three ports, and the two that are legitimately unmet
(`index`) stay visible beside the one that is not, so the failure shows the *distinction* being
lost rather than only that a set changed.

**What it does not protect.** That the entry channel is the *right* one — `_has_entry_channel`
asks only whether the type declares any. A port whose type has an entry channel it should not be
using is invisible to this, and to `validate` generally.

---

## The frontend typecheck was inert — 2026-08-23

**Not a revert. A guard that never held, found by a Docker build refusing what it had passed.**

`.github/workflows/ci.yml` ran `npx tsc --noEmit` in `frontend/`. `frontend/tsconfig.json` is:

```json
{ "files": [], "references": [{ "path": "./tsconfig.app.json" }, { "path": "./tsconfig.node.json" }] }
```

With `"files": []` and no project flag, `tsc --noEmit` type-checks **nothing** and exits 0.

**Watched failing.** A one-line file was added:

```ts
export const broken: number = "this is definitely not a number";
```

```
$ npx tsc --noEmit     # what CI ran
exit: 0
$ npx tsc -b           # what the Docker build runs
src/build/__inert.ts(1,14): error TS2322: Type 'string' is not assignable to type 'number'.
```

**What it did not protect.** Everything. Three real type errors reached a Docker build during Plan
3E while this lane was green — a model split into `DraftGraph-Input`/`-Output` by FastAPI, a
`Verdict` namespaced because three classes share the name, and an `HTMLCollection` spread that
the build's lib does not allow.

**How it was hidden.** `npm run build` is `tsc -b && vite build`, so the *real* check existed and
ran — in the image build, which neither `make check` nor the CI frontend lane invokes. The lane
looked like a typecheck, was named like one, and cost eight seconds of nothing.

**The generalisable part**, which is why this is in the ledger rather than only in a commit: a
guard invoking a tool with the wrong arguments reports success rather than an error, so it is
**invisible to the very failure it exists to catch**. `test_the_scan_reached_the_sources` in
`test_diagnostics_ownership.py` is the pattern that would have caught it — a guard asserting that
it looked at something before asserting what it found.

---

## Plan 18a — the execution boundary, 2026-08-23

| date | guard | what was reverted | what happened | message |
|---|---|---|---|---|
| 2026-08-23 | `test_emit.py::test_emit_config_cannot_depend_on_a_deployment_target` | added `target: str = "local"` to `emit_config` | failed | `emit_config takes ['pipeline', 'target']. The executor reaches a run through a PROFILE and -c site.config, never through emission — docs/design/execution-boundary.md §6.` |

**Why this guard is on a signature rather than on output.** `docs/design/execution-boundary.md`
§6 forbids the executor entering the artifact, and the tempting guard is one that renders a
config and asserts what is in it. That guard passes right up until somebody adds the parameter
*and* threads it through — by which time `Pipeline.emitted`'s digests already depend on a
deployment choice and the fix is a schema conversation.

A one-parameter signature **cannot express** a per-target emission, so this fails at the moment
somebody reaches for the wrong design rather than after they have built it. That is the same
shape as invariant 11's directory-by-construction argument: prevention beats detection where the
type system will carry it.

---

## The boundary, guarded at the table and at the column — 2026-08-23

| date | guard | what was reverted | what happened | message |
|---|---|---|---|---|
| 2026-08-23 | `test_models.py::test_a_gate_run_carries_no_input_and_no_credential` | added `input_path: Mapped[str \| None]` to `GateRun` | failed | `gate_run's columns moved: [... 'input_path' ...]. A gate runs Mendel's own artifact on data somebody else published and takes no samplesheet, no executor, no workDir and no credential — docs/design/execution-boundary.md §3. A column for any of those makes this run history, which is Wiener's, and moves the boundary without anybody deciding to.` |
| 2026-08-23 | `test_models.py::test_the_registry_is_not_in_the_database` | added a `Run` model with `__tablename__ = "run"` to `mendel_api.models` | failed | `the tables moved: [... 'run' ...]. … a table of RUNS is Wiener's, and building it here because the worker is here is the exact failure docs/design/execution-boundary.md §8 names.` |

**The second row is a guard that already existed and was not claimed.** `test_the_registry_is_
not_in_the_database` was written for issue #43 — declared data is files, so a table of contracts
would be that decision quietly reversed. Asserting the *exact* table set rather than an absence
made it, by accident, the only structural guard on `execution-boundary.md` §8: run state needs
somewhere to live, and a `run` table in `mendel-api` is the first move in the mistake §8 names.

**Reverting it is what showed the guard was half-inert.** It failed — and printed
`unexpected: {…}`, which tells the person who hit it nothing except that a set changed. The
obvious repair from that message is to add `"run"` to the set. A guard whose message argues for
the wrong fix is barely a guard, which is A14's point arriving from a new direction: this one was
never *watched* failing, only asserted to pass. The message now names both rejections, and the
revert was re-run to read it.

**Its coverage is narrow and stated rather than implied.** Run state in Redis, in a JSON blob, or
as extra columns on `gate_run` all pass it. The first two are out of reach of a model-level guard;
the third is the first row above, which is why the pair was added together. The cheap mistake —
one plausible column on a table that already remembers a Nextflow invocation — is now the guarded
one.

---

## Invariant 1 grows by a package — 2026-08-24

**The first time `CLOSED_PACKAGES` has gained a whole package** rather than an import, so both
halves were reverted: the guard that notices an unclassified package, and the guard that
notices what a classified one imports.

| date | guard | what was reverted | what happened | message |
|---|---|---|---|---|
| 2026-08-24 | `test_purity.py::test_every_package_is_classified` | created `packages/wiener-core/` before classifying it | failed | `every package must be classified pure, banlist or explicitly impure — a package this file has never heard of is a package it is not guarding:` / `  on disk, unclassified: ['wiener-core']` / `  classified, not on disk: []` |
| 2026-08-24 | `test_purity.py::test_pure_packages_import_nothing_impure` | added `import socket` to `wiener_core/__init__.py` | failed | `Pure packages must not import I/O or model libraries:` / `  packages/wiener-core/src/wiener_core/__init__.py imports socket` / `  packages/wiener-core/src/wiener_core/__init__.py imports socket, which is not on this package's allowlist` |

**The second message says it twice, and that is the union of two rules rather than a repeat.**
The first line is the global banlist — `socket` is refused to every pure package — and the
second is this package's own allowlist. An import that is not banned outright but is absent from
the allowlist prints only the second, which is what the next entry to this list will look like.

**What is not guarded yet, and is the reason this package is on the list at all.** `datetime` is
allowed for the class and must never be `datetime.now`: §6.1 of `docs/design/wiener.md` says the
same events must replay to the same decisions, and the allowlist cannot express *this name but
not that attribute of it*. `test_wiener_core_never_reads_a_clock` is Task 4's, and until it lands
and is reverted here, this section is the weaker half of the claim.

**The plan's Step 5 command selected nothing.** It read `pytest -k unclassified`, and the test is
`test_every_package_is_classified` — "unclassified" appears only in the failure message. A step
that runs no test and reports no failure is the vacuous pass this ledger exists to catch, found
this time in a plan rather than in a guard.

---

## The clock, kept out of the fold — 2026-08-24

`tests/test_no_clock.py`, Task 4. `docs/design/wiener.md` §6.1's claim is that the same events
replay to the same decisions, and it dies the first week a clock is read inside `wiener-core`.
The purity allowlist cannot hold it: `datetime` is on that package's list because `admit()`
parses an ISO-8601 `utcTime`, and an allowlist works on module names rather than on attributes
of them. So this is a separate scan, and it was reverted three ways.

| date | guard | what was reverted | what happened | message |
|---|---|---|---|---|
| 2026-08-24 | `test_no_clock.py::test_wiener_core_never_reads_a_clock` | `from datetime import datetime` + `datetime.now()` in `policy.py` | failed | `wiener-core read a clock:` / `  policy.py:83 reads now` / `Time enters as data — a field on the event, or an explicit now_ms parameter…` |
| 2026-08-24 | same | `import datetime` + `datetime.datetime.now()` | failed | `  policy.py:83 reads now` |
| 2026-08-24 | same | `from time import monotonic` + `monotonic()` | failed | `  policy.py:82 imports time.monotonic` |

**The second and third rows are why the guard was widened before it was ever committed.** The
plan's version matched an `ast.Attribute` whose `.value` is a bare `ast.Name`, and that sees
exactly one of the three spellings. Run against the other two it reports nothing:

```
CAUGHT  from datetime import datetime; datetime.now()
MISSED  import datetime; datetime.datetime.now()
MISSED  from time import monotonic; monotonic()
```

`datetime.datetime.now()` is the *ordinary* spelling after a plain `import datetime`, and the
value there is another `Attribute` rather than a `Name`. A bare `monotonic()` has no attribute
access at all, so no attribute rule can ever see it — the import is the only observable moment,
which is why importing one of those names is itself the offence.

**This is A1's shape in a new place.** That audit defeated the purity scan with `pathlib.os`, a
chain the check could not see; this is the same blind spot, found before it shipped rather than
after, because the revert was tried three ways instead of once.

**What it still does not cover**, stated rather than implied: a clock reached through a name
this file does not know — `os.times`, a C extension, a callable passed in as an argument. The
last one is not a defect but the design: `now_ms` is a parameter, and a caller passing a live
clock is `wiener-api` doing its job.

---

## Wiener's four tables, and the query that may not be written elsewhere — 2026-08-24

Task 5. Four reverts, and the third is the one worth reading: **the guard the plan shipped
would have passed it.**

| date | guard | what was reverted | what happened | message |
|---|---|---|---|---|
| 2026-08-24 | `test_wiener_models.py::test_the_tables_are_the_four_that_argued_for_themselves` | added a fifth model, `run_note` | failed | `the tables moved: ['run', 'run_artifact', 'run_event', 'run_note', 'run_task']. run_event is the record and run_task and run are projections of it with a rebuild path — a table that is neither needs an argument in docs/design/wiener.md §7.1 before it exists.` |
| 2026-08-24 | `test_wiener_models.py::test_no_table_stores_a_samplesheet_s_contents` | added `input_path` to `run` | failed | `a table grew a column for a sample: ['run.input_path']. The samplesheet PATH reaches Wiener in the admitted started payload because Nextflow put it there; nothing copies it into a column of its own and nothing indexes it.` |
| 2026-08-24 | `test_tenancy.py::test_no_query_is_built_outside_the_repository` | `session.get(Run, run_id)` in `routes/_probe.py` | failed | `a query on a tenant-scoped table was built outside repository.py:` / `  routes/_probe.py:7 — get()` |
| 2026-08-24 | `test_tenancy.py::test_every_repository_function_takes_a_lab_id` | dropped `lab_id` from `repository.run` | failed | `run(session: Session, run_id: str) -> Run \| None — a repository function takes the session and the laboratory it is scoped to, in that order, so an unscoped query cannot be spelled.` |

**The second message was rewritten before it was accepted.** It printed the whole column set
and an `assert not ({...} & {...})` — true, unreadable, and silent about which column offended.
It now names `run.input_path`. That is the third message in two days improved for the same
reason, and the pattern is worth stating: **an assertion written to be correct and an assertion
written to be read are different assertions**, and only the revert tells them apart.

**Row three is A177's whole argument, demonstrated.** The plan's tenancy guard scanned for
`select(...)` calls with a `Name` argument and a `lab_id` within three lines. `session.get(Run,
run_id)` is a query on a tenant-scoped table, it is the obvious way to write `GET
/api/runs/{id}`, and that guard **cannot see it** — no `select`, no `Name` argument, nothing to
match. The rule is now about *where a query may live*, and the same revert fails loudly.

**What it does not cover**, stated rather than implied: raw `text()` SQL, a query built by
string concatenation, and anything reaching the database through a connection this scan cannot
see. Postgres row-level security is the control that survives all three, and it is not built —
§7.1's mechanism is a repository module and a scan, which is prevention by convention plus
detection, not prevention by construction. Invariant 11's directory-by-construction note
records the same trade going the other way.

---

## The two halves, and the clock that wakes a run — 2026-08-24

Two gaps found by reading the spec against the code after Checkpoint 3, and closed before
phase 3 could build on either.

| date | guard | what was reverted | what happened | message |
|---|---|---|---|---|
| 2026-08-24 | `test_purity.py::test_the_two_halves_share_only_comeni_core` | `import mendel_compiler.layout` in `wiener_api/repository.py` | failed | `the two halves of the product may share only comeni_core:` / `  packages/wiener-api/src/wiener_api/repository.py imports mendel_compiler` |
| 2026-08-24 | same | `from wiener_core.state import RunState` in `mendel_api/questions.py` | failed | `  packages/mendel-api/src/mendel_api/questions.py imports wiener_core` |

**`docs/design/wiener.md` §3.3 declared this rule and nothing built it.** Both reverts were run
*before* the guard existed and both passed — green, twice — which is the difference between a
rule written down and a rule held.

**The claim it corrects was half wrong when first reported.** `wiener-core` importing
`mendel_compiler` *does* already fail, because that package's allowlist is closed and
`mendel_compiler` is not on it. What was unguarded is everything impure: `wiener-api` in one
direction and every `mendel-*` package in the other. Saying "the arrow is unguarded" was
therefore too broad, and the difference matters — a closed allowlist protects the pure half by
construction, and only the impure half needed a rule.

**Why it was urgent rather than tidy.** Phase 3 draws the run graph, `layout.py` lives in
`mendel-compiler`, and the obvious way to get it is an import — from `wiener-api`, which is
exactly where nothing was watching.

**It is an AST scan rather than a substring one**, unlike its neighbour
`test_no_pure_package_imports_an_impure_one`, which greps for `"mendel_forge" in text`. For an
arrow between two halves that over-matching is not acceptable in either direction: a sentence
naming the other half would fail the build, and a guard nobody trusts gets deleted.

---

## A fifth pure package, and the arithmetic that moved — 2026-08-24

`dag-core`, phase 3 Task 1. The layout is shared by the builder's canvas and Wiener's run graph,
so it is a package that is neither half (`docs/design/wiener.md` §9.1.1).

| date | guard | what was reverted | what happened | message |
|---|---|---|---|---|
| 2026-08-24 | `test_purity.py::test_every_package_is_classified` | created `packages/dag-core/` before classifying it | failed | `every package must be classified pure, banlist or explicitly impure …` / `  on disk, unclassified: ['dag-core']` |

**Its allowlist is the shortest on the list and does not include `comeni_core`.** The arithmetic
moved unchanged; the one thing that changed is that it no longer reads a `PipelineIR`. A package
that lays out a graph has no business knowing what a pipeline is, and the allowlist is where
that is enforced rather than hoped for.

**`__future__` was on the entry before it was written**, because the plan's own audit (A187)
found `_outside_allowlist` has no exemption for it. That is the cheaper order — a finding in a
plan costs a paragraph, and the same finding at execution costs a failing gate and a guess.

**The move was proven rather than asserted**: `packages/mendel-compiler/tests/test_layout.py`
was 13 passing before and 13 passing after, `make verify` is green, and the frontend's 113
canvas tests are untouched. One line changed in that test file — `_port_x` is imported from
`dag_core.layout` now — and no assertion did.

---

## The exporter, refused where it does not belong — 2026-08-24

Phase 3 Task 6, and **§3.1 predicted this exact moment**: *"the OpenTelemetry SDK is a network
client, so the purity guard makes it structurally impossible to put the exporter on the wrong
side of the line. Nobody has to remember this."*

| date | guard | what was reverted | what happened | message |
|---|---|---|---|---|
| 2026-08-24 | `test_purity.py::test_pure_packages_import_nothing_impure` | `from opentelemetry.sdk.trace import TracerProvider` in `wiener_core/spans.py` | failed | `Pure packages must not import I/O or model libraries:` / `  packages/wiener-core/src/wiener_core/spans.py imports opentelemetry.sdk.trace, which is not on this package's allowlist` |

**A prediction that comes true is worth recording as loudly as one that does not.** The entry in
`CLOSED_PACKAGES` was argued for on 2026-08-24 partly on this basis, and the argument was
speculative at the time: a fold over events has no need of a socket, and the OTel payoff was
named as a bonus nobody had tested. It has now been tested.

**What it cost, which is the honest half**: `spans()` describes spans and cannot send them, so
there is a translation in `wiener-api` — including turning a readable `<run>.<task>.<attempt>`
id into the eight bytes the wire wants. That translation is a real cost of the split, and it is
smaller than the thing it prevents.

---

## Absence is not zero, and two tests said so — 2026-08-24

W2 Task 1 step 6. `overview()` is the front door's projection, and its docstring's sharpest
claim is that *a number nothing reported is `None`, never zero* — a run launched without
`trace.enabled` reports no resources at all, and a zero reads as **this process used no
memory**, which is a lie a reader cannot tell from a true number.

| date | guard | what was reverted | what happened | message |
|---|---|---|---|---|
| 2026-08-24 | `test_overview.py::test_absence_is_none_and_never_zero` | `memory_peak_bytes=_worst([...])` → `_worst([...]) or 0` in `wiener_core/overview.py` | failed | `AssertionError: assert 0 is None` / `  where 0 = ProcessRow(process='GREET', …, memory_peak_bytes=0, …).memory_peak_bytes` |

**A second test failed that was not aimed at this**, and that is the part worth recording:
`test_a_declared_process_the_run_never_reached_is_a_row_and_not_a_gap` went red on the same
edit, because a process the run has not reached reports nothing either — so `or 0` claims a
peak for a process that never started. One `or 0` is two different lies, and only one of them
had a test written for it.

**`or 0` rather than `if … else 0` on purpose.** The plausible way this defect arrives is not
somebody deciding zero is right; it is somebody making a type checker happy about `int | None`
in one keystroke. That is the edit the guard has to catch.

---

## An undefined `var()` is silence, not an error — 2026-08-24

W2 Task 4 step 7. **This guard is the only kind of thing that could have caught the defect it
was written for.** `--hover` was referenced five times in `frontend/src/build/` and defined
nowhere from Plan 3C until today: `hover:bg-[var(--hover)]` compiles, ships, and renders as
nothing at all. Five hover states were dead CSS for a fortnight, which is most of why the
builder felt inert, and no test, typecheck or review found it — because there is nothing to
find. An undefined custom property is not an error; the declaration is simply dropped.

| date | guard | what was reverted | what happened | message |
|---|---|---|---|---|
| 2026-08-24 | `tokens.test.ts::defines every custom property the app references` | deleted the `--hover:` line from `frontend/src/tokens.css` | failed | `AssertionError: expected [ Array(1) ] to deeply equal []` / `+ "--hover (…/build/Builder.tsx, …/build/Compare.tsx, …/build/Findings.tsx, …/main.css)"` |

**It names the files, not just the token**, which is the difference between a guard that
reports a fact and one that hands over the fix.

**Writing it found two more the plan did not know about.** `--profiled` and `--settled` were
referenced in `Findings.tsx` and `Port.tsx` as names for tier 3 and tiers 1–2, and neither has
ever existed in the palette — the real names are `--measured` and `--pea`. One of them hid
inside a fallback chain, `var(--advisory, var(--profiled))`, where **both** names were
undefined, which is why the guard's regex matches `var(\s*--name` rather than the closing
paren: a fallback to another missing token is the most invisible form of this bug.

**Paired with a vacuity check**, per A67: `finds something, so it cannot pass by reaching
nothing`. A file walk that breaks would otherwise turn the guard green rather than red.

---

## A zero-length bar and a zero are the same picture — 2026-08-24

W2 Task 6 step 5. The overview is the run page's front door, and §4's second rule is that
**absence is `—`, never `0%`**: a run launched without `trace.enabled` reports nothing at all,
and a zero reads as *this process used no memory*.

| date | guard | what was reverted | what happened | message |
|---|---|---|---|---|
| 2026-08-24 | `Overview.test.tsx::renders an absent measurement as a dash and never as zero` | `bytes()` returns `"0 B"` instead of `ABSENT` for `null`, in `runs/units.ts` | failed | `expect(element).toHaveTextContent()` / `Expected element to have text content: —` / `Received: 0 B of 34.4 GB` |

**The same edit is caught twice, in two packages, and that is the point.** `wiener-core`'s
`test_absence_is_none_and_never_zero` holds the projection and this holds the drawing — the
number can be lied about at either end, and a `?? 0` in a component is exactly as invisible as
an `or 0` in the fold. One guard per end is not redundancy; it is two different authors.

**The bar is guarded by construction rather than by a test.** `Bar` renders no fill element at
all when the value is `null`, so there is nothing to give a width — a zero-length bar and a
zero-valued bar are the same picture, and only one of them is true.

---

## The tail that got slower the longer you watched — 2026-08-24

W2 Task 10. A199: `setEvents((seen) => [...seen, event])` copies the whole array **per
message**, so a 5,000-task run's console degrades quadratically as it grows. The fix buffers
arrivals and writes state once per animation frame.

| date | guard | what was reverted | what happened | message |
|---|---|---|---|---|
| 2026-08-24 | `useRunStream.test.tsx::coalesces a burst into one state write rather than one per event` | restored the per-message `setEvents` in `ws.onmessage`, dropping the frame buffer | failed | `AssertionError: expected "vi.fn()" to be called 1 times, but got 0 times` |

**The first version of this test proved nothing and passed anyway**, which is the part worth
recording. It asserted that the events array had not changed synchronously after fifty
messages — true with the fix and true without it, because React batches renders on its own.
A guard that passes on the code it was written to reject is worse than no guard: it is a green
tick over an open hole.

What discriminates is the **frame count**: one scheduled `requestAnimationFrame` for fifty
messages is only true of the buffered version, and zero is what the unbuffered one gives. The
lesson is the A67 one from a new angle — a guard has to be watched failing *against the
specific defect*, not merely watched failing.

**A second defect was found by the drain test in the same task**, and it was mine rather than
inherited: the paging loop's `setEvents` updater closed over the loop's mutable `page`
variable, and React runs a functional update *later* — so page one's updater read whichever
page had arrived by then. 437 events came back as 237, page two vanished, page three merged
twice. `const arrived = page.events` inside the loop body is the whole fix.

---

## Hidden must not rot into broken — 2026-08-30

Plan 4 phase 0, task 1. The forge left the navigation by the operator's decision and **stayed in
the router**, which is two claims rather than one — and a pair of claims needs a pair of guards,
because each is exactly the failure mode of satisfying the other.

| date | guard | what was reverted | what happened | message |
|---|---|---|---|---|
| 2026-08-30 | `router.test.tsx` "keeps %s resolvable after the tabs came out" | deleted `{ path: "/forge/tools", element: <Tools /> }` from `routes` — the smallest edit somebody would make to a route they can no longer see in the nav | failed on `/forge/tools` only; the other three paths held | `TestingLibraryElementError: Unable to find role="navigation"` — the route falls through to the `ErrorBoundary`, which renders outside the `Shell`, so the missing landmark is what names it |
| 2026-08-30 | `router.test.tsx` "offers no way into the forge from the frame" | restored one `<Tab to="/forge/queue">Forge</Tab>` to `Shell.tsx` | failed | `AssertionError: expected [ '/forge/queue' ] to deeply equal []` — names the href that came back |

**Why two.** Deleting the tabs and deleting the routes both produce a green suite under either
guard alone: with only the no-way-in guard, removing the forge entirely passes; with only the
resolvability guard, leaving the tabs in place passes. The decision was *hidden, not removed*,
and it takes both to say so.

**The second guard's message is the better one**, and the first is worth a note. `Unable to find
role="navigation"` does not say *the route is gone* — it says the `Shell` did not render, and the
reason is one inference away (a route with no match renders `ErrorBoundary` as the layout's
`errorElement`, outside the nav). It was left as it is rather than given a `data-testid`, because
the alternative was making a component this phase does not own cooperate with a test; the
assertion on `ErrorBoundary`'s own heading text is in the same test and catches the case where a
route resolves to a *broken* component rather than to none.

## A class that animates nothing — 2026-08-30

Plan 4 phase 0, task 3. `tokens.test.ts` already caught an undefined `var()`; this is the same
silence one layer up. **The plan was wrong about what was missing.** It said the token guard
needed generalising from a `--hover` grep — it does not, it has walked every file and every
`var()` including fallback chains since 2026-08-24. What was missing was this.

| date | guard | what was reverted | what happened | message |
|---|---|---|---|---|
| 2026-08-30 | `tokens.test.ts` "defines every motion class the app wears" | renamed `.settle` to `.settled` in `main.css` — the rule stays, the name it is worn under does not | failed | `expected [ Array(1) ] to deeply equal []`, listing `".settle (src/home/Home.tsx)"` — names the class **and** the file wearing it |
| 2026-08-30 | `tokens.test.ts` "watches classes that are actually worn…" | made `wearing()`'s walk `continue` on every file, so it returns an empty map | failed | `AssertionError: expected 0 to be greater than 0` |

**The second row is the load-bearing one and the first is why.** When the walk was broken, the
guard above it **passed** — an empty map has nothing missing, so it reported green having checked
nothing. That is A67 exactly, and it is the shape W2 found in its batching test: a guard that
passes on the code it was written to reject is a green tick over an open hole. A scan-based guard
needs its anti-vacuity partner or it is decoration.

**Why an undefined class is worse than an undefined token.** A missing `var()` renders as
inherited and looks deliberate. A missing animation class renders as *nothing moves*, which looks
exactly like `prefers-reduced-motion` working correctly — so it is invisible to the one reader
most likely to check.

**What this guard cannot do**, recorded so nobody trusts it further than it goes: `MOVEMENTS` is a
closed list, so it catches a **deleted rule** and misses an **invented class**. That is deliberate
— `dashboard.md` §8 makes a sixth movement a design decision, and a guard that silently blessed
any new name would be arguing the opposite.

## The page body never scrolls sideways — 2026-08-30

Plan 4 phase 0, task 4.

| date | guard | what was reverted | what happened | message |
|---|---|---|---|---|
| 2026-08-30 | `tokens.test.ts` "keeps sideways scrolling inside the one container allowed to have it" | added `overflow-x: auto` to `body` in `main.css` — the well-meant fix somebody makes when one wide table clips | failed | `AssertionError: expected [ 'body', '.tbl' ] to deeply equal [ '.tbl' ]` — names the offending selector |

**The plan asked for a guard this environment cannot give, and the narrower one shipped instead.**
The step read *"assert `overflow-x` is not `auto` or `scroll` on any ancestor the Shell renders"* —
which sounds like a rendered-DOM assertion and would be one. There is no layout engine in
happy-dom, so a test phrased that way would compute nothing and pass, which is the exact shape
this ledger's 2026-08-24 entry warns about. What it checks instead is the declarations it can
see: `.tbl` is the only rule in the design system that declares `overflow-x`, and `Shell.tsx`
declares none.

**What it deliberately does not police:** a component scrolling its own `<pre>`. Three do — a
drift excerpt, gate output, an artifact excerpt — and that is rule 2 working rather than a breach
of it, because wide content is supposed to scroll in its own container.

## The silent 500, and a revert that proved nothing — 2026-08-30

Plan 4 phase 0, task 5. The defect the whole phase exists for: on 2026-08-29 a hand-drawn
pipeline was walked end to end, *Keep* answered 500, and **the rail did not change** — nothing on
screen, nothing in the console, `docker logs` the only way to learn the page's central action had
failed.

| date | guard | what was reverted | what happened | message |
|---|---|---|---|---|
| 2026-08-30 | `Walk.test.tsx` "says so when a step's mutation failed…" + "keeps a coded refusal lookup-able…" | deleted the `{error && …}` block and its `Failed` import from `Walk.tsx` — the surface, restoring the 2026-08-29 state exactly | both failed | `expect(element).toHaveTextContent()` naming the missing string |
| 2026-08-30 | `Walk.tsx`'s required `error` prop (type, not test) | — nothing; making it required was itself the experiment | `tsc` named **all three** forgetful call sites in `Builder.tsx` plus eight fixtures | `TS2741: Property 'error' is missing in type … but required in type …` |
| 2026-08-30 | `reported.test.ts` "hands an error back from every mutation hook" | rewrote `usePropose` to `const m = useMutation(…); return { propose: m.mutate }` — a hook that keeps the error to itself | failed | `expected [ 'api/usePropose.ts' ] to deeply equal []` |
| 2026-08-30 | `reported.test.ts` "references that error in every component that calls one" | renamed every `error` to `refusal` in `forge/Decide.tsx`, leaving zero references | failed | `expected [ 'forge/Decide.tsx' ] to deeply equal []` |

**The second row is the real fix and it is not a test.** A hook that returns an error cannot make
a caller read it; a required prop can. `useKeep` had returned `error` since 3E with a docstring
reading *"Shown, not swallowed"* — and `Builder.tsx` never passed it, into a `keep` prop that had
no slot for it. One call site, one dropped field, and no scan could have seen it.

### The miss, which is worth more than the four rows above

**A revert was run that did not reach the code the guard names, and the guard passed.** That is
question 3 of this file's own three, and it was answered wrongly for a full cycle.

The first version of this guard asserted a *string* — that each hook's source contained `error:`
— and carried an `UNREPORTED` debt list of six forge hooks it claimed were silent. To watch it
fail, `usePropose` was edited by `s.replace('  return {', …)`. **`usePropose` contains no
`return {`**: it returns `useMutation(…)` directly. The edit applied nowhere, the file was
unchanged, the test passed, and it was very nearly recorded as watched-failing.

Two things came out of catching it:

- **The finding it was built on was false.** All six "silent" hooks return the `useMutation`
  result *whole*, which carries `.error` to the caller, and every forge consumer references one.
  There was never a debt list — the six were classified by grepping for a string rather than by
  reading what the function returns. `CLAUDE.md` already records this exact habit costing a bug:
  *in the same audit I verified one fact by reading the generator and took the other from a
  comment, and only one of those habits found a bug.*
- **A debt list built on a bad measurement is worse than no guard**, because it would have shipped
  six files permanently labelled broken and exempted from the check that says so.

The guard was rewritten to test the property that actually holds — a hook hands back an error
either by returning the mutation or by mapping it onto a field — and both reverts above were
verified to land (`grep -c` on the edited file) **before** the run was believed.

## One curve was three, and only the build could say so — 2026-08-30

Plan 4 phase 0, task 2, found during final verification rather than while writing the task.

| date | guard | what was reverted | what happened | message |
|---|---|---|---|---|
| 2026-08-30 | `tokens.test.ts` "declares one easing curve, in the source" | replaced `transition-colors` in `Shell.tsx` with an explicit `ease-[cubic-bezier(.4,0,.2,1)]` — verified landed with `grep -c` before believing the run | failed | names the curve **and** the file: `"cubic-bezier(.4,0,.2,1) (src/app/Shell.tsx)"` |

**The phase's own headline constraint was false in the shipped artifact while every test was
green.** `tokens.css` declared one curve. `dist/assets/*.css` carried three: eleven components
reach for Tailwind's `transition-colors` and one for `animate-pulse`, and each emits Tailwind's
own easing rather than ours. Nothing in the repository compiles the stylesheet — not `vitest`,
not `tsc` — so there was no test that could have been wrong about this, which is a different
thing from a test being wrong.

Found by `npm run build` followed by `grep -o 'cubic-bezier([^)]*)' dist/assets/*.css | sort -u`.
That command is now in `dashboard.md` §8, because it is the only place the claim is checkable and
it needs a production build, so it cannot live in the unit suite.

Fixed with two `@theme` overrides — `--default-transition-timing-function` and `--animate-pulse`
— rather than by rewriting twelve call sites, so the next `transition-colors` somebody types is
right without them knowing any of this happened.

**The guard needed comment-stripping on its first run**, and that is worth a line. Both initial
failures were the guard catching the *documentation* of the curves that had just been replaced —
this file's own comments quote the old values, which is the habit the rest of this repository
asks for. A scan that cannot tell a declaration from prose punishes writing down what you
changed.
