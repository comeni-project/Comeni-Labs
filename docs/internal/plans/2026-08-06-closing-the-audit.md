# Closing the 2026-08-06 Audit Implementation Plan

> **Plan 1.8.** Execute after Plan 1.7 (complete) and **before** Plan 2. It exists because the
> audit in [`docs/internal/audits/2026-08-06-plan-1-to-1.7-audit.md`](../audits/2026-08-06-plan-1-to-1.7-audit.md)
> found thirteen defects and closed none of them. Read that document first: every task here is
> named for the finding it closes, and the finding is where the reproduction lives.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this
> plan task-by-task, sequentially, driving it yourself. Steps use checkbox (`- [ ]`) syntax for
> tracking. Do **not** farm the tasks out with subagent-driven-development — subagents are for
> review and design only. This matches the execution decision recorded in `CLAUDE.md`.

**Goal:** Close A1–A13. When this plan is done, a guard that says "cannot" either can or does
not say it; a lockfile pins the bytes that were loaded; and a decision that was resolved is a
decision the pipeline made.

**Architecture:** No new subsystem and no new dependency. Nine of the thirteen fixes move a
check that lives in one caller into the type that should have been enforcing it — the same
shape of move, over and over, and that repetition is the finding behind the findings. Two
(A8, A4) change a signature or a type's home. One (A1) admits that a static check cannot make
the claim CLAUDE.md makes for it, and replaces the claim rather than the check.

**Tech Stack:** Python 3.12, Pydantic v2, pytest, ruff, `uv` workspace. No AI, no network, no
new dependency. `sys.addaudithook` (stdlib, test-only) is the one new mechanism.

## Global Constraints

- **`comeni-core` and `mendel-resolver` are under a closed allowlist** in `tests/test_purity.py`.
  Verified present today: `collections`, `collections.abc`, `datetime`, `enum`, `hashlib`,
  `pathlib`, `typing`, `pydantic`, `yaml`. Task 5 reads a YAML manifest from `comeni-core` and
  needs nothing added. **No task in this plan may widen the allowlist** — if one appears to, the
  fix is in the wrong package.
- **Every fix ships with a guard that was watched failing.** This is not a style preference: the
  2026-08-03 audit's holes and four of this audit's were found by breaking a guard on purpose.
  A step that says "watch it fail" is a step, not a suggestion, and the expected failure message
  is written into the plan so a wrong failure is visible as a wrong failure.
- **Determinism is a test.** Anything serialising a `frozenset` needs a sorting
  `field_serializer`. Task 1 sorts a list inside a validator and Task 5 changes what a layer is
  called; both move golden bytes, and both must move them *once*, in their own commit.
- Ruff line length 100. `make check` passes before every commit. `make -j1 check`, unfiltered —
  `MAKEFLAGS` carries `-j12`, so a piped parallel run has hidden a lint failure before.
- **Do not fix a finding beyond its scope.** A3 gets a stopgap here and its real fix in Plan 2
  Task 11; A2's clinical question and A4's cost question were decided by the operator on
  2026-08-06 and those decisions are recorded per-task. Widening a task is how a plan stops
  being reviewable.

---

## File Structure

```
packages/comeni-core/src/comeni_core/
├─ profile.py              MODIFY — A13: reject duplicate measurements, sort
├─ contract.py             MODIFY — A11: reject duplicate params; A10: extra="forbid" ×6
├─ digest.py               MODIFY — A9: a layer may not contain a symlink
├─ lockfile.py             MODIFY — A12: layer name from the manifest
├─ layer.py                NEW    — A12: the manifest, read in one place
├─ gates.py                NEW    — A4: Gate moves here so a bundle can carry one
├─ egress.py               MODIFY — A4: PublishBundle.gate
├─ marks.py                MODIFY — A3: ParamLiteral gains a shape check
packages/mendel-resolver/src/mendel_resolver/
├─ resolve.py              MODIFY — A2: validate the profile; A8: apply the resolution
├─ router.py               MODIFY — A8: resolve the ambiguity where it is created
├─ layers.py               MODIFY — A9 + A12: refuse symlinks, name from the manifest
packages/mendel-compiler/src/mendel_compiler/
├─ gates.py                MODIFY — A4: Gate becomes a re-export shim
├─ emit.py                 MODIFY — A11: sort on the key alone
├─ cli.py                  MODIFY — A2: drop the belt-and-braces re-route; A4: record the gate
├─ conformance.py          MODIFY — A5: report a cross-layer selection
tools/
├─ check_registry_drift.py MODIFY — A7: compare the manifest
tests/
├─ test_purity_runtime.py  NEW    — A1: the assertion that actually holds
├─ test_audit_regressions.py NEW  — one test per finding, named for it
CLAUDE.md                  MODIFY — A1: invariant 1 says what is enforced
```

**Ordering rationale.** Tasks 1–3 are mechanical and make the registry fail loudly, so every
later task runs against data that has stopped lying. Task 4 removes the CLI's belt-and-braces
profile check and must come *after* nothing else depends on it. Task 5 changes what a layer is
called, which moves lockfile bytes, so it is isolated. Task 6 is the largest and changes a
signature Plan 2 builds on. Tasks 8–10 are the egress boundary and can only be done once Task 6
has settled what a `DecisionRecord` contains. Task 11 is last of the code tasks because it
rewrites a claim in `CLAUDE.md` that the preceding ten tasks are the evidence for.

**Out of scope, and why.**

- **A3's real fix — parameters as closed vocabulary.** Decided 2026-08-06: recommendation 2,
  *in Plan 2 Task 11*, where `Param`'s domain was deliberately left to be designed. Task 9 here
  is the stopgap only, and says so in its own docstring so nobody mistakes it for the answer.
- **Issue #2 (`sealed` must block tier-3 on asserted measurements).** Needs Plan 2's
  `ProfilePolicy`. Task 4 gets closer to it by making validation structural, and stops there.
- **A second audit round.** Task 12 sets it up; it is not part of this plan's execution. The
  exit criterion, decided 2026-08-06, is **no critical findings survive** — important and minor
  findings get filed and carried, rather than looping until an audit comes back empty, which no
  audit in this repository ever has.

---

### Task 1: A13 + A11 — a type may not accept a duplicate it cannot act on

