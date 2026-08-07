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