Two findings, one shape. `DataProfile` accepts two `Measured` entries naming the same
measurement and `get` returns the first; `ModuleContract` accepts two `Param`s with the same
name and the emitter dies sorting them. In both cases the validated construction path already
normalises — `MeasurementRegistry.profile()` takes a `dict` and sorts it — and the
*deserialised* path does not. A type whose two constructors disagree has one constructor too
many.

`Registry.load` already refuses a contract ID declared twice in one layer, with the reason
written out: resolving it by glob order would be a silent arbitrary pick. That argument applies
one level down and was not made there.

**Files:**
- Modify: `packages/comeni-core/src/comeni_core/profile.py`
- Modify: `packages/comeni-core/src/comeni_core/contract.py`
- Modify: `packages/mendel-compiler/src/mendel_compiler/emit.py`
- Test: `tests/test_audit_regressions.py` (new)

**Interfaces:**
- Consumes: nothing new
- Produces: `ValidationError` on a duplicate, from both types

- [ ] **Step 1: Write the failing tests**

Create `tests/test_audit_regressions.py`. It gains one section per finding as the plan
proceeds; this task writes the header and the first two.

```python
"""One test per finding in the 2026-08-06 audit, named for it.

Kept in one file rather than scattered into the suites they belong to, because the
question a reader has is "is A9 still closed?" and the answer should not require knowing
which module A9 was about. Each test carries the finding's one-line summary.
"""

import pytest
from pydantic import ValidationError


def test_a13_a_profile_rejects_a_duplicate_measurement():
    """A13 — `get` was first-wins, so list order changed the pipeline."""
    from comeni_core.profile import DataProfile

    with pytest.raises(ValidationError, match="strandedness"):
        DataProfile.model_validate(
            {
                "measurements": [
                    {"measurement": "strandedness", "value": "reverse"},
                    {"measurement": "strandedness", "value": "unstranded"},
                ]
            }
        )


def test_a13_a_profile_sorts_so_the_same_facts_are_the_same_profile():
    """Order must not survive validation, or two equal profiles compare unequal."""
    from comeni_core.profile import DataProfile

    forward = DataProfile.model_validate(
        {"measurements": [{"measurement": "a", "value": 1}, {"measurement": "b", "value": 2}]}
    )
    backward = DataProfile.model_validate(
        {"measurements": [{"measurement": "b", "value": 2}, {"measurement": "a", "value": 1}]}
    )
    assert forward.model_dump_json() == backward.model_dump_json()


def test_a11_a_contract_rejects_a_duplicate_param_name():
    """A11 — two bindings of one name reached `sorted` and compared two ResolvedValues."""
    from comeni_core.contract import ModuleContract

    with pytest.raises(ValidationError, match="threads"):
        ModuleContract.model_validate(
            {
                "id": "audit/dup@1.0.0",
                "nf_process": "DUP",
                "nf_include": "./modules/dup/main",
                "params": [{"name": "threads", "default": 4}, {"name": "threads", "default": 8}],
                "provenance": {
                    "source": "audit",
                    "drafted_by": "audit",
                    "approved_by": "audit",
                    "approved_at": "2026-08-06",
                },
            }
        )


def test_a11_the_emitter_never_compares_two_resolved_values():
    """Belt and braces: the sort key is the name, so a tie cannot reach the value."""
    from comeni_core.ir import IRNode, ResolvedValue, Tier

    node = IRNode(
        id="n",
        contract_id="audit/x@1.0.0",
        selection=ResolvedValue(value="audit/x@1.0.0", tier=Tier.STRUCTURAL, reason="r"),
    )
    node.set_param("threads", ResolvedValue(value=1, tier=Tier.CONVENTION, reason="a"))
    node.set_param("threads", ResolvedValue(value=2, tier=Tier.CONVENTION, reason="b"))
    # No exception: emit.py must not fall through to comparing the values.
    assert sorted(((b.name, b.value) for b in node.params), key=lambda pair: pair[0])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_audit_regressions.py -v`
Expected: the two `pytest.raises` tests FAIL with `DID NOT RAISE`; the sort test PASSES already
(it exercises the fixed expression, not the code) and the ordering test FAILS on unequal JSON.

- [ ] **Step 3: `DataProfile` normalises in the validator, not in one constructor**

In `packages/comeni-core/src/comeni_core/profile.py`, extend `_accept_mapping` with a second
validator that runs on the list form too:

```python
    @model_validator(mode="after")
    def _one_entry_per_measurement(self) -> "DataProfile":
        """Reject a repeated measurement, and sort.

        `MeasurementRegistry.profile()` takes a `dict` and sorts it, so the validated path
        was always normalised and the deserialised path never was. `get` returns the first
        match, so two profiles asserting the same facts in different order resolved to
        different pipelines — invariant 10 held literally (same `Goal`, same bytes) and
        failed in the sense anyone would rely on. Audit 2026-08-06, A13.
        """
        names = [m.measurement for m in self.measurements]
        repeated = sorted({n for n in names if names.count(n) > 1})
        if repeated:
            raise ValueError(
                f"a profile may state each measurement once; repeated: {', '.join(repeated)}"
            )
        self.measurements.sort(key=lambda m: m.measurement)
        return self
```

- [ ] **Step 4: `ModuleContract` refuses a duplicate param name**

In `packages/comeni-core/src/comeni_core/contract.py`, on `ModuleContract`:

```python
    @model_validator(mode="after")
    def _one_binding_per_param(self) -> "ModuleContract":
        """`IRNode.set_param` appends, so a duplicate here became two bindings there.

        `Registry.load` already refuses a contract ID declared twice in one layer, because
        resolving it by glob order would be the silent arbitrary pick invariant 8 exists to
        prevent. Same argument, one level down. Audit 2026-08-06, A11.
        """
        names = [p.name for p in self.params]
        repeated = sorted({n for n in names if names.count(n) > 1})
        if repeated:
            raise ValueError(f"{self.id} declares {', '.join(repeated)} more than once")
        return self
```

- [ ] **Step 5: The emitter sorts on the key alone**

In `packages/mendel-compiler/src/mendel_compiler/emit.py`, line ~194:

```python
                for name, value in sorted(
                    ((b.name, b.value) for b in node.params), key=lambda pair: pair[0]
                )
```

with a comment naming why the key is explicit — a tuple sort falls through to the second
element, and `ResolvedValue` is not orderable. Task 1 makes a tie unreachable; this makes it
harmless if it ever becomes reachable again.

- [ ] **Step 6: Run the tests and the full gate**

Run: `uv run pytest tests/test_audit_regressions.py -v && make -j1 check`
Expected: all four pass; 305 existing tests still pass. If any golden file moved, **stop** —
the shipped registry declares no duplicate params and every profile already reaches
`DataProfile` sorted, so a moved byte means one of those assumptions is wrong and the plan is
wrong rather than the code.

- [ ] **Step 7: Commit**

`fix(core): a type may not accept a duplicate it cannot act on — A11, A13`

---

### Task 2: A10 — a contract is pinned by its file, not by what survived parsing

`digest_of` hashes `model.model_dump_json()`. Of the six models a contract is built from, only
`Alternative` sets `extra="forbid"`, so Pydantic's default `ignore` drops unknown keys before
the dump runs and two materially different files pin to one digest. The lockfile's stated
promise — *"this pipeline was built against exactly this contract"* — is not kept.

The larger cost is not the lockfile. **A misspelled key in a contract loads clean today.**
`ext_arg:` for `ext_args:`, `state:` for `states:` — accepted, behaves differently from what it
says, and conformance checking cannot see it because conformance compares a contract to its
*module* and this is a contract disagreeing with itself.

**Verified before writing this task:** `extra="forbid"` on all six rejects **zero** contracts in
the shipped registry. Every declared key in `registry/contracts/**` is a field. This is a
one-line-per-model change with no data migration.

**Files:**
- Modify: `packages/comeni-core/src/comeni_core/contract.py`
- Test: `tests/test_audit_regressions.py`

- [ ] **Step 1: Write the failing test**

```python
def test_a10_an_unknown_contract_key_is_refused():
    """A10 — dropped keys meant two different files pinned to one digest."""
    from comeni_core.contract import ModuleContract

    base = {
        "id": "audit/x@1.0.0",
        "nf_process": "X",
        "nf_include": "./modules/x/main",
        "provenance": {
            "source": "audit", "drafted_by": "audit",
            "approved_by": "audit", "approved_at": "2026-08-06",
        },
    }
    with pytest.raises(ValidationError, match="clinical_use"):
        ModuleContract.model_validate({**base, "clinical_use": "approved"})
    with pytest.raises(ValidationError, match="ext_arg"):
        ModuleContract.model_validate({**base, "ext_arg": "--misspelled"})


def test_a10_two_contract_files_cannot_share_a_digest():
    """The property the lockfile actually sells."""
    from comeni_core.contract import ModuleContract
    from comeni_core.digest import digest_of

    base = {
        "id": "audit/x@1.0.0", "nf_process": "X", "nf_include": "./modules/x/main",
        "provenance": {
            "source": "audit", "drafted_by": "audit",
            "approved_by": "audit", "approved_at": "2026-08-06",
        },
    }
    plain = ModuleContract.model_validate(base)
    with pytest.raises(ValidationError):
        ModuleContract.model_validate({**base, "validated_by": "Dr Nobody, 2019"})
    assert digest_of(plain)  # the honest file still pins
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_audit_regressions.py -k a10 -v`
Expected: FAIL with `DID NOT RAISE` on both.

- [ ] **Step 3: Forbid extras on all six**

Add `model_config = ConfigDict(extra="forbid")` to `InputPort`, `OutputPort`, `Param`,
`NfInput`, `Provenance` and `ModuleContract`. `Alternative` already has it — match its comment
style and point at the finding:

```python
    # Pydantic ignores unknown keys by default, so `ext_arg:` for `ext_args:` loaded clean
    # and behaved differently from what it said, and `digest_of` pinned what survived
    # parsing rather than the file. Audit 2026-08-06, A10. Verified: this rejects nothing
    # in the shipped registry.
    model_config = ConfigDict(extra="forbid")
```

- [ ] **Step 4: Prove the registry is clean**

Run: `uv run pytest tests/test_spine_contracts.py tests/test_registry_layer.py -v && make -j1 check`
Expected: green. A contract that now fails is a contract that was lying; fix the contract, do
not relax the config.

- [ ] **Step 5: Commit**

`fix(core): forbid unknown keys in every contract model — A10`

---

### Task 3: A9 — a layer may not contain a symlink

The Plan 1.7 hardening hashes a symlink as its target path and never follows it. That is
correct for a link pointing out of the layer, and it is what git does. But `Registry.load`
opens the same path with `read_text()`, which **does** follow it. The bytes routed on and the
bytes pinned are different bytes.

Reproduced in the audit: a contract replaced by a symlink, its target's `priority` raised to
999, and the layer digest **byte-identical**. Zero drift from `mendel upgrade`. This is
invariant 11's closing sentence defeated by the mechanism written to uphold it, and it is worse
than A5 because A5 at least moves the lockfile.

**The fix is to refuse, not to follow.** A layer is a unit strangers distribute; a link out of
it is already meaningless to whoever receives it, and a link *inside* it is a duplicate file
with extra steps. Refusing is smaller than resolving, and it fails at load time with a message
instead of at publish time with a wrong digest.

**Files:**
- Modify: `packages/comeni-core/src/comeni_core/digest.py`
- Modify: `packages/mendel-resolver/src/mendel_resolver/layers.py`
- Test: `tests/test_audit_regressions.py`

- [ ] **Step 1: Write the failing test**

```python
def test_a9_a_symlinked_contract_is_refused_by_the_digest(tmp_path):
    """A9 — the registry read through it; the digest hashed its target path."""
    from comeni_core.digest import digest_of_directory

    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "real.yml").write_text("id: alpha\n")
    layer = tmp_path / "layer" / "contracts"
    layer.mkdir(parents=True)
    (layer / "c.yml").symlink_to(outside / "real.yml")

    with pytest.raises(ValueError, match="symlink"):
        digest_of_directory(tmp_path / "layer")


def test_a9_a_symlinked_layer_is_refused_at_load(tmp_path):
    """The message must arrive at load, not at publish."""
    import shutil

    from mendel_resolver import layers as layers_mod

    layer = tmp_path / "lab"
    shutil.copytree("registry", layer)
    victim = next((layer / "contracts").rglob("*.yml"))
    body = victim.read_text()
    (tmp_path / "elsewhere.yml").write_text(body)
    victim.unlink()
    victim.symlink_to(tmp_path / "elsewhere.yml")

    with pytest.raises(ValueError, match="symlink"):
        layers_mod.load(layer)
```

- [ ] **Step 2: Run to verify both fail**

Run: `uv run pytest tests/test_audit_regressions.py -k a9 -v`
Expected: FAIL with `DID NOT RAISE`. **Before fixing, re-run the audit's reproduction** and
confirm the digest is unchanged across a target rewrite — the finding is only closed if you
have seen it open.

- [ ] **Step 3: The digest refuses a symlink**

In `digest.py`, replace the symlink branch. Delete `_LINK` and rewrite the docstring paragraph
that justified it — the fix it describes was right about the hazard and wrong about the remedy,
and leaving the old reasoning in place would mislead the next reader:

```python
        for entry in sorted(p for p in path.rglob("*") if p.is_symlink() or p.is_file()):
            if entry.is_symlink():
                raise ValueError(
                    f"{entry.relative_to(path)} is a symlink; a registry layer may not "
                    "contain one. The loader follows it and this digest cannot, so the "
                    "bytes routed on would not be the bytes pinned (audit 2026-08-06, A9)."
                )
```

Keep `_FILE`: domain separation still matters the moment a second entry kind is ever added, and
the tag is already in every digest ever written.

> **A symlinked *directory* is consistent rather than exploitable** — `rglob` does not descend
> into one, so neither the digest nor `Registry.load` sees anything inside it. Verified during
> the audit. It is still refused by the check above, because "the layer contains a link" is a
> simpler rule to state than "the layer contains a link to a file".

- [ ] **Step 4: The loader refuses it too, and earlier**

In `mendel_resolver/layers.py`, at the top of `load()`, after `layers` is normalised to
`Path`s — one loop, so the error names the layer rather than the digest:

```python
    for layer in layers:
        for entry in sorted(layer.rglob("*")):
            if entry.is_symlink():
                raise ValueError(
                    f"registry layer {layer} contains a symlink at "
                    f"{entry.relative_to(layer)}. A layer is a unit that is distributed; a "
                    "link out of it is meaningless to whoever receives it, and a link inside "
                    "it is a copy with extra steps. Audit 2026-08-06, A9."
                )
```

- [ ] **Step 5: Run the gate, and re-run the audit reproduction**

Run: `uv run pytest tests/test_audit_regressions.py -k a9 -v && make -j1 check`
Then re-run the audit's symlink script and confirm it now raises rather than reporting an
unchanged digest.

- [ ] **Step 6: Commit**

`fix(core): a registry layer may not contain a symlink — A9`

---

### Task 4: A2 — the profile is validated by the resolver, not by one CLI branch

`Goal.model_validate` builds an unvalidated `DataProfile`; `MeasurementRegistry.profile()` is
the only validating constructor and `resolve()` never routes through it. The CLI's `build`
branch re-routes as belt and braces — and `mendel upgrade` takes `previous.goal` verbatim, so
the one verb that reads a **foreign file** is the one verb with no check. Reproduced: a bundle
carrying `sample_name: PATIENT-00417` upgraded to exit 0 with the string in the new IR.

CLAUDE.md invariant 15 says the guard "moved rather than weakened". It moved into an
application-layer step in `mendel-compiler`, which is not a property of anything. The fix is to
put it where nothing can route around it: `resolve()` cannot resolve a profile it has not
checked.

**Files:**
- Modify: `packages/mendel-resolver/src/mendel_resolver/resolve.py`
- Modify: `packages/mendel-compiler/src/mendel_compiler/cli.py`
- Modify: `packages/mendel-resolver/src/mendel_resolver/__init__.py`
- Test: `tests/test_audit_regressions.py`

**Interfaces:**
- Consumes: `comeni_core.measurement.MeasurementRegistry`
- Produces: `resolve(goal, registry, rules, measurements, ...)` — a **required** parameter

**Verified before writing this task:** `resolve()` has eight call sites — `cli.py:150`,
`mendel_resolver/__init__.py:15`, `tests/test_runnable.py` ×3, `tests/test_spine_contracts.py`,
`tests/test_lockfile.py`, `packages/comeni-core/tests/test_ir_profile.py` ×2. Every one already
holds a `Layers`, so every one has `loaded.measurements` to hand. **Make it required, not
optional with a default of `None`** — an optional guard is a guard the next verb forgets, which
is the finding.

- [ ] **Step 1: Write the failing test**

```python
def test_a2_resolve_refuses_an_unvalidated_profile():
    """A2 — invariant 15 lived in one CLI branch; `upgrade` did not pass through it."""
    from comeni_core.goal import Goal
    from mendel_resolver import layers as layers_mod
    from mendel_resolver.resolve import resolve

    loaded = layers_mod.load("registry")
    goal = Goal.model_validate(
        {
            "have": [{"type_id": "fastq.reads"}],
            "want": ["counts.matrix"],
            "profile": {"measurements": [{"measurement": "sample_name", "value": "PT-4471023"}]},
        }
    )
    with pytest.raises(ValueError, match="sample_name"):
        resolve(goal, loaded.registry, loaded.rules, loaded.measurements)


def test_a2_upgrade_refuses_a_bundle_carrying_an_undeclared_measurement(tmp_path):
    """The reachable route: a bundle is a downloaded artifact."""
    # Build the tainted bundle by hand, run `mendel upgrade`, assert a non-zero exit
    # and that nothing was written to --out. Mirrors tests/test_upgrade.py's fixtures.
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_audit_regressions.py -k a2 -v`
Expected: FAIL — `resolve()` takes no `measurements` argument yet, so a `TypeError`. That is the
right failure: fix the signature, then watch it fail on `DID NOT RAISE`, then fix the check.
Two failures, both watched.

- [ ] **Step 3: `resolve()` validates what it was handed**

```python
def resolve(
    goal: Goal,
    registry: Registry,
    rules: RuleTable,
    measurements: MeasurementRegistry,
    resolver: AmbiguityResolver | None = None,
    layer_names: Sequence[str] = (),
) -> PipelineIR:
    # Invariant 15 lived in `mendel build`'s own re-route, so `mendel upgrade` — the one
    # verb that reads a file somebody else wrote — skipped it entirely, and a bundle
    # carrying `sample_name: PATIENT-00417` resolved to exit 0. A guard in a caller is a
    # guard the next caller forgets. Audit 2026-08-06, A2.
    for measured in goal.profile.measurements:
        measurements.check(measured.measurement, measured.value)
```

Required rather than defaulted, and placed before `route()` so nothing is built from a profile
that has not been checked.

- [ ] **Step 4: Update all eight call sites**

Each already has a `Layers`; pass `loaded.measurements`. No call site needs new plumbing —
that is why this is the right place for the check.

- [ ] **Step 5: Delete the CLI's belt and braces**

In `cli.py` (lines ~142–148), remove the re-route through `.profile()`, leaving a comment
saying where the check went and why it is no longer here. **Leave `mendel upgrade` alone** — it
inherits the fix through `resolve()`, which is the entire point.

- [ ] **Step 6: Watch invariant 15's own guard still hold**

Run: `uv run pytest tests/test_construction.py tests/test_egress.py tests/test_purity.py -v`
Then delete the new `measurements.check` loop and confirm `test_a2_...` fails. Restore.

- [ ] **Step 7: Run the gate and commit**

`fix(resolver): resolve() validates the profile it was handed — A2`

---

### Task 5: A12 + A7 — a layer is called what its manifest says

Layer identity is `Path.name` — in `layers.py:68` and `lockfile.py:77`. `--registry .` records
`name: ''` into a published bundle and every `ShadowRecord` in it; renaming a checkout reports
*"the layer stack changed"* against an unchanged pipeline. And `tools/check_registry_drift.py`
uses `registry.yml` only to check the target *is* a layer, never comparing it, so `name`,
`version` and `licence` can diverge between the two repositories undetected.

Both halves are the same omission: **the manifest exists and nothing reads it.** Plan 1.7 added
it for exactly this reason — *"a layer that moves to its own repository cannot rely on the
directory it happened to be checked out into"*.

> **This task moves golden bytes.** The shipped manifest says `name: comeni-registry-examples`,
> not `registry`. Every lockfile, every `ShadowRecord` and every `PipelineIR.registry_layers`
> will change. That is the fix working. Commit it alone, and regenerate goldens in the same
> commit so the diff shows a name change and nothing else.

**Files:**
- Create: `packages/comeni-core/src/comeni_core/layer.py`
- Modify: `packages/comeni-core/src/comeni_core/lockfile.py`
- Modify: `packages/mendel-resolver/src/mendel_resolver/layers.py`
- Modify: `tools/check_registry_drift.py`
- Test: `tests/test_audit_regressions.py`, `tests/test_registry_drift.py`

**Interfaces:**
- Produces: `comeni_core.layer.LayerManifest`, `layer_name(path) -> LayerName`
- `yaml` is already on `comeni-core`'s purity allowlist — verified; nothing widens.

- [ ] **Step 1: Write the failing tests**

```python
def test_a12_a_layer_is_named_by_its_manifest():
    """A12 — the basename is not an identity."""
    from comeni_core.layer import layer_name

    assert layer_name("registry") == "comeni-registry-examples"


def test_a12_a_renamed_checkout_is_not_drift(tmp_path):
    """The property: a `mv` must not read as a changed registry."""
    import shutil

    from comeni_core.lockfile import Lockfile

    a = tmp_path / "registry"
    shutil.copytree("registry", a)
    locked = Lockfile.of(contracts={}, layers=[a])
    b = tmp_path / "renamed-by-the-recipient"
    a.rename(b)
    assert locked.drift_against(contracts={}, layers=[b]) == []


def test_a12_a_layer_without_a_manifest_falls_back_to_its_basename(tmp_path):
    """An overlay a lab made by hand is ordinary, not broken."""
    from comeni_core.layer import layer_name

    (tmp_path / "lab-overlay" / "contracts").mkdir(parents=True)
    assert layer_name(tmp_path / "lab-overlay") == "lab-overlay"


def test_a7_the_drift_detector_compares_the_manifest(tmp_path):
    """A7 — name, version and licence could diverge between the two repositories."""
    # Copy registry/ twice, change `licence` in one, assert the tool exits non-zero
    # and names `licence` in its output. Mirrors tests/test_registry_drift.py.
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_audit_regressions.py -k "a12 or a7" -v`
Expected: `ModuleNotFoundError: comeni_core.layer`.

- [ ] **Step 3: One reader for the manifest**

Create `packages/comeni-core/src/comeni_core/layer.py` with a `LayerManifest` model
(`extra="forbid"`, per Task 2's rule applied to a type written after it) holding `name`,
`version`, `licence`, `kinds`, `description`, and:

```python
def layer_name(path: Path | str) -> LayerName:
    """What this layer is called — its manifest's name, or its directory's.

    The basename is not an identity: `--registry .` yields `''`, and renaming a checkout
    read as a changed registry against an unchanged pipeline. `registry.yml` was added in
    Plan 1.7 for exactly this reason. Falling back to the basename keeps a hand-made
    overlay with no manifest working, which is the common private case.
    Audit 2026-08-06, A12.
    """
```

- [ ] **Step 4: Both call sites read it**

`layers.py:68` — `names=[layer_name(layer) for layer in with_contracts]`.
`lockfile.py:77` and the `drift_against` comparison at ~125 — `name=layer_name(path)`.
Keep the positional comparison exactly as it is; Plan 1.7 got that right and the reason is in
its comment.

- [ ] **Step 5: The drift detector compares the manifest**

In `tools/check_registry_drift.py`, load both manifests through `LayerManifest` and report a
field-by-field difference, `licence` included. It already loads one to check the target is a
layer; this is that load plus a comparison.

- [ ] **Step 6: Regenerate goldens, in this commit**

Run: `make -j1 check`. Expect lockfile and bundle goldens to move `registry` →
`comeni-registry-examples`. **Read the diff** and confirm nothing else moved.

- [ ] **Step 7: Commit**

`fix(core): a registry layer is named by its manifest — A7, A12`

---

### Task 6: A8 — a resolved decision reaches the pipeline

The largest task, and the one with a deadline: Plan 2 plugs a model into `AmbiguityResolver`,
and today that port cannot change a module choice.

`router._choose` picks `ordered[0]` by id order, appends an `Ambiguity` to `plan.ambiguities`,
and returns. The resolver is not consulted. `resolve()` calls `resolver.resolve()` afterwards,
at the bottom of the function, and puts the answer into a `DecisionRecord` and **nowhere else** —
`ir.nodes` and `ir.edges` are already built. `_source_for` is worse: it calls the resolver at
line 160 and then writes `chosen=f"{chosen[0]}.{chosen[1]}"`, overwriting the answer in the very
statement that records it.

Three consequences, worst last: `ReplayResolver` cannot replay a module choice; a
`human_override` on a producer is accepted, recorded and ignored; and **a `DecisionRecord` can
state something the pipeline does not do**. The last is the serious one — a published bundle is
supposed to be the auditable object, and a reader has no way to notice it is wrong.

Nothing is wrong in output today, because `FlagOnlyResolver` returns the candidate the code
already picked. That is why this survived: the only shipped resolver agrees with the code that
ignores it.

**Files:**
- Modify: `packages/mendel-resolver/src/mendel_resolver/router.py`
- Modify: `packages/mendel-resolver/src/mendel_resolver/resolve.py`
- Test: `tests/test_audit_regressions.py`

**Interfaces:**
- Consumes: `route(goal, registry, rules, resolver, max_depth)` — the resolver moves *in*
- Produces: `RoutePlan.steps[].selection_reason` unchanged for the unambiguous path

- [ ] **Step 1: Write the failing tests — the invariant, not the instance**

The test that would have caught this on the day it was written is a *property*, so write that
rather than a scenario:

```python
def test_a8_every_producer_record_names_the_contract_that_was_selected():
    """A8 — the record could state a choice the pipeline did not make.

    Not a scenario test: this is the invariant the whole publish/replay story rests on,
    and `tests/test_upgrade.py::test_untouched_decisions_replay` asserted only that some
    record said `resolved_by == "replay"` — never that the replayed value reached the IR.
    """
    # Build against a registry with two tied producers (fixture below), assert for every
    # DecisionRecord whose subject starts "producer:" that some IRNode has
    # node.selection.value == record.chosen.


def test_a8_a_human_override_changes_which_module_is_emitted(tmp_path):
    """The curation property federation §4.3 sells, end to end."""
    # publish against two tied aligners -> ALIGNER_A; set human_override to aligner-b;
    # upgrade -> the emitted main.nf must call ALIGNER_B, and the record must agree.


def test_a8_an_edge_record_names_the_edge_that_was_built():
    """`_source_for` recorded `equally_good[-1]` while calling the resolver for nothing."""
```

Build the two-tied-producer fixture as a real temporary layer; the audit's reproduction scripts
under the session scratchpad are the model, but **write fresh ones into the repo** — a fixture
that only exists in a scratchpad is a fixture that is gone next week.

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_audit_regressions.py -k a8 -v`
Expected: the override test FAILS with `ALIGNER_A` still emitted; the record/selection property
FAILS on a mismatch. Capture the output into the commit message — this is the finding, and it
should be visible in the history rather than only in the audit.

- [ ] **Step 3: `route()` takes the resolver**

Thread `resolver: AmbiguityResolver` through `route()` into `_choose`. It is required, not
optional: an optional resolver is how the parameter path ended up being the only one that
worked.

- [ ] **Step 4: `_choose` resolves where it decides**

Replace the trailing block. The `Ambiguity` is still appended — the record is not going away —
but the resolver is asked *before* the return, and its answer selects from `ordered`:

```python
    ambiguity = Ambiguity(
        node_id=_node_id(ordered[0]),
        subject=f"producer:{type_id}",
        candidates=sorted(c.id for c in ordered),
        context={"states": sorted(states)},
    )
    plan.ambiguities.append(ambiguity)
    resolution = resolver.resolve(ambiguity)
    # The answer must select, not merely be recorded. Until 2026-08-06 this returned
    # ordered[0] and the resolver was consulted afterwards purely to fill in a
    # DecisionRecord, so a replayed or human-overridden module choice was accepted,
    # written into the published bundle, and discarded. Audit A8.
    chosen = next((c for c in ordered if c.id == resolution.chosen), ordered[0])
```

Falling back to `ordered[0]` when the resolver names a non-candidate is deliberate and matches
`ReplayResolver._still_applies`, which already rejects a forged override rather than trusting
it — verified clean during the audit. **Record what was actually chosen**, not what was asked
for, so the record cannot drift from the pipeline again.

- [ ] **Step 5: `resolve()` stops resolving twice**

The loop over `plan.ambiguities` at `resolve.py:85` must now build its `DecisionRecord` from the
resolution `route()` already obtained rather than calling the resolver a second time — a second
call is a second chance to disagree, and with a model behind the port it is also a second
charge. Carry the `Resolution` on the `Ambiguity`'s route step, or have `route()` return the
records; prefer whichever leaves `RoutePlan` a plain data object.

- [ ] **Step 6: `_source_for` uses the answer it asked for**

```python
        chosen = next(
            (s for s in equally_good if f"{s[0]}.{s[1]}" == resolution.chosen),
            equally_good[-1],
        )
```

and record `chosen` after it is selected, not before.

- [ ] **Step 7: Strengthen the test that missed it**

In `tests/test_upgrade.py`, `test_untouched_decisions_replay` asserts only that a record says
`resolved_by == "replay"`. Add the assertion that makes it mean something: the replayed value is
in the IR. Leave the original assertion — it is not wrong, it was incomplete.

- [ ] **Step 8: Run everything**

Run: `make -j1 check` and `uv run pytest -m slow` — this task changes module selection, so the
counts-matrix gate is the one that proves the spine still routes.
Expected: 305+ pass, `-m slow` still produces 124 genes with `-s 2 -p`.

- [ ] **Step 9: Commit**

`fix(resolver): a resolved decision selects, it does not merely get recorded — A8`

---

### Task 7: A5 — an overlay that changes a selection says so

Invariant 11 ends *"never let an installed overlay reroute a pipeline silently"*. An overlay
contract with a **different module key** is by definition not a shadow, so no `ShadowRecord` is
written; winning on priority rather than tying means invariant 8 never fires either. It is a
clean win, classified tier 2, review `none`, and the build output is indistinguishable from
normal. Reproduced with a rival sorter at priority 99.

The gap is between two documented rules: invariant 11 says never silently, invariant 8 covers
ties, and a priority win is neither. The aligner escaped only because a rule pins it — luck.

**Files:**
- Modify: `packages/comeni-core/src/comeni_core/registry.py` (a contract records its layer)
- Modify: `packages/comeni-core/src/comeni_core/ir.py` (`needs_review` lists it)
- Modify: `packages/mendel-compiler/src/mendel_compiler/cli.py` (stderr)
- Test: `tests/test_audit_regressions.py`

**Interfaces:** the information exists in `selection.reason` and `registry_layers`; what is
missing is *which layer a chosen contract came from*, which `Registry.load` knows and discards.
Carry it as a `dict[ContractId, LayerName]` on `Registry` rather than a field on
`ModuleContract` — a contract is content-addressed by Task 2 and must not gain a field that
depends on where it was found, or its digest becomes location-dependent and A10 reopens sideways.

- [ ] **Step 1: Write the failing test** — build with a rival sorter at priority 99 in an
      overlay; assert `ir.needs_review()` names the node and that the reason says which layer.
- [ ] **Step 2: Run to verify it fails** — expect `needs_review()` to list only
      `star_align.seq_platform`, exactly as the audit recorded.
- [ ] **Step 3:** `Registry` gains `layer_of: dict[ContractId, LayerName]`, populated in `load()`.
- [ ] **Step 4:** `resolve()` marks a selection from a non-base layer `ReviewLevel.ADVISORY` with
      a reason naming the layer. **Advisory, not required** — an overlay winning is the normal
      case for a lab that installed one, and making it block would train people to ignore it.
      Tier stays 2: the selection genuinely was a documented default. What changes is visibility.
- [ ] **Step 5:** `mendel build` prints the overlay-sourced selections on stderr.
- [ ] **Step 6:** Run the gate; commit `fix(resolver): an overlay-sourced selection is visible — A5`

---

### Task 8: A6 — the egress guard learns `Mapping` and `bytes`

`_mentions_mapping` tests `issubclass(origin, dict)`, and `collections.abc.Mapping` is a
**superclass** of `dict`, not a subclass — so a field typed `Mapping[MeasurementId, ParamValue]`
is a real dict at runtime with arbitrary keys, which is precisely the `{"patient_id": ...}` case
the guard's own docstring claims to forbid. And `bytes` is not `str`, not `dict`, not `Any`,
carries no `FreeText` marker, and appears nowhere in the guard.

Neither is present in a payload today, so nothing leaks. Both are one plausible field away — a
`signature: bytes` on a lockfile is an obvious addition, and A5's fix makes an attribution
mapping tempting.

**Files:**
- Modify: `tests/test_egress.py`
- Test: the guard is the test; the regression file gets the meta-assertion

- [ ] **Step 1: Watch the guard fail on purpose.** Add `attribution: Mapping[MeasurementId,
      ParamValue] = {}` and `signature: bytes = b""` to the real `PublishBundle`, run
      `uv run pytest tests/test_egress.py`, and confirm **7 passed**. This is the step; a guard
      fix written without seeing the hole is how A6 got written the first time.
- [ ] **Step 2:** Broaden the mapping check to `collections.abc.Mapping` (which catches `dict`,
      `MutableMapping`, `OrderedDict`, `Counter`), and add a rule banning `bytes`, `bytearray`
      and `memoryview` outright with the reason in the message: an unbounded channel for exactly
      the free text the boundary exists to contain.
- [ ] **Step 3:** Re-run with the two fields still present; expect **2 failures naming both**.
- [ ] **Step 4:** Revert the two fields. Re-run; expect green.
- [ ] **Step 5:** Commit `test(egress): Mapping and bytes are shapes the guard now knows — A6`

---

### Task 9: A3 — reject path-shaped parameter values (stopgap)

`ParamValue = int | float | bool | Annotated[str, ParamLiteral] | None`. `_has_bare_str` exempts
anything with `__metadata__`, so the `ParamLiteral` arm passes — but `ParamLiteral` is a marker
class with no closed domain and nothing enforcing provenance. On the unmodified repo, with no
monkeypatching, `DecisionRecord.chosen`, `.candidates[*]`, `.human_override` and `Measured.value`
all carried filesystem paths and a diagnosis into a `PublishBundle`. `human_override` is the
most pointed: it is explicitly the slot for a human's answer, and it is a wide-open string.

> **Decided 2026-08-06 (audit D1, recommendation 2 + 1).** The real fix is parameters as closed
> vocabulary, **in Plan 2 Task 11**, where `Param`'s domain was deliberately left to be designed.
> This task is recommendation 1 as a stopgap, because A3 is a live route into a published
> artifact and Plan 2 is not close. Write that into the code, so nobody mistakes the blocklist
> for the answer.

**Files:**
- Modify: `packages/comeni-core/src/comeni_core/marks.py`
- Test: `tests/test_audit_regressions.py`

- [ ] **Step 1: Write the failing test** — a `DecisionRecord` with
      `human_override="/data/patients/PT-4471023/S1_R1.fastq.gz"` must raise; one with
      `human_override="nf-core/star/align@2.7.11b"` must not.
- [ ] **Step 2: Run to verify it fails.**
- [ ] **Step 3:** Attach an `AfterValidator` to the `ParamLiteral` arm rejecting a leading `/`
      or `~`, a `..` segment, and known sequencing-file suffixes (`.fastq`, `.fq`, `.bam`,
      `.cram`, `.vcf`, with or without `.gz`). Docstring states plainly that this is a blocklist,
      that a blocklist is not a guarantee, and that Plan 2 Task 11 replaces it.
- [ ] **Step 4: Check it against the shipped registry** — run `make -j1 check` and confirm no
      legitimate parameter is rejected. A genome build like `GRCh38` is fine; if any real value
      trips the rule, **narrow the rule**, do not exempt the value.
- [ ] **Step 5:** Commit `fix(core): reject path-shaped parameter values — A3 (stopgap)`

---

### Task 10: A4 — a bundle records which gate it passed

A contract can point channels at the wrong inputs and pass conformance, `nextflow lint` and
`-stub-run`, because nf-core stubs never read their inputs. Only `--gate test` sees it. And
publication has no undo.

> **Decided 2026-08-06 (audit D2, second option).** `mendel publish` does **not** require
> `--gate test` — minutes, Docker and network per publish is too high a floor. Instead the
> bundle records which gate it passed, so a curator can refuse one that never ran the only gate
> that checks wiring. `PipelineIR.unverified` already sets that precedent.

**The type has to move.** `Gate` is a `StrEnum` in `mendel_compiler/gates.py`; `PublishBundle`
is in `comeni-core`, which must not depend on the compiler. Same move `Goal` and `DataProfile`
made, with the same shim — and `egress.py` already declares a `StrEnum` (`ErrorCategory`) in
`comeni-core`, so the precedent for the vocabulary living there is in the file itself. The
**command lines** (`_ARGS`) stay in `mendel-compiler`, because those are how a gate is run and
`comeni-core` has no business knowing.

**Files:**
- Create: `packages/comeni-core/src/comeni_core/gates.py` (the `Gate` vocabulary alone)
- Modify: `packages/mendel-compiler/src/mendel_compiler/gates.py` (re-export shim)
- Modify: `packages/comeni-core/src/comeni_core/egress.py` (`PublishBundle.gate: Gate | None`)
- Modify: `packages/mendel-compiler/src/mendel_compiler/cli.py`
- Test: `tests/test_audit_regressions.py`, `tests/test_egress.py`

- [ ] **Step 1: Write the failing test** — `PublishBundle(...).gate` is the gate that ran;
      publishing without a gate records `None`, and `None` is distinguishable from "passed lint".
- [ ] **Step 2: Run to verify it fails.**
- [ ] **Step 3:** Move the enum; shim the old location; assert `CompilerGate is CoreGate` in a
      test, as `test_goal_location.py` does for `Goal`.
- [ ] **Step 4:** `PublishBundle.gate: Gate | None = None`, and `mendel publish` fills it in
      from what it actually ran.
- [ ] **Step 5:** Run `tests/test_egress.py` — a new field on an egress payload must satisfy
      every shape rule, and a `StrEnum` does.
- [ ] **Step 6:** Commit `feat(core): a bundle records which gate it passed — A4`

---

### Task 11: A1 — the purity guard says what it enforces

`tests/test_purity.py` is a static AST check over import *statements*. It never reasons about
attribute access on an already-imported allowed module, and `exec` is a builtin needing no
import. A module importing only `pathlib` and `typing` reached `os.system` via `pathlib.os`,
`socket` via `typing.sys.modules`, and arbitrary imports via `exec` — and **opened a TCP
connection delivering a serialized `Goal`**, with `tests/test_purity.py` green.

CLAUDE.md's claim that telemetry is "structural rather than a promise" because "the pure
packages cannot import an HTTP client" is false as written.

> **Decided 2026-08-06 (audit D3, recommendation 2 + 3).** Keep the static check for cheap
> feedback, add one runtime assertion that actually holds, and soften the claim to what is
> enforceable. This task also does the cheap half of option 1 — banning module-attribute chains
> and `exec`/`eval`/`compile` — because `pathlib.os.system` is a *demonstrated* route and five
> lines of AST closes it. That is cost-raising, not a guarantee, and the code says so.

**Files:**
- Create: `tests/test_purity_runtime.py`
- Modify: `tests/test_purity.py`
- Modify: `CLAUDE.md` (invariant 1 and the Distribution section's telemetry claim)

- [ ] **Step 1: Reproduce the audit's finding first.** Recreate `comeni_core/telemetry.py`
      importing only `pathlib` and `typing`, run `uv run pytest tests/test_purity.py`, and
      confirm **1 passed** while `phone_home()` delivers a goal to a local listener. Do not skip
      this — a guard fixed without seeing it fail is the pattern this whole audit is about.
- [ ] **Step 2: The runtime assertion.** `tests/test_purity_runtime.py` installs
      `sys.addaudithook`, runs a real build end to end, and asserts no `socket.connect`,
      `subprocess.Popen`, `os.system` or `exec`/`compile` event originates from a frame inside
      the three pure packages. This is the version that resists cleverness, because it checks
      behaviour rather than syntax.
- [ ] **Step 3: Watch it fail** against the telemetry module from Step 1. Expected: named event,
      named frame, named package.
- [ ] **Step 4: Extend the static check** — flag an `ast.Attribute` chain resolving to a module
      object (`pathlib.os`, `typing.sys`) and any call to `exec`, `eval` or `compile`. Comment it
      as raising the cost, not closing the class.
- [ ] **Step 5: Delete the telemetry module.** Confirm `git status` is clean.
- [ ] **Step 6: Rewrite the claim.** In `CLAUDE.md`, invariant 1 and the telemetry paragraph
      become what is true: the pure packages *do not* reach the network, a static check rejects
      the imports and the obvious indirections, and a runtime assertion proves no build opens a
      socket. Not "cannot". The 2026-08-03 audit already made this call for `mendel-compiler`,
      on the grounds that an honest banlist beats a dishonest allowlist; this applies the same
      standard to the two packages that kept the stronger word.
- [ ] **Step 7:** Commit `test(purity): assert behaviour, and claim only what is enforced — A1`

---

### Task 12: Documentation, and the next audit

- [ ] **Step 1:** Mark A1–A13 ✅ in the audit document, each with the commit that closed it.
      **Do not renumber and do not delete** — the document's own header says findings keep their
      numbers permanently, and a closed finding with its reproduction intact is the only record
      of why the code looks the way it does.
- [ ] **Step 2:** `CHANGELOG.md`, `docs/internal/README.md` (Plan 1.8 complete, Plan 2 next),
      and `CLAUDE.md`'s current-state section.
- [ ] **Step 3:** Journal entry. It must carry the finding behind the findings: **nine of
      thirteen fixes moved a check out of a caller and into a type.** A guard in a caller is a
      guard the next caller forgets, and that sentence is worth more to the next session than
      any individual fix.
- [ ] **Step 4:** Open the pull request. `make -j1 check` and `uv run pytest -m slow` both green.
- [ ] **Step 5:** Set up round two — a fresh worktree, the same five adversarial passes, and at
      least two independent reviewers with no session context. **Audit the fixes hardest**: three
      audits running, the sharpest defect has been in the freshest code every time, and A9 was a
      fix that opened the hole it closed.

---

## Verification

```bash
make -j1 check                    # unfiltered; MAKEFLAGS carries -j12 and has hidden a lint failure
uv run pytest -m slow             # the counts matrix — Task 6 changes module selection
uv run pytest tests/test_purity.py tests/test_purity_runtime.py \
              tests/test_egress.py tests/test_construction.py -v
uv run pytest tests/test_audit_regressions.py -v   # one test per finding
uv run python tools/check_registry_drift.py        # now compares the manifest
```

**Done when:** thirteen findings are ✅ with the commit that closed each, `tests/test_audit_regressions.py`
holds a test per finding that was watched failing, and `CLAUDE.md` makes no claim this plan did
not enforce.
