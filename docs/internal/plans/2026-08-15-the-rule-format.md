# Plan 1.15 — the rule format, re-derived

> **For agentic workers:** REQUIRED SUB-SKILL: use `superpowers:executing-plans` and drive this
> yourself, sequentially, task by task. **Do not use `subagent-driven-development`** — that is the
> operator's standing instruction in `CLAUDE.md`, not a preference. Subagents are for review and
> design only. Work in a worktree, not the main checkout. Steps use `- [ ]` for tracking.

**Goal:** replace the tier-3 rule format with a premise layer and a decision layer, so that a rule
can say whether a step exists, cannot silently delete an unrelated decision, and exits at the tier
its evidence earns.

**Architecture:** two layers. The **premise layer** builds the facts `when` reads — measurements,
goal facts, and derived facts — each carrying provenance. The **decision layer** maps premises to
scoped **effects** on a **role** (`presence`, `param`, `implementation`), keyed
`(effect, role[, name])` rather than by type id. A row's tier is computed from its predicates
rather than from which code path ran.

**Tech Stack:** Python 3.12, pydantic v2, pytest, `uv`. No new dependencies.

**Spec:** [`docs/internal/specs/2026-08-15-root-5-the-rule-format.md`](../specs/2026-08-15-root-5-the-rule-format.md).
Read it before Task 0; every task below argues from a numbered section of it.

## Global Constraints

- **Invariant 1.** `comeni-core`, `mendel-resolver` and `mendel-compiler` do not reach the network.
  Nothing in this plan adds an import to those packages beyond stdlib and pydantic.
- **Invariant 4.** A rule miss demotes to tier 4. Nothing here calls a model inside tier 3.
- **Invariant 7.** Vocabularies are closed. `roles:` is closed the same way — an undeclared role
  fails to load.
- **Invariant 11.** Every loader takes **layer roots**, never a `rules/` directory. Stacking goes
  through `comeni_core.layered.stack()` with a `Kind`.
- **`make verify`, not `make check`.** This plan touches `resolve.py`, `router.py`, `rules.py` and
  `pipeline.py` — four of the six files `CLAUDE.md` names as unverifiable by `make check` alone.
  Every task ends on `make verify`.
- **`make drift` is expected RED from Task 0 until Task 11, and that is the only gate that may
  be.** `registry/` here is the `comeni-registry` layer, and the twelve contracts gain `roles:`
  in Task 0. Publishing that early is not an option: an older Mendel loading a layer containing
  a directory it does not know **refuses outright** — `registry layer … contains roles/roles.yml,
  which nothing reads` (A26, verified against `84814f8` on 2026-08-15) — so `roles/` would
  hard-break every existing consumer. It crosses when this plan does.
  **So `make verify` exits non-zero for Tasks 0–10, and the executor must read *why*.** `drift`
  runs last, after `check`, `slow` and `guards` have all passed, so the permitted failure looks
  exactly like this and nothing else:

  ```
  15 file(s) drifted   ← the twelve contracts, from `roles:`, plus measurements/read_length.yml,
                          rules/rnaseq.yml and registry.yml:kinds
    only in Comeni-Labs      measurements/purpose.yml
  ```

  **The count grew from twelve on execution**, and each addition is recorded rather than
  absorbed, because a permitted failure whose shape nobody wrote down is a failure nobody
  checks:
  - `registry.yml:kinds` gained `roles` — Task 0 shipped `roles/` and left the manifest
    naming four kinds.
  - `measurements/purpose.yml` is Task 1's, reported under *only in Comeni-Labs* rather than
    as drift because the other repository has no such file.
  - `measurements/read_length.yml` gained `per_sample: true` in Task 2b.
  - `rules/rnaseq.yml` migrated at **Task 4, not Task 11**. It had to: Task 4 changes
    `DecisionTarget` incompatibly, and a shipped rule file that no longer parses would put
    `make check` red for seven tasks — which the Global Constraints above forbid, and rightly.
    Task 11 keeps the retirement and the documentation.

  Any other file in that list, or a failure before `drift`, is a real failure. Do not paper over
  it with `make check`.
  **Closing condition: Task 11 is not complete until `make drift` is green.** A gate that is red
  for a stated reason with a named closing condition is fine; one that is red for unexamined
  reasons trains everybody to ignore it, which is how `make check` came to be run in place of
  `make verify` for a whole plan (see A14).
  The drift gate was **structurally inert until 2026-08-15**: `REGISTRY ?= ../comeni-registry` was
  relative to `$(CURDIR)`, so from `.worktrees/<plan>` it resolved to `.worktrees/comeni-registry`,
  never existed, and `drift` prints *"skipped"* rather than failing when the path is absent — so
  the check was off for exactly the work `CLAUDE.md` requires to happen in a worktree. It now
  derives the sibling of the **main** checkout from `--git-common-dir`.
- **Every guard is watched failing.** Each task's final step reverts its own guard, watches it
  fail, restores it, and appends a row to `docs/internal/audits/guard-ledger.md`. That is A14's
  closure condition and it is measured per **guard**, not per file (A69).
- **Diagnostic codes:** this plan uses `MD0302`–`MD0311`. `MD0300` and `MD0301` exist; the
  `MD0300`–`MD0399` band is routing and resolution. Every new code gets a `diagnostics.yml` entry
  and `make docs` regenerates the table in `docs/reference/cli.md`.
- **Line length 100.** `uv run ruff check .` clean at every commit.
- **Everything here is written by a person and read by one — tiers, rules, and decisions alike.**
  Operator's requirement, 2026-08-15; spec §4.7 and §6. It binds every task, not the two that
  mention it:
  - **No structured value is a reader's only account of itself.** A mapping is what a policy
    reads. Wherever one reaches `pipeline.yml` or a diagnostic, a sentence goes beside it. The
    live counter-example is the shipped `reason:` carrying `{''read_length'': ''>= 70''}` — a
    dict repr in YAML, naming the predicate and not the value.
  - **A refusal names the offending thing *and* what would have been right.** Every code from
    `MD0302` to `MD0311`. Already this repository's practice; here it is a requirement.
  - **A rule reads as a claim about the world.** `presence: trimming` and
    `implementation: alignment` are English; `producer_of: fastq.reads` with `then: null` — the
    old way to spell *"do not trim"* — is not.
  - **A number that means something carries its meaning.** `tier: 3` gains `review: advisory`
    (Task 7 Step 5), so the artifact stops requiring `CLAUDE.md` open beside it.

## Scope note

This is one plan rather than two because neither layer is useful alone: a premise layer nothing
reads is dead code, and a decision layer with no premises has nothing to decide on. Tasks 0–7
produce a working format; Tasks 8–11 migrate the registry onto it and retire the old one. **Do not
stop after Task 7** — the repository would hold two rule formats, which is worse than either.

## File structure

| File | Responsibility |
|---|---|
| `packages/comeni-core/src/comeni_core/roles.py` | **new** — `RoleName`, the closed role vocabulary loader |
| `packages/comeni-core/src/comeni_core/contract.py` | **modify** — `ModuleContract.roles`, `Param.domain`, `InputPort.state_required_because` |
| `packages/mendel-resolver/src/mendel_resolver/premises.py` | **new** — `Premise`, `PremiseOrigin`, `build_premises` |
| `packages/mendel-resolver/src/mendel_resolver/predicates.py` | **new** — one predicate evaluator, `tier_of_row` |
| `packages/mendel-resolver/src/mendel_resolver/rules.py` | **rewrite** — `Derivation`, `DecisionTarget`, `Decision`, `Effect`, `RuleTable` |
| `packages/mendel-resolver/src/mendel_resolver/resolve.py` | **modify** — consume effects instead of `value_for`/`producer_for` |
| `packages/mendel-resolver/src/mendel_resolver/router.py` | **modify** — honour a `presence` effect; conventional state requirements |
| `packages/comeni-core/src/comeni_core/pipeline.py` | **modify** — `SCHEMA_VERSION = 3`, `Why.premise` |
| `registry/roles/roles.yml` | **new** — the closed role vocabulary. A *directory*, because `stack()` reads `layer.path / kind.which.value` |
| `registry/rules/rnaseq.yml` | **rewrite** — into the new format |

**Where rules are stored — spec §2.1.** Both layers live in the existing `rules/` directory; a
file may carry `derives:`, `decisions:` or both, parsed by one `Kind[str, Derivation | Decision]`
(the union shape `Kind[str, Measurement | MeasurementDelta]` already uses). Keys are namespaced —
`derive:<fact>`, `presence:<role>`, `implementation:<role>`, `param:<role>:<name>` — because
`stack()` has one key space per kind, and `Policy.REPLACE` applies **per key, not per file**, so
an overlay replacing a derivation leaves the decision beside it untouched. No new `DeclaredKind`
beyond Task 0's `ROLES`.

---

## Task 0: a contract declares the roles it fills

**Spec:** §4.1. A rule targets a role, so roles must exist before anything can target one.

**Files:**
- Create: `packages/comeni-core/src/comeni_core/roles.py`
- Create: `registry/roles.yml`
- Modify: `packages/comeni-core/src/comeni_core/contract.py` (add `roles` to `ModuleContract`)
- Modify: all twelve files under `registry/contracts/`
- Test: `packages/comeni-core/tests/test_roles.py`

**Interfaces:**
- Produces: `RoleName = Annotated[str, Mark.ROLE_NAME]`;
  `RoleVocabulary.load(layers) -> RoleVocabulary` with `.names: frozenset[str]`;
  `ModuleContract.roles: list[RoleName]`.
- Consumes: nothing.

- [ ] **Step 1: Write the failing test**

```python
# packages/comeni-core/tests/test_roles.py
import pytest
from comeni_core.contract import ModuleContract
from comeni_core.roles import RoleVocabulary, UnknownRoleError


def test_a_contract_declaring_an_undeclared_role_fails_to_load(tmp_path, a_contract):
    """Invariant 7: role names are closed vocabulary, like states."""
    vocab = RoleVocabulary(names=frozenset({"alignment"}))
    with pytest.raises(UnknownRoleError) as exc:
        vocab.check(ModuleContract.model_validate({**a_contract, "roles": ["alignmnet"]}))
    assert "alignmnet" in str(exc.value)
    assert "alignment" in str(exc.value), "the message must name what does exist"


def test_a_contract_may_fill_more_than_one_role(a_contract):
    contract = ModuleContract.model_validate({**a_contract, "roles": ["qc_per_sample"]})
    assert contract.roles == ["qc_per_sample"]


def test_roles_default_to_empty_so_every_existing_contract_still_loads(a_contract):
    assert ModuleContract.model_validate(a_contract).roles == []
```

- [ ] **Step 2: Run it and watch it fail**

Run: `uv run pytest packages/comeni-core/tests/test_roles.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'comeni_core.roles'`

- [ ] **Step 3: Write `roles.py`**

```python
"""The closed vocabulary of jobs a contract can fill.

A rule targets a *role*, never a type id and never a contract. Audit A119 and A123 are one
defect: a rule whose target named `alignment.bam` collided with every other rule about that
type, and REPLACE stacking resolved the collision by deleting one of them.
"""

from collections.abc import Sequence
from pathlib import Path

from comeni_core import yaml_strict
from comeni_core.layered import DeclaredKind, Kind, Policy, Stacked, layers_of, stack
from pydantic import BaseModel, ConfigDict


class UnknownRoleError(ValueError):
    """A contract named a role no layer declares."""


class RoleVocabulary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    names: frozenset[str]

    @staticmethod
    def kind() -> Kind[str, str]:
        def parse(path: Path) -> list[str]:
            return list((yaml_strict.load(path) or {}).get("roles", []))

        return Kind(DeclaredKind.ROLES, parse=parse, key=lambda name: name,
                    policy=Policy.REPLACE)

    @classmethod
    def load(cls, layers: Path | Sequence[Path]) -> "RoleVocabulary":
        stacked: Stacked[str, str] = stack(layers_of(layers), cls.kind())
        return cls(names=frozenset(stacked.entries))

    def check(self, contract) -> None:
        for role in contract.roles:
            if role not in self.names:
                raise UnknownRoleError(
                    f"MD0302: {contract.id} declares role {role!r}, which no layer declares.\n"
                    f"  Roles that do exist: {', '.join(sorted(self.names))}"
                )
```

Add `ROLES = "roles"` to `DeclaredKind` in `comeni_core/layered.py`, and to `ModuleContract`:

```python
    roles: list[RoleName] = Field(default_factory=list)
    """The jobs this contract can do. A rule targets one of these, never a type id.

    Empty is legal and means no rule can target this contract — which is correct for a
    contract nobody has classified yet, and is what keeps this field addable without
    rewriting every layer on the same day.
    """
```

Add `ROLE_NAME` to `Mark` in `comeni_core/marks.py` with the same `_single_line` validator the
other declared-id aliases use, and `RoleName = Annotated[str, Mark.ROLE_NAME, AfterValidator(_single_line)]`.

- [ ] **Step 4: Write `registry/roles.yml`**

```yaml
# The jobs a contract can fill. Closed, like every other vocabulary: a contract naming a
# role that is not here fails to load (MD0302).
roles:
  - trimming
  - alignment
  - index_building
  - bam_sorting
  - bam_indexing
  - quantification
  - qc_per_sample
  - qc_aggregation
  - profiling
```

- [ ] **Step 5: Add `roles:` to all twelve contracts**

`trimgalore` → `[trimming]`; `star/align`, `hisat2/align` → `[alignment]`;
`star/genomegenerate`, `hisat2/build` → `[index_building]`; `samtools/sort` → `[bam_sorting]`;
`samtools/index` → `[bam_indexing]`; `subread/featurecounts` → `[quantification]`;
`fastqc` → `[qc_per_sample]`; `multiqc` → `[qc_aggregation]`;
`comeni/profile/fastqc`, `comeni/profile/collect` → `[profiling]`.

- [ ] **Step 6: Run the tests**

Run: `uv run pytest packages/comeni-core/tests/test_roles.py -v && make verify`
Expected: PASS, and `make verify` green — the counts matrix is unchanged because roles decide
nothing yet.

- [ ] **Step 7: Watch the guard fail, then commit**

Delete `roles:` from `registry/contracts/nf-core/star-align.yml`, run
`uv run pytest packages/comeni-core/tests/test_roles.py -v`, and confirm nothing fails — roles are
optional, so this guard does **not** yet protect the registry. Record that "nothing failed" row in
the ledger beside the test that will close it (Task 4's `test_every_contract_declares_a_role`).
Restore, then:

```bash
git add packages/comeni-core registry/
git commit -m "feat(core): a contract declares the roles it fills (A119, A123)"
```

---

## Task 1: the premise layer

**Spec:** §3. What `when` reads, with provenance on every fact.

**Files:**
- Create: `packages/mendel-resolver/src/mendel_resolver/premises.py`
- Test: `packages/mendel-resolver/tests/test_premises.py`

**Interfaces:**
- Consumes: `MeasurementRegistry`, `DataProfile`, `Goal`.
- Produces: `PremiseOrigin` (StrEnum: `MEASURED`, `ASSERTED`, `GOAL`, `DERIVED`, `UNMEASURED`);
  `Premise(id, value, origin, because, cite, derived_from)`;
  `build_premises(*, goal, derivations, measurements) -> dict[str, Premise]`.

> **Corrected 2026-08-15, against the code rather than against the draft.** The first version of
> this task was wrong in four ways, and the fourth changed the design for the better.
>
> 1. **`DataProfile` has `measurements: list[Measured]`** — not `values` and `sources`. `Measured`
>    is `(measurement, value, source, by)`, so **provenance is per entry**, which is what lets one
>    profile mix a measured `read_length` with an asserted `strandedness`. Read `DataProfile.get`.
> 2. **`required_states` lives on `Goal.constraints`**, not on `Goal`. `Goal` has exactly `have`,
>    `want`, `constraints`, `profile`.
> 3. **`build_premises` takes the `Goal`, not a profile** — the profile is `goal.profile`, and
>    passing both invites them to disagree.
> 4. **`purpose` is a declared measurement, not a new `Goal` field.** See spec §4.6. Adding a
>    field to `Goal` would widen a door-1 *and* door-4 payload and pull in the egress guard and
>    invariant 14's literal list; a declared measurement asserted with `ValueSource.GOAL` needs
>    none of that and gets validation from `MeasurementRegistry.profile()`. `n_samples` is the
>    precedent — a measurement describing the study, with no `describes`.
>
> **`tests/test_construction.py` scans `packages/*/src` only**, so a test may construct a
> `DataProfile` directly. Prefer `measurements.profile({...})` anyway: it is the validated path
> and it is what every other test in this repository does.

- [ ] **Step 1: Write the failing test**

```python
# packages/mendel-resolver/tests/test_premises.py
import pathlib

from comeni_core.tiers import ValueSource
from mendel_resolver import layers
from mendel_resolver.goal import Goal, GoalInput
from mendel_resolver.premises import PremiseOrigin, build_premises

ROOT = pathlib.Path(__file__).parents[3]
LOADED = layers.load(ROOT / "registry")


def _goal(**measured) -> Goal:
    """A goal whose profile carries `measured`, through the one validated constructor."""
    return Goal(
        have=[GoalInput(type_id="fastq.reads")],
        want=["counts.matrix"],
        profile=LOADED.measurements.profile(measured, source=ValueSource.MEASURED),
    )


def test_a_measured_fact_says_it_was_measured():
    premises = build_premises(
        goal=_goal(read_length=150), derivations=[], measurements=LOADED.measurements
    )
    assert premises["read_length"].value == 150
    assert premises["read_length"].origin is PremiseOrigin.MEASURED


def test_an_asserted_fact_is_not_a_measured_one():
    """The distinction `sealed` exists to act on (issue #2). `Measured.source` is per entry,
    so one profile can carry both and the premise layer must not flatten them."""
    goal = Goal(
        have=[GoalInput(type_id="fastq.reads")],
        want=["counts.matrix"],
        profile=LOADED.measurements.profile(
            {"strandedness": "reverse"}, source=ValueSource.GOAL
        ),
    )
    premises = build_premises(goal=goal, derivations=[], measurements=LOADED.measurements)
    assert premises["strandedness"].origin is PremiseOrigin.ASSERTED


def test_a_goal_declared_purpose_is_a_premise():
    """Spec §4.6: `purpose` is a declared measurement, so it needs no field on `Goal`."""
    premises = build_premises(
        goal=_goal(purpose="variant_calling"), derivations=[], measurements=LOADED.measurements
    )
    assert premises["purpose"].value == "variant_calling"


def test_required_states_reach_the_premise_set():
    """A120's cheaper half — the router already consults these, and `when` could not.
    R11 (Salmon for transcript-level, featureCounts for gene-level) dies on exactly this."""
    goal = Goal(
        have=[GoalInput(type_id="fastq.reads")],
        want=["counts.matrix"],
        constraints={"required_states": {"counts.matrix": ["gene_level"]}},
    )
    premises = build_premises(goal=goal, derivations=[], measurements=LOADED.measurements)
    assert "gene_level" in premises["required_states"].value
    assert premises["required_states"].origin is PremiseOrigin.GOAL


def test_a_human_override_is_evidence_of_the_same_quality_as_a_goal_assertion():
    """Different authors, identical evidence: in neither case did anything look at the data.
    Collapsing them here rather than at each point of use keeps `sealed` a single check."""
    premises = build_premises(
        goal=_goal(ValueSource.HUMAN, strandedness="forward"),
        derivations=[], measurements=LOADED.measurements,
    )
    assert premises["strandedness"].origin is PremiseOrigin.ASSERTED


def test_required_states_is_present_and_empty_rather_than_absent():
    """So `when: {required_states: absent}` means "the goal asked for no states" and not
    "this build predates the field". A premise that vanishes when empty cannot be tested."""
    premises = build_premises(
        goal=_goal(read_length=150), derivations=[], measurements=LOADED.measurements
    )
    assert premises["required_states"].value == []


def test_nothing_may_declare_a_measurement_named_required_states():
    """It is the goal's own shape. A measurement of that name would silently shadow it, and
    which won would depend on what the loader reached first."""
    class _Shadowing:
        def ids(self): return ["required_states"]

    with pytest.raises(PremiseError, match="MD0303"):
        build_premises(
            goal=Goal(have=[GoalInput(type_id="fastq.reads")], want=["counts.matrix"]),
            derivations=[], measurements=_Shadowing(),
        )
```

`_goal` is a helper building the profile through `LOADED.measurements.profile(measured,
source=source)` — the validated constructor — rather than `DataProfile(...)`. The construction
guard scans `packages/*/src` and not `tests/`, so a direct build would pass; it would also skip
the validation that makes an undeclared measurement impossible, which is why that constructor
exists.

**`purpose` must be declared before this test passes.** Add
`registry/measurements/purpose.yml`:

```yaml
kind: enum
values: [expression, variant_calling, junction_discovery, transcript_assembly]
extensible: true
description: "What the analysis is for — the question the pipeline answers"
cite: "nf-core/rnaseq usage; Conesa et al. 2016, doi:10.1186/s13059-016-0881-8"
```

No `describes` and no `meta_key`: `purpose` is a property of the study rather than of a read, and
nothing carries it into a module's `meta` map. `extensible: true` because the list of things
sequencing is for cannot be enumerated, which is the same call `organism` gets.

- [ ] **Step 2: Run it and watch it fail**

Run: `uv run pytest packages/mendel-resolver/tests/test_premises.py -v`
Expected: FAIL — `No module named 'mendel_resolver.premises'`

- [ ] **Step 3: Write `premises.py`**

```python
"""The facts a rule may read, and where each one came from.

Tier 3 is defined as producing `value + rule + measurement` and produced only the first two
(A108). The premise is the missing third, and it has to carry its own provenance or `sealed`
cannot refuse a decision resting on an assertion (issue #2).
"""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class PremiseError(ValueError):
    """The premise set could not be built."""


class PremiseOrigin(StrEnum):
    MEASURED = "measured"
    ASSERTED = "asserted"
    GOAL = "goal"
    DERIVED = "derived"
    UNMEASURED = "unmeasured"
    """Read by a row testing `absent`. A gap is evidence; it is evidence of a gap."""


class Premise(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    value: Any
    origin: PremiseOrigin
    because: str = ""
    cite: str = ""
    derived_from: list[str] = Field(default_factory=list)


_BY_SOURCE = {
    ValueSource.MEASURED: PremiseOrigin.MEASURED,
    ValueSource.GOAL: PremiseOrigin.ASSERTED,
    ValueSource.HUMAN: PremiseOrigin.ASSERTED,
}
"""`ValueSource` answers *who settled this*; `PremiseOrigin` answers *how good is it as a
premise*, and the two are not the same question. A goal assertion and a human override are
different authors and identical evidence: nobody looked at the data. Collapsing them here
rather than at the point of use is what keeps `sealed` a single check."""

_RESERVED = "required_states"


def build_premises(*, goal, derivations, measurements) -> dict[str, Premise]:
    """Measured, then asserted, then goal, then derived. One pass, no fixpoint.

    Ordered rather than iterated to a fixpoint because a fixpoint makes the premise set a
    function of evaluation order, and two rules could then disagree about the same fact
    depending on which loaded first. One pass is what keeps `same goal in -> same pipeline
    out` a property of the data rather than of the loader.

    Takes the `Goal` rather than a goal and a profile: the profile is `goal.profile`, and a
    signature that accepts both invites a caller to pass two that disagree.
    """
    premises: dict[str, Premise] = {}
    for entry in goal.profile.measurements:
        premises[entry.measurement] = Premise(
            id=entry.measurement,
            value=entry.value,
            origin=_BY_SOURCE.get(entry.source, PremiseOrigin.ASSERTED),
        )
    # `required_states` is the goal's own shape rather than a measurement, so it cannot
    # collide with one: `MeasurementRegistry.profile()` would have refused an undeclared key,
    # and nothing may declare a measurement by this name (checked below).
    if _RESERVED in measurements.ids():
        raise PremiseError(
            f"MD0303: a measurement is declared named {_RESERVED!r}, which is the goal's "
            f"own shape and cannot also be measured."
        )
    premises[_RESERVED] = Premise(
        id=_RESERVED,
        value=sorted(
            state
            for required in goal.constraints.required_states
            for state in required.states
        ),
        origin=PremiseOrigin.GOAL,
    )
    return premises
```

`purpose` needs no special case: it is a declared measurement, so it arrives through
`goal.profile` with whatever source it was asserted under. That is the whole benefit of spec
§4.6, and it is why this function is shorter than the draft that had a `_GOAL_FACTS` tuple.

Derivations are the argument and are unused until Task 2; that is deliberate, so Task 2 adds
behaviour rather than a parameter.

`MeasurementRegistry` exposes `get`, `ids`, `check`, `profile`, `to_measure`, `meta_for` and
`meta_sources_for` — **and no `all()`**, which an earlier draft of this task called. Checked
2026-08-15.

- [ ] **Step 4: Run the tests**

Run: `uv run pytest packages/mendel-resolver/tests/test_premises.py -v`
Expected: PASS (7 passed — the corrected test list above, not the four the draft had)

Then **`make check`**, not only that file. Four things outside `mendel-resolver` move here and
three of them are found by nothing else: see the corrections below.

- [ ] **Step 5: Watch the guard fail, then commit**

Change `origin=_BY_SOURCE[entry.source]` to always `PremiseOrigin.MEASURED`. Confirm
`test_a_measured_fact_says_it_was_measured` still passes.

**Three tests fail, and this step predicted none.** Record the row, restore, then revert the
`_RESERVED in measurements.ids()` refusal and the `required_states` premise in turn — each has
its own test and each was watched. Then:

```bash
git add packages/mendel-resolver registry tools tests docs
git commit -m "feat(resolver): a premise carries where it came from (A108, A120)"
```

> **Corrected 2026-08-15, on execution. Five things, and only the first is in this package.**
>
> 1. **Step 5's prediction was wrong.** It said to confirm *"no test fails — the asserted case
>    has no guard yet, which is Task 8's"*, which was true of the four-test draft. The
>    corrected test list pins the asserted side three times over, so collapsing the mapping
>    fails three tests. The guard is live, and the revert is what said so.
> 2. **`registry/measurements/purpose.yml` makes `make types` fail** — `tools/generate_types.py`
>    generates `profile.pyi` from the declared measurements, and `make check` runs it with
>    `--check`. Regenerate it in the same commit.
> 3. **And it makes the generator emit a line over 100 characters.** `purpose`'s four values
>    put the return annotation at 101 on a line of its own, past both of the generator's
>    line-wrapping forms, so the generated stub failed `ruff check` — which the generator's own
>    comment exists to prevent. A third form was added, wrapping inside `Literal[`. Shortening
>    the declared values instead would have let a line limit edit the vocabulary.
> 4. **`enum` is not on `mendel-resolver`'s purity allowlist.** `PremiseOrigin` is the first
>    vocabulary this package *declares* rather than reads from `comeni-core`. Added with a
>    written argument, in the shape the `re` entry established on 2026-08-14.
> 5. **`MD0303` needs a `diagnostics.yml` entry, and so did Task 0's `MD0302`**, which shipped
>    without one — the Global Constraints require it and nothing enforces it, because a code
>    inside an f-string is invisible to `Diagnostic`'s validation. Both are declared now.
>    Task 0 also left `registry/registry.yml` naming four kinds beside a `roles/` directory.

---

## Task 2: derivations — a fallback, and an aggregate

**Spec:** §3.1, §3.2. R15 and R19, which the shipped format loads dead or cannot write.

**Files:**
- Modify: `packages/mendel-resolver/src/mendel_resolver/premises.py`
- Modify: `packages/mendel-resolver/src/mendel_resolver/rules.py` (add `Derivation`)
- Test: `packages/mendel-resolver/tests/test_premises.py`

**Interfaces:**
- Produces: `Derivation(fact, kind, rows, aggregate, because, cite)`;
  `Aggregate(measurement, over, using)`.

- [ ] **Step 1: Write the failing test**

```python
def test_a_derivation_fills_a_gap_and_never_overwrites(measurements, a_goal):
    """R15/A122: 'infer strandedness when it was not measured' loads dead today."""
    derivation = Derivation.model_validate({
        "fact": "strandedness", "kind": "enum",
        "rows": [{"when": {"strandedness": "absent"}, "then": "reverse",
                  "because": "dUTP protocols dominate current library prep",
                  "cite": "Wang et al. 2012, doi:10.1093/bib/bbs046"}],
    })
    absent = build_premises(profile=DataProfile(values={}, sources={}), goal=a_goal,
                            derivations=[derivation], measurements=measurements)
    assert absent["strandedness"].value == "reverse"
    assert absent["strandedness"].origin is PremiseOrigin.DERIVED
    assert absent["strandedness"].derived_from == ["strandedness"]

    measured = build_premises(
        profile=DataProfile(values={"strandedness": "forward"},
                            sources={"strandedness": "measured"}),
        goal=a_goal, derivations=[derivation], measurements=measurements)
    assert measured["strandedness"].value == "forward", "a measurement always wins"
    assert measured["strandedness"].origin is PremiseOrigin.MEASURED


def test_an_aggregate_reduces_the_cohort(measurements, a_goal):
    """R19, and §12's cohort-versus-sample question."""
    derivation = Derivation.model_validate({
        "fact": "cohort_max_read_length", "kind": "integer",
        "aggregate": {"measurement": "read_length", "over": "cohort", "using": "max"},
        "because": "the index is built once per run", "cite": "STAR manual 2.2.2",
    })
    premises = build_premises(
        profile=DataProfile(values={"read_length": [150, 100, 150]},
                            sources={"read_length": "measured"}),
        goal=a_goal, derivations=[derivation], measurements=measurements)
    assert premises["cohort_max_read_length"].value == 150
    assert premises["cohort_max_read_length"].derived_from == ["read_length"]
```

- [ ] **Step 2: Run it and watch it fail**

Run: `uv run pytest packages/mendel-resolver/tests/test_premises.py -k derivation -v`
Expected: FAIL — `Derivation` is not defined

- [ ] **Step 3: Implement `Derivation` and wire it into `build_premises`**

```python
class Aggregate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    measurement: str
    over: Literal["cohort"]
    using: Literal["max", "min", "mean"]


class Derivation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fact: str
    kind: MeasurementKind
    rows: list["DecisionRow"] = Field(default_factory=list)
    aggregate: Aggregate | None = None
    because: str = ""
    cite: str | None = None

    @model_validator(mode="after")
    def _one_source(self) -> "Derivation":
        if bool(self.rows) == bool(self.aggregate):
            raise ValueError(
                f"MD0304: derivation {self.fact!r} needs exactly one of `rows`, `aggregate`"
            )
        return self
```

In `build_premises`, after the goal loop:

```python
    _AGGREGATORS = {"max": max, "min": min, "mean": lambda xs: sum(xs) / len(xs)}
    for derivation in derivations:
        fact = derivation.fact
        if derivation.aggregate is not None:
            values = premises.get(derivation.aggregate.measurement)
            if values is None or not isinstance(values.value, list):
                continue
            premises[fact] = Premise(
                id=fact, value=_AGGREGATORS[derivation.aggregate.using](values.value),
                origin=PremiseOrigin.DERIVED, because=derivation.because,
                cite=derivation.cite or "", derived_from=[derivation.aggregate.measurement],
            )
            continue
        if fact in measurements.ids() and fact in premises:
            continue   # a derivation over a declared measurement may only fill a gap
        for row in derivation.rows:
            if matches(row.when, premises):
                premises[fact] = Premise(
                    id=fact, value=row.then, origin=PremiseOrigin.DERIVED,
                    because=row.because or derivation.because,
                    cite=row.cite or derivation.cite or "", derived_from=sorted(row.when),
                )
                break
```

`matches` arrives in Task 3; until then inline the equality/`absent` cases and replace the call in
Task 3's step 3.

- [ ] **Step 4: Run the tests**

Run: `uv run pytest packages/mendel-resolver/tests/test_premises.py -v`
Expected: PASS (14 passed — Task 1's seven, plus this task's)

- [ ] **Step 5: Watch the guard fail, then commit**

Delete the `if derivation.fact in premises: continue` line.

**Nothing fails, and this step predicted a failure.** Strengthen the guard first — see the
correction below — then revert again and watch two tests fail with `'reverse' == 'forward'`.
Restore, record both rows, then:

```bash
git add packages/mendel-resolver packages/comeni-core docs
git commit -m "feat(resolver): a derived fact fills a gap and never overwrites (A122, R15)"
```

> **Corrected 2026-08-15, on execution. Three things, and the second is the useful one.**
>
> 1. **The test code was written against the pre-Task-1 signature** — `build_premises(profile=…,
>    goal=…)` with `DataProfile(values=…, sources=…)`. Neither exists; the corrected signature is
>    `build_premises(*, goal, derivations, measurements)` and provenance is per entry on
>    `goal.profile.measurements`. Task 1's own correction block already says this; it had not
>    been applied here.
> 2. **Step 5's guard is inert as specified.** R15's row is `when: {strandedness: absent}`, so
>    with `strandedness` measured the row fails its own predicate and the never-overwrite rule is
>    never consulted. Deleting the rule leaves every test green. The replacement conditions on a
>    *different* fact from the one it derives, plus a second test for derivation-against-
>    derivation. **Following this plan carefully would not have caught it — only running the
>    revert did.**
> 3. **The aggregate half is not built, on purpose.** `DataProfile` cannot hold
>    `read_length: [150, 100, 150]`: `ParamValue` is `int | float | bool | str | None`, and
>    `MeasurementRegistry.check` refuses a list for an integer measurement. So R19 needs a
>    decision about how a cohort-valued measurement is represented, which neither this plan nor
>    spec §3.2 makes. Shipping `Aggregate` as a model that loads and never evaluates would be
>    A122 exactly — the defect this task exists to close — so it is left out rather than left
>    dead. `list` is already a permitted egress container, so the boundary is not the obstacle.
> 4. **The never-overwrite rule is narrower than specified**, dropping the plan's
>    `fact in measurements.ids() and` clause so it applies to derived facts too. Two derivations
>    of the same fact now resolve first-wins rather than by load order — invariant 10, and the
>    convention `ReplayResolver` already uses.

---

## Task 3: one predicate evaluator, and a row's tier

**Spec:** §4.4, §4.5. A121, and the earned-tier rule.

**Files:**
- Create: `packages/mendel-resolver/src/mendel_resolver/predicates.py`
- Test: `packages/mendel-resolver/tests/test_predicates.py`

**Interfaces:**
- Produces: `matches(when: dict, premises: dict[str, Premise]) -> bool`;
  `tier_of_row(when: dict) -> Tier`.

- [ ] **Step 1: Write the failing test**

```python
from comeni_core.tiers import Tier
from mendel_resolver.predicates import matches, tier_of_row
from mendel_resolver.premises import Premise, PremiseOrigin

P = lambda **kw: {k: Premise(id=k, value=v, origin=PremiseOrigin.MEASURED)
                 for k, v in kw.items()}


def test_negation_over_an_enum_is_not_a_malformed_number():
    """A121: `_comparison` ran every literal through float(), so `!= unstranded` was
    reported as 'unstranded is not a number. Write it as "!= 70"'."""
    assert matches({"strandedness": {"not": "unstranded"}}, P(strandedness="reverse"))
    assert not matches({"strandedness": {"not": "unstranded"}}, P(strandedness="unstranded"))


def test_absence_is_a_predicate():
    assert matches({"strandedness": "absent"}, {})
    assert not matches({"strandedness": "absent"}, P(strandedness="reverse"))


def test_a_row_testing_no_premise_positively_is_tier_2():
    """§4.4. A catch-all is a documented default; it did not do tier-3 work."""
    assert tier_of_row({}) is Tier.CONVENTION
    assert tier_of_row({"strandedness": "absent"}) is Tier.CONVENTION
    assert tier_of_row({"read_length": ">= 70"}) is Tier.DATA_PROFILED
    assert tier_of_row({"read_length": ">= 70", "paired": "absent"}) is Tier.DATA_PROFILED
```

- [ ] **Step 2: Run it and watch it fail**

Run: `uv run pytest packages/mendel-resolver/tests/test_predicates.py -v`
Expected: FAIL — `No module named 'mendel_resolver.predicates'`

- [ ] **Step 3: Write `predicates.py`**

```python
"""One evaluator, shared by load-time validation and runtime matching.

Two copies of this predicate is how a rule passes validation and then fails to fire, which is
why `_comparison` was one function in the old format and why this is one here.
"""

import operator

from comeni_core.tiers import Tier

_OPS = {">=": operator.ge, ">": operator.gt, "<=": operator.le, "<": operator.lt,
        "==": operator.eq, "!=": operator.ne}


def tier_of_row(when: dict) -> Tier:
    """The tier this row exits at, determined by the rule TEXT rather than by the data.

    A row earns tier 3 only by testing a premise *positively*. `when: {}` is a catch-all and
    `when: {x: absent}` is a convention about what to assume in a gap — both produce
    `value + citation`, which is tier 2's shape, not tier 3's.

    Static on purpose: an author sees each branch's tier while writing it, and a reviewer can
    predict a build's review load from the rules rather than from a run.
    """
    positive = [key for key, expected in when.items() if expected != "absent"]
    return Tier.DATA_PROFILED if positive else Tier.CONVENTION


def _one(expected, premise) -> bool:
    if expected == "absent":
        return premise is None
    if expected == "present":
        return premise is not None
    if premise is None:
        return False
    actual = premise.value
    if isinstance(expected, dict):
        if "not" in expected:
            return actual != expected["not"]
        if "in" in expected:
            return actual in expected["in"]
        raise ValueError(f"MD0305: unknown predicate {expected!r}")
    if isinstance(expected, str):
        symbol, _, literal = expected.partition(" ")
        if symbol in _OPS:
            try:
                return _OPS[symbol](actual, float(literal))
            except (TypeError, ValueError):
                return _OPS[symbol](actual, literal)
    return actual == expected


def matches(when: dict, premises: dict) -> bool:
    return all(_one(expected, premises.get(key)) for key, expected in when.items())
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest packages/mendel-resolver/tests/test_predicates.py -v`
Expected: PASS (9 passed)

- [ ] **Step 5: Replace Task 2's inlined matcher with `matches`, and re-run**

Delete `premises._matches` rather than leaving it beside this one. Run:
`uv run pytest packages/mendel-resolver/tests -v`. Expected: PASS.

- [ ] **Step 6: Watch the guard fail, then commit**

Change `tier_of_row`'s `expected != "absent"` to `True`; two tests fail. Then revert the
`MD0305` raise and the cohort refusal in turn. Restore, record the rows, then:

```bash
git add packages/mendel-resolver packages/comeni-core docs
git commit -m "feat(resolver): one predicate evaluator, and a row's tier is its text (A121)"
```

> **Corrected 2026-08-15, on execution. Three additions, no contradictions.**
>
> 1. **`present` is a predicate and earns tier 3**, where `absent` does not. The plan's
>    `_one` implements both and `tier_of_row` counts only `absent` as non-positive, which is
>    right — but the plan never says why they differ, and they read as a pair. `present` is a
>    test on the data; `absent` is a test on its absence. Two tests now pin that.
> 2. **`MD0312` — a scalar comparison against a per-sample measurement.** New since the plan
>    was written, because `read_length` is now declared `per_sample`. Without it the resolver
>    raises `TypeError` naming neither the rule nor the fact. Outside the plan's declared
>    `MD0302`–`MD0311` band, which is fully allocated; `MD0300`–`MD0399` is the reserved band.
> 3. **`predicates.py` imports `Premise` under `TYPE_CHECKING` only** — `premises` calls
>    `matches`, so a runtime import back is a cycle. The plan's sketch left both parameters
>    unannotated, which sidesteps the question rather than answering it.
>
> The plan's `_one` also loses the fact's name, so `MD0305` could not say *which* fact carried
> the bad predicate. `_one` takes the key here for that reason alone.

---

## Task 4: the decision layer — effects on a role

**Spec:** §4.1, §4.3, §5. A119's collision and A123, closed at load.

**Files:**
- Rewrite: `packages/mendel-resolver/src/mendel_resolver/rules.py`
- Test: `packages/mendel-resolver/tests/test_rules.py`

**Interfaces:**
- Produces: `Effect` (StrEnum: `PRESENCE`, `PARAM`, `IMPLEMENTATION`);
  `DecisionTarget(effect, of, name, when_implementation)`;
  `Decision(decides, rows, because, cite)` where `decides` is `DecisionTarget | list[DecisionTarget]`;
  `Fired(effect, role, name, value, tier, because, cite, axis_because, premise)`;
  `RuleTable.effects_for(premises) -> list[Fired]`.

- [ ] **Step 1: Write the failing test**

```python
def test_two_decisions_cannot_share_a_key(load_rules, tmp_path):
    """A119, the collision I reproduced: a lab's dedup rule keyed producer_of:alignment.bam
    silently deleted the shipped aligner rule and swapped HISAT2 for STAR on 50bp reads."""
    with pytest.raises(RuleValidationError, match="both decide 'presence:trimming'"):
        load_rules("""
        decisions:
          - decides: {effect: presence, of: trimming}
            rows: [{when: {}, then: absent, cite: "a"}]
          - decides: {effect: presence, of: trimming}
            rows: [{when: {}, then: present, cite: "b"}]
        """)


def test_a_param_must_be_declared_by_every_contract_that_could_fill_the_role(load_rules):
    """A123 and issue #10's deadness: star_ignore_sjdbgtf is STAR's alone, so the value is
    dead whenever HISAT2 wins."""
    with pytest.raises(RuleValidationError, match="not declared by nf-core/hisat2/align"):
        load_rules("""
        decisions:
          - decides: {effect: param, of: alignment, name: star_ignore_sjdbgtf}
            rows: [{when: {}, then: false, cite: "STAR manual 2.2.3"}]
        """)


def test_narrowing_to_the_implementations_that_declare_it_is_accepted(load_rules):
    table = load_rules("""
    decisions:
      - decides: {effect: param, of: alignment, name: star_ignore_sjdbgtf,
                  when_implementation: [nf-core/star/align@1.11.0]}
        rows: [{when: {}, then: false, cite: "STAR manual 2.2.3"}]
    """)
    assert len(table.decisions) == 1


def test_a_rule_naming_a_contract_the_stack_does_not_hold_is_refused(load_rules):
    """R20 -- the shape a lab writing overlay rules meets first."""
    with pytest.raises(RuleValidationError, match="does not fill role 'alignment'"):
        load_rules("""
        decisions:
          - decides: {effect: implementation, of: alignment}
            rows: [{when: {}, then: nf-core/salmon@1.10.0, cite: "Patro 2017"}]
        """)
```

- [ ] **Step 2: Run it and watch it fail**

Run: `uv run pytest packages/mendel-resolver/tests/test_rules.py -k "share_a_key or declared_by" -v`
Expected: FAIL — `Effect` is not defined

- [ ] **Step 3: Rewrite `rules.py`'s target and validation**

```python
class Effect(StrEnum):
    PRESENCE = "presence"
    PARAM = "param"
    IMPLEMENTATION = "implementation"


class DecisionTarget(BaseModel):
    model_config = ConfigDict(extra="forbid")

    effect: Effect
    of: RoleName
    name: NfIdentifier | None = None
    when_implementation: list[ContractId] = Field(default_factory=list)

    def key(self) -> str:
        return f"{self.effect}:{self.of}" + (f":{self.name}" if self.name else "")
```

Validation, in this order — **structural checks first, justification last**, because the citation
check firing first reported *"salmon does not fill role alignment"* as *"this row needs a cite"*:

```python
def _validate_target(target, index, *, roles, params_by_contract, seen):
    fillers = [c for c in roles.get(target.of, [])]
    if not fillers:
        raise RuleValidationError(
            f"MD0306: decision {index}: no contract fills role {target.of!r}.\n"
            f"  Roles that are filled: {', '.join(sorted(roles))}"
        )
    if target.effect is Effect.PARAM:
        if target.name is None:
            raise RuleValidationError(f"MD0307: decision {index}: a param effect needs a name")
        narrowed = target.when_implementation or fillers
        missing = [c for c in narrowed if target.name not in params_by_contract.get(c, set())]
        if missing:
            raise RuleValidationError(
                f"MD0308: decision {index}: {target.name!r} is not declared by "
                f"{', '.join(sorted(missing))}, which can fill role {target.of!r}.\n"
                f"  The value would be dead whenever one of those wins. Narrow with "
                f"`when_implementation:`, or decide a param they all declare."
            )
    if target.key() in seen:
        raise RuleValidationError(
            f"MD0309: decision {index} and decision {seen[target.key()]} both decide "
            f"{target.key()!r} in the same layer."
        )
    seen[target.key()] = index
```

Key the `Kind` on `decision.decides.key()` as before, so REPLACE stacking still works — but now
the key is `(effect, role, name)` rather than a type id, which is what stops two unrelated
decisions colliding.

- [ ] **Step 4: Run the tests**

Run: `uv run pytest packages/mendel-resolver/tests/test_rules.py -v`
Expected: PASS

- [ ] **Step 5: Add `test_every_contract_declares_a_role` and close Task 0's open row**

```python
def test_every_contract_in_the_registry_declares_a_role():
    """Task 0 left `roles:` optional so the field could be added without rewriting every
    layer that day. This is the guard that makes the registry keep it."""
    layers = layer_loader.load(Path("registry"))
    missing = [c.id for c in layers.registry.all() if not c.roles]
    assert missing == [], f"these contracts fill no role: {missing}"
```

- [ ] **Step 6: Watch the guard fail, then commit**

Delete `roles:` from `star-align.yml`. Three tests fail and ten more error — this closes the
"nothing failed" row recorded in Task 0. Then revert `MD0309`, `MD0308` and `MD0306` in turn.
Restore, append the rows, then:

```bash
git add -A
git commit -m "feat(resolver): a decision names a role, and cannot collide (A119, A123, R20)"
```

> **Corrected 2026-08-15, on execution. Five things, and the first is a scope move.**
>
> 1. **`registry/rules/rnaseq.yml` migrates here, not at Task 11.** `DecisionTarget` changes
>    incompatibly, so leaving the shipped rule in the old format puts `make check` red for
>    seven tasks — which the Global Constraints forbid. Task 11 keeps the retirement and the
>    documentation. `producer_of: alignment.bam` becomes `{effect: implementation, of: alignment}`.
> 2. **The consumers move to premises, and `route()` refuses a rule table without them.**
>    `rules.value_for(param, profile)` becomes `value_for(roles, param, premises,
>    implementation=…)` and `producer_for(type_id, profile)` becomes `implementation_for(role,
>    premises)`, with the router deriving the roles in play from its candidates. `premises or {}`
>    is deliberately *not* the default: an empty premise set makes every `when` fail, so a caller
>    that forgot the argument would get a table that silently stops firing — A122 through a
>    default. `resolve()` builds them once and threads them.
> 3. **`derives:` is parsed here**, by the same `Kind`, keyed `derive:<fact>`. Task 2 built the
>    derivation type and nothing loaded it; leaving that until Task 11 would have shipped the
>    format's own dead-rule pathology for seven tasks.
> 4. **`when` validation moved out of `parse` into a post-assembly pass** (`MD0310`,
>    `RuleTable.check_premise_names`). A decision may read a fact a derivation in another file
>    supplies, so a per-file check refuses legitimate rules by load order. Same reason
>    `roles.check` runs after the registry is assembled.
> 5. **`MD0307` covers two more cases than the plan gives it**: a `name` on a non-`param`
>    effect, and a presence row whose `then` is neither `present` nor `absent`. Both would
>    otherwise change or corrupt the key silently, which is `MD0309`'s subject one level down.
>
> The plan's `test_a_decision_must_decide_exactly_one_thing` is gone: `effect` is a required
> discriminator, so the state it tested is unrepresentable. It is replaced by three tests over
> `MD0307`.

---

## Task 5: presence, and a conventional state requirement

**Spec:** §4.1, §8.2. The finding that nearly shipped: `presence: absent` makes the spine
unroutable, because `state_required: [trimmed]` is a convention wearing a structural constraint.

**Files:**
- Modify: `packages/comeni-core/src/comeni_core/contract.py` (`InputPort.state_required_because`)
- Modify: `packages/mendel-resolver/src/mendel_resolver/router.py`
- Modify: `registry/contracts/nf-core/star-align.yml`, `hisat2-align.yml`
- Test: `packages/mendel-resolver/tests/test_presence.py`

**Interfaces:**
- Produces: `InputPort.state_required_conventional: list[StateName]`;
  `RuleTable.presence_for(role, premises) -> Fired | None`.

- [ ] **Step 1: Write the failing test**

```python
def test_removing_a_conventionally_required_state_still_routes():
    """§8.2. STAR soft-clips; --skip_trimming exists because trimming is optional. So
    `trimmed` is a convention, and only a structural requirement may block routing."""
    plan = route(goal_with(read_length=150), registry_without("nf-core/trimgalore@0.6.10"),
                 vocabulary, absent_roles={"trimming"})
    assert "nf-core/star/align@1.11.0" in [s.contract_id for s in plan.steps]
    assert "nf-core/trimgalore@0.6.10" not in [s.contract_id for s in plan.steps]


def test_removing_a_structurally_required_state_is_refused():
    """featureCounts genuinely requires a coordinate-sorted BAM; absence is unroutable and
    must say so rather than emitting something that dies at run time."""
    with pytest.raises(UnroutableError, match="coordinate_sorted"):
        route(a_goal, registry, vocabulary, absent_roles={"bam_sorting"})
```

- [ ] **Step 2: Run it and watch it fail**

Run: `uv run pytest packages/mendel-resolver/tests/test_presence.py -v`
Expected: FAIL — `route()` has no `absent_roles` parameter

- [ ] **Step 3: Split the state requirement on `InputPort`**

```python
    state_required: list[StateName] = Field(default_factory=list)
    """States this port cannot function without. A structural constraint: absence is
    unroutable and is refused."""

    state_required_conventional: list[StateName] = Field(default_factory=list)
    """States this port is conventionally given but does not require.

    `star/align` declared `state_required: [trimmed]`, and STAR soft-clips adapters --
    nf-core/rnaseq's `--skip_trimming` exists precisely because trimming is optional. So the
    contract encoded a tier-2 convention as a tier-1 constraint, and a rule deciding that
    trimming should be absent produced an *unroutable pipeline* rather than a shorter one.
    Same disease as `the only contract that produces this` (A113), one layer down.
    """
```

Move `trimmed` from `state_required` to `state_required_conventional` on both aligner contracts,
with a `because` naming the soft-clipping.

- [ ] **Step 4: Teach `route()` about absent roles**

In `router.route`, accept `absent_roles: frozenset[str] = frozenset()` and, in `_choose`, exclude
any contract filling an absent role. In `_satisfy_port`, treat
`state_required_conventional` as satisfiable by a port lacking those states.

- [ ] **Step 5: Run the tests**

Run: `uv run pytest packages/mendel-resolver/tests/test_presence.py -v && make verify`
Expected: PASS. **`make verify` is mandatory here** — this is a routing change and
`tests/test_counts.py` is the only thing that proves the spine still produces a counts matrix.

- [ ] **Step 6: Watch the guard fail, then commit**

Move `trimmed` back to `state_required` on `star-align.yml`; three tests fail with the real
`nothing produces fastq.reads with states ['trimmed']` message. Then revert the `absent_roles`
filter, the conventional alternative, and the `resolve()` wiring in turn. Restore, record, then:

```bash
git add -A
git commit -m "feat: a step can be absent, and a convention cannot block routing (§8.2)"
```

> **Corrected 2026-08-15, on execution. Four things.**
>
> 1. **The fallback is two `Alternative`s, not a flag threaded through the router.** `accepts`
>    already means *try this, then that*, first-match-wins, so `alternatives()` returns the
>    conventional form followed by the structural one. A second mechanism for the same idea is
>    a second place for the two to disagree, and `_satisfy_port`'s failure list stays correct
>    for free.
> 2. **A conventional requirement must keep driving insertion**, and the plan does not say so.
>    Simply dropping `trimmed` from `state_required` deletes trimming from *every* pipeline:
>    the goal's raw `fastq.reads` then satisfies the aligner directly and TrimGalore is never
>    inserted. `test_the_spine_still_inserts_trimming_when_no_rule_removes_it` is the guard,
>    and reverting the fallback fails it and the spine reachability test and nothing else.
> 3. **`state_conventional_because`, not `state_required_because`.** The latter reads as
>    justifying `state_required`, which is the field it is not about, and the distinction
>    between the two is the whole of §8.2.
> 4. **`resolve()` computes `absent_roles` from `presence_for`, and an end-to-end test covers
>    it.** `presence_for` shipped in Task 4 and nothing called it; a method being correct is a
>    separate fact from anything calling it, which is Task 0's recorded lesson.
>
> **`presence: present` does nothing, and that is deliberate.** It is the default branch of a
> presence decision — "absent below 50bp, otherwise present" — where *present* means leave
> routing alone. Forcing a step routing would not otherwise insert is a different feature and
> is §4.1's open half; it is carried, not implemented.

---

## Task 6: one decision, several effects

**Spec:** §4.2. `star_ignore_sjdbgtf` depends on how the index was built — one choice, two tools.

**Files:**
- Modify: `packages/mendel-resolver/src/mendel_resolver/rules.py`
- Test: `packages/mendel-resolver/tests/test_rules.py`

- [ ] **Step 1: Write the failing test**

```python
def test_one_decision_lands_on_two_tools(load_rules, premises):
    """A decision that reads another decision buys ordering, cycles, and the loss of the
    single pass. 'Where the annotation is used' is one choice with two flags."""
    table = load_rules("""
    decisions:
      - decides:
          - {effect: param, of: index_building, name: sjdbgtffile,
             when_implementation: [nf-core/star/genomegenerate@1.11.0]}
          - {effect: param, of: alignment, name: star_ignore_sjdbgtf,
             when_implementation: [nf-core/star/align@1.11.0]}
        because: "splice junctions can be supplied at index time or at align time"
        cite: "STAR manual 2.2.3"
        rows: [{when: {}, then: false, cite: "STAR manual 2.2.3"}]
    """)
    fired = table.effects_for(premises)
    assert {f.key() for f in fired} == {
        "param:index_building:sjdbgtffile", "param:alignment:star_ignore_sjdbgtf"}
    assert {f.cite for f in fired} == {"STAR manual 2.2.3"}, "one choice, one citation"
```

- [ ] **Step 2: Run it and watch it fail**

Run: `uv run pytest packages/mendel-resolver/tests/test_rules.py -k two_tools -v`
Expected: FAIL — `decides` rejects a list

- [ ] **Step 3: Accept a list of targets**

```python
    decides: DecisionTarget | list[DecisionTarget]

    def targets(self) -> list[DecisionTarget]:
        """A decision landing on two tools is ONE choice with one premise and one citation.

        Modelling it as two decisions would make the second read the first, and decisions
        reading decisions is what this format refuses -- it buys evaluation order, the
        possibility of a cycle, and the loss of `build_premises`' single pass.
        """
        return self.decides if isinstance(self.decides, list) else [self.decides]
```

Validate and fire per target; the key check in Task 4 already runs per target.

- [ ] **Step 4: Run the tests**

Run: `uv run pytest packages/mendel-resolver/tests/test_rules.py -v`
Expected: PASS

- [ ] **Step 5: Watch the guard fail, then commit**

Make `targets()` return `[self.decides[0]]` for a list. Confirm the test fails on the set
comparison, naming the missing key. Restore, record, then:

```bash
git add packages/mendel-resolver
git commit -m "feat(resolver): one decision may land on several tools (root 5 §4.2)"
```

---

## Task 7: the tier a decision earned

**Spec:** §1, §4.4. A113, A83's naming, and the catch-all defect.

**Files:**
- Modify: `packages/mendel-resolver/src/mendel_resolver/rules.py` (tier-2 citation at load)
- Modify: `packages/mendel-resolver/src/mendel_resolver/resolve.py` (`_source_for`'s tier-1 reason)
- Test: `packages/mendel-resolver/tests/test_earned_tiers.py`

- [ ] **Step 1: Write the failing test**

```python
def test_a_tier_2_row_must_carry_a_citation(load_rules):
    """A76/A128, stated as a rule rather than fixed twice. Tier 2 produces value + citation."""
    with pytest.raises(RuleValidationError, match="exits at tier 2"):
        load_rules("""
        decisions:
          - decides: {effect: presence, of: trimming}
            rows: [{when: {}, then: absent, because: "nothing to trim"}]
        """)


def test_only_one_candidate_is_not_a_forcing_constraint():
    """A113. Tier 1 produces `value + the forcing constraint`, and 'this stack holds one
    contract' is a fact about registry contents, not about the inputs."""
    ir = build(a_goal)
    sorter = ir.node("samtools_sort")
    assert sorter.selection.tier is Tier.CONVENTION
    assert "only contract" not in sorter.selection.reason
    assert "uncontested" in sorter.selection.reason


def test_the_presence_of_a_forced_step_is_still_tier_1():
    """The other half: featureCounts requires coordinate_sorted, so a sorter must exist."""
    ir = build(a_goal)
    assert ir.presence_of("bam_sorting").tier is Tier.STRUCTURAL
```

- [ ] **Step 2: Run it and watch it fail**

Run: `uv run pytest packages/mendel-resolver/tests/test_earned_tiers.py -v`
Expected: FAIL — the tier-2 row loads, and `samtools_sort` reports tier 1

- [ ] **Step 3: Enforce the citation at load, and split the two questions in `_source_for`**

In `_validate`, after the structural checks:

```python
        if tier_of_row(row.when) is Tier.CONVENTION and not (row.cite or decision.cite):
            raise RuleValidationError(
                f"MD0310: {path}, decision {target.key()}, row {index}\n"
                f"  This row tests no premise positively, so it exits at tier 2 -- a\n"
                f"  documented default. Tier 2 produces `value + citation` and this row has\n"
                f"  neither a row `cite` nor a block one."
            )
```

In `_source_for`, replace the single tier-1 `"the only contract that produces this"` with two
records: the step's **presence** at `Tier.STRUCTURAL` citing the consumer's requirement, and its
**implementation** at `Tier.CONVENTION` with
`f"uncontested — the only contract filling {role} in this stack"`.

- [ ] **Step 4: Run the tests**

Run: `uv run pytest packages/mendel-resolver/tests/test_earned_tiers.py -v && make verify`
Expected: PASS

- [ ] **Step 5: A tier says what it means, in the artifact (spec §6.2)**

`tier: 3` is a number whose meaning lives in a table in another document. `review_level_for` is
already a function of the tier, so carry the answer:

```python
def test_a_decision_states_its_own_review_level():
    """A reader should not need CLAUDE.md open to learn what tier 3 obliges them to do."""
    ir = build(a_goal)
    why = ir.step("star_align").why
    assert why.tier is Tier.DATA_PROFILED
    assert why.review is ReviewLevel.ADVISORY


def test_the_review_level_is_derived_and_cannot_disagree_with_the_tier():
    """Two fields that can disagree is a field that will. Computed, never stored."""
    assert Why(tier=Tier.CONVENTION, ...).review is ReviewLevel.NONE
```

`pipeline.py` imports neither `ReviewLevel` nor `review_level_for` today — both live in
`comeni_core.tiers` beside `Tier`, which it already imports. On `Why`, as a `@computed_field` so
it serialises into `pipeline.yml` and cannot drift from the tier it describes:

```python
    @computed_field
    @property
    def review(self) -> ReviewLevel:
        """What this tier obliges a reader to do, beside the tier itself.

        Derived rather than stored: a stored copy is a second source of truth for one fact,
        and `Why` already learned that lesson once — `for_value` exists because a reason
        could outlive the value it explained (A104).
        """
        return review_level_for(self.tier)
```

- [ ] **Step 6: Confirm the review queue did not grow**

```bash
uv run mendel build --goal examples/rnaseq-goal.yml --registry registry/ --out /tmp/t --gate lint
```

Expected: still `1 requiring review` (`star_align.seq_platform`). Tier 1 is silent and tier 2 is
green; if this number moved, the split is wrong and the plan must stop here.

- [ ] **Step 7: Watch the guard fail, then commit**

Five reverts: the `MD0313` rule, the single-candidate tier, both `because` threads, and
`Why.review_level`. Restore, record, then:

```bash
git add -A
git commit -m "feat(resolver): a decision exits at the tier its evidence earned (A113)"
```

> **Corrected 2026-08-15, on execution. Six things.**
>
> 1. **`MD0313`, not `MD0310`.** The plan gives this rule `MD0310`, which Task 4 already spent
>    on the `when`-premise check. `MD0302`–`MD0311` is fully allocated; `MD0300`–`MD0399` is
>    the reserved band.
> 2. **The A113 split lives in `router._choose`, not `resolve._source_for`.** The plan names
>    the wrong function; `_source_for` picks an upstream output for a port and never assigns a
>    selection tier.
> 3. **The presence half needs a field, and it is `IRNode.presence` → `Step.presence`.**
>    `tests/test_pipeline_totality.py` refuses an IR field with no home in the artifact, so
>    this could not be IR-only. Named `presence` rather than `exists` because it matches
>    `effect: presence` in the rule format, and because `test_pipeline_totality` keys on field
>    names.
> 4. **`SCHEMA_VERSION` goes to 3 here**, not in Task 8. `Step.presence` and
>    `Why.review_level` both change the serialised shape, and
>    `test_a_schema_change_bumps_the_version` is what said so.
> 5. **`review_level`, not `review`.** `ResolvedValue.review_level` has computed the same thing
>    since Plan 1, and two names for one concept is how the two come to disagree. `Why` also
>    needs `_drop_computed`, or a `pipeline.yml` this Mendel writes cannot be read back.
> 6. **Step 5's test as written is inert**, and reverting proved it: it reads
>    `ResolvedValue.review_level`, which already existed. The guard has to build a real
>    `Pipeline` and read `step.why.review_level`.
>
> Step 6's manual check is now `test_the_review_queue_did_not_grow`, because a check somebody
> has to remember to run is a check that stops being run — which is A14's own subject.

---

## Task 8: the premise reaches the artifact

**Spec:** §6. A108 and A127, and the hook issue #2 needs.

**Files:**
- Modify: `packages/comeni-core/src/comeni_core/pipeline.py` (`SCHEMA_VERSION = 3`, `Why.premise`)
- Modify: `packages/mendel-resolver/src/mendel_resolver/resolve.py`
- Test: `packages/comeni-core/tests/test_pipeline_file.py`

- [ ] **Step 1: Write the failing test**

```python
def test_a_tier_3_decision_records_the_premise_it_rested_on():
    """A108: measured and asserted builds had a byte-identical steps: block."""
    measured = build(goal_with(strandedness=("reverse", "measured")))
    asserted = build(goal_with(strandedness=("reverse", "asserted")))
    assert measured.model_dump() != asserted.model_dump()
    why = measured.setting("subread_featurecounts", "min_mqs").why
    assert why.premise == {"purpose": "expression"}
    assert why.premise_origin == {"purpose": "goal"}


def test_a_version_2_document_backfills_an_empty_premise():
    """A document written before the field existed cannot answer. Requiring it of one asserts
    the premise is *missing* rather than *never recorded* -- the Task 0 lesson from 1.14."""
    loaded = Pipeline.model_validate(a_v2_document)
    assert loaded.version == 2
    assert loaded.steps[0].why.premise == {}
```

- [ ] **Step 2: Run it and watch it fail**

Run: `uv run pytest packages/comeni-core/tests/test_pipeline_file.py -k premise -v`
Expected: FAIL — `Why` has no field `premise`

- [ ] **Step 3: Add the fields and the migration**

```python
SCHEMA_VERSION = 3
```

On `Why`:

```python
    premise: dict[str, Any] = Field(default_factory=dict)
    """The premises this decision read, and their values. Tier 3 is *advisory* -- "the
    machinery worked, check the premise" -- and until version 3 there was no premise to
    check. Audit A108, A127."""

    premise_origin: dict[str, str] = Field(default_factory=dict)
    """Where each premise came from: measured, asserted, goal, derived, unmeasured.

    This is what `ProfilePolicy` reads to make `sealed` refuse a tier-3 decision resting on
    an assertion (issue #2), which is why the origin travels with the value rather than
    being recoverable by joining against the profile."""
```

Extend the existing version-1 backfill validator to leave `premise` empty for `version < 3`,
following the shape already in `pipeline.py` around line 489.

- [ ] **Step 4: Run the tests**

Run: `uv run pytest packages/comeni-core/tests -v && make verify`
Expected: PASS

- [ ] **Step 5: The premise reads as prose, not as a dict repr (spec §6.1)**

A mapping is what a policy reads; it is not what a person reads. Today's artifact says

```yaml
reason: 'rule producer_of:alignment.bam matched {''read_length'': ''>= 70''}: STAR''s …'
```

— a Python dict repr embedded in YAML with doubled quotes, reporting the **predicate** and never
the **value**. A reader learns the rule tested `>= 70` and never learns `read_length` was 150, or
that anything measured it. The premise is the one thing tier 3 asks a reviewer to check.

```python
def test_the_reason_states_the_premise_value_not_the_predicate():
    ir = build(goal_with(read_length=150))
    reason = ir.step("star_align").why.reason
    assert "read_length is 150, measured" in reason
    assert "{" not in reason, "no dict repr reaches a sentence a person reads"
    assert ">= 70" not in reason, "the predicate is the rule's business, not the reader's"


def test_an_inferred_premise_says_so_in_the_sentence():
    """Scenario B of the spec: nothing measured strandedness."""
    ir = build(goal_with_no_strandedness())
    reason = ir.setting("hisat2_align", "save_unaligned").why.reason
    assert "strandedness is reverse, inferred" in reason
    assert "nothing measured it" in reason
```

Replace `Pin.reason_line`'s `f"{head} matched {matched}"` — where `matched` is the raw `when`
mapping — with a clause built from the premises actually read. `_ORIGIN_PROSE` maps
`MEASURED -> "measured"`, `ASSERTED -> "asserted, not measured"`,
`GOAL -> "declared in the goal"`, `DERIVED -> "inferred — nothing measured it"`, and
`_premise_clause` joins `f"{p.id} is {p.value}, {_ORIGIN_PROSE[p.origin]}"` with `"; "`.

The value comes first because it is what a reviewer checks against the sample sheet; the origin
comes second because it is what tells them whether checking is worth their time.

`premise` and `premise_origin` stay as the machine-readable companion — `ProfilePolicy` reads
those. Neither replaces the other: shipping only the mapping repeats, one level up, the exact
defect this plan exists to fix.

- [ ] **Step 6: Check the digest did not move for archived pipelines**

This is Plan 1.14's Task 0 lesson: adding a field moves an archived pipeline's `from_digest`, so
`MD0213` reports a schema change as a human edit. Run
`uv run pytest -k "digest or stale" -v` and confirm the v2 fixture still verifies.

- [ ] **Step 7: Watch the guard fail, then commit**

Delete `premise_origin` from the `Why` written in `resolve.py`. Confirm
`test_a_tier_3_decision_records_the_premise_it_rested_on` fails on the origin assertion. Restore,
record, then:

```bash
git add -A
git commit -m "feat(core): a decision records the premise it rested on — version 3 (A108, A127)"
```

> **Corrected 2026-08-15, on execution. Five things, and the first is forced.**
>
> 1. **`premise: dict[str, Any]` cannot exist.** `Why` is reachable from door 4 and
>    `tests/test_egress.py` refuses it three ways at once — a mapping, an `Any`, and a bare
>    `str` key. It is `list[PremiseRecord]`, one record carrying id, value and origin, which
>    is the better shape anyway: two parallel mappings can disagree about their key sets.
>    `premise_origin` is gone into that record.
> 2. **`PremiseOrigin` moves to `comeni_core.tiers`**, beside `ValueSource`. The artifact
>    carries it and `comeni-core` must not depend on `mendel-resolver` — the move `Goal` and
>    `DataProfile` both made. `premises.py` re-exports it. `PremiseRecord` gets its own module
>    (`comeni_core/premise.py`) because `pipeline.py` imports `ir.py`, so neither can host it.
> 3. **`SCHEMA_VERSION` was already 3**, bumped in Task 7 by `Step.presence`.
> 4. **Two code paths carry a premise**, and the plan's tests only reach one. A *selection*
>    goes through `RouteStep.selection_premise`; a *param* goes through `Pin.premise` in
>    `_resolve_param`. Reverting the param line left every premise test green.
> 5. **A goal-file profile entry is `ASSERTED`, not `GOAL`.** `GOAL` is reserved for the
>    goal's own shape, which `required_states` carries. So the prose is *"asserted, not
>    measured"*, which is the sentence a reviewer needs.
>
> The v2 fixture the plan asks for does not exist; `docs/internal/audits/fixtures/pipeline-v1`
> is the committed archived document and serves the same purpose, so the test asserts
> `version < SCHEMA_VERSION` rather than a literal.

---

## Task 9: exhaustiveness over a declared domain

**Spec:** §7.1. A124, without forcing a catch-all that would demote a tier-3 branch.

**Files:**
- Modify: `packages/mendel-resolver/src/mendel_resolver/rules.py`
- Test: `packages/mendel-resolver/tests/test_rules.py`

- [ ] **Step 1: Write the failing test**

```python
def test_two_complementary_comparisons_are_exhaustive(load_rules):
    """The shipped aligner rule: >= 70 and < 70, no catch-all. Demanding one would demote
    Kim et al.'s branch from tier 3 to tier 2 and strip its premise."""
    table = load_rules("""
    decisions:
      - decides: {effect: implementation, of: alignment}
        rows:
          - {when: {read_length: ">= 70"}, then: nf-core/star/align@1.11.0, cite: "Dobin 2013"}
          - {when: {read_length: "< 70"},  then: nf-core/hisat2/align@2.2.2, cite: "Kim 2019"}
    """)
    assert len(table.decisions) == 1


def test_a_gap_in_an_ordered_domain_is_refused(load_rules):
    with pytest.raises(RuleValidationError, match="between 50 and 70"):
        load_rules("""
        decisions:
          - decides: {effect: implementation, of: alignment}
            rows:
              - {when: {read_length: ">= 70"}, then: nf-core/star/align@1.11.0, cite: "a"}
              - {when: {read_length: "< 50"},  then: nf-core/hisat2/align@2.2.2, cite: "b"}
        """)


def test_an_enum_is_exhaustive_when_the_rows_cover_its_values(load_rules):
    """strandedness has exactly three values and extensible: false, so three rows suffice."""
    assert load_rules(THREE_ROWS_OVER_STRANDEDNESS).decisions


def test_an_extensible_enum_still_needs_a_catch_all(load_rules):
    """An overlay may add a value, so coverage today is not coverage tomorrow."""
    with pytest.raises(RuleValidationError, match="extensible"):
        load_rules(THREE_ROWS_OVER_AN_EXTENSIBLE_ENUM)
```

- [ ] **Step 2: Run it and watch it fail**

Run: `uv run pytest packages/mendel-resolver/tests/test_rules.py -k exhaustive -v`
Expected: FAIL — no completeness check exists

- [ ] **Step 3: Implement the partition check**

```python
def _exhaustive(rows, measurements) -> str | None:
    """None if the rows cover their premise's domain, else what is uncovered.

    Ordered kinds: `>= x` and `< x` are complementary by construction, so a pair at the same
    boundary is exhaustive without any bound being declared. Enums: covered when the values
    are covered and `extensible` is false.

    A catch-all is still legal and still exhaustive -- it is just no longer *required*, which
    matters because requiring one demotes the last branch to tier 2 and takes its citation
    with it.
    """
```

Refuse with `MD0311`, naming the uncovered interval or the missing enum values.

- [ ] **Step 4: Run the tests**

Run: `uv run pytest packages/mendel-resolver/tests/test_rules.py -v`
Expected: PASS

- [ ] **Step 5: Watch the guard fail, then commit**

Make `_exhaustive` return `None` unconditionally. Confirm `test_a_gap_in_an_ordered_domain_is_refused`
fails. Restore, record, then:

```bash
git add -A
git commit -m "feat(resolver): completeness is checked against the declared domain (A124)"
```

> **Corrected 2026-08-15, on execution. Four things.**
>
> 1. **Six shipped fixtures were incomplete tables**, across four files — the largest fixture
>    consequence in this plan, and the finding rather than an inconvenience. Each answered part
>    of its premise's domain and demoted silently to tier 4 for the rest.
> 2. **Completing them does not break the miss test.**
>    `test_rule_miss_demotes_to_tier_4_and_flags` carries an empty profile, so every row fails
>    its own predicate whatever the table covers. Worth checking rather than assuming: a
>    completeness check that made misses unreachable would have removed tier 4's own test.
> 3. **Overlaps are legal and are not gaps**, and a test says so. `>= 50` beside `< 70` covers
>    the line twice; first-match-wins already settles it, and refusing it would be enforcing a
>    different property under completeness' name.
> 4. **Checked after the stack is assembled**, like `MD0310`: `add_values` lets an overlay
>    extend an enum, so a table exhaustive against the base layer alone is not exhaustive
>    against the stack it will run under.
>
> `_sole_premise`'s first draft carried an unreachable clause — `any(len(row.when) > 1 …)`
> cannot be true when `len(tested) != 1` is false. Found by reverting it and watching nothing
> fail; deleted rather than kept.

---

## Task 10: a param declares its domain, and `then` is type-checked

**Spec:** §7.1's second half. A118, replacing a character class with a type check.

**Files:**
- Modify: `packages/comeni-core/src/comeni_core/contract.py` (`Param.domain`)
- Modify: `packages/mendel-resolver/src/mendel_resolver/rules.py` (retire `_computed_over`)
- Test: `packages/mendel-resolver/tests/test_rules.py`

- [ ] **Step 1: Write the failing test**

```python
def test_a_then_outside_the_params_domain_is_refused(load_rules):
    """A118: `then: "read_length-1"` loaded, resolved at tier 3 with a citation, and reached
    STAR as a literal string. The only thing that refused it was a shell-injection character
    class that permits `-`."""
    with pytest.raises(RuleValidationError, match="min_mqs accepts an integer"):
        load_rules("""
        decisions:
          - decides: {effect: param, of: quantification, name: min_mqs}
            rows: [{when: {}, then: "read_length-1", cite: "STAR manual 2.2.2"}]
        """)


def test_a_legitimate_value_containing_a_measurement_name_still_loads(load_rules):
    """The negative that keeps it honest: `paired` is a declared measurement, so a substring
    test would refuse `paired-end`, a legitimate value killed by a check nobody could disable."""
    assert load_rules(SEQ_PLATFORM_IS_PAIRED_END).decisions
```

- [ ] **Step 2: Run it and watch it fail**

Run: `uv run pytest packages/mendel-resolver/tests/test_rules.py -k domain -v`
Expected: FAIL — `Param` has no `domain`

- [ ] **Step 3: Add `Param.domain` and type-check `then`**

```python
    domain: ParamDomain | None = None
    """What values this parameter accepts. `None` means undeclared, which is legal and is
    what every contract says today.

    Without it, `MD0300` had to guess whether a `then` was arithmetic by looking for a
    measurement name beside an operator -- a heuristic that admits anything spelled
    unexpectedly and refuses `paired-end`. With it, the question is a type check.
    """
```

`ParamDomain` mirrors `Measurement`: `kind`, `values`, `minimum`, `maximum`. Declare it on the
five params the shipped contracts have (`min_mqs`, `index_format`, `save_unaligned`,
`star_ignore_sjdbgtf`, `seq_platform`). Keep `_computed_over` as a fallback for params with no
declared domain, and say so in its docstring.

- [ ] **Step 4: Run the tests, then commit**

Run: `uv run pytest packages/mendel-resolver/tests -v && make verify`

Watch the guard fail by widening `min_mqs`'s domain to `kind: string`; confirm the first test
fails. Restore, record, then:

```bash
git add -A
git commit -m "feat: a param declares its domain, so a computed then is a type error (A118)"
```

> **Corrected 2026-08-15, on execution. Four things.**
>
> 1. **Four params get a domain, not five.** `seq_platform` deliberately declares none: the
>    list of sequencing platforms cannot be enumerated, and a param whose legal values are
>    open is exactly the case `domain: None` exists for. It also keeps `_computed_over`'s
>    path tested.
> 2. **`_domain_of` requires unanimity across the implementations**, not "take the first".
>    Two fillers declaring different domains is a registry defect, and taking the first
>    decides which contract is right by load order. Falling back to the heuristic refuses less
>    and invents nothing; refusing the disagreement outright needs a code of its own and is
>    carried.
> 3. **The plan's revert does not work.** `MeasurementKind` has no `string` member, so
>    "widening `min_mqs`'s domain to `kind: string`" cannot be written. The reverts used
>    instead are the type-check branch, the range check, `_computed_over`, and the unanimity
>    check.
> 4. **Both paths emit `MD0300`**, since both refuse the same thing — a `then` the tool cannot
>    receive — and one concern gets one code.

---

## Task 11: migrate the registry, retire the old format, write it down

**Files:**
- Rewrite: `registry/rules/rnaseq.yml`
- Delete: `RuleTable.value_for`, `producer_for`, `DecisionTarget.param`/`producer_of`
- Modify: `docs/reference/pipeline-schema.md`, `docs/design/rule-tables-and-port-logic.md` §13,
  `CLAUDE.md`, `docs/internal/journal/`
- Test: `tests/test_counts.py` (unchanged, must stay green)

- [ ] **Step 1: Rewrite the shipped rule into the new format**

`decides: {effect: implementation, of: alignment}`, the two comparison rows unchanged, keeping
each row's own `because` and `cite` and the block's axis citation — the A79/A107 split from
Plan 1.14 survives intact.

- [ ] **Step 2: Run the full gate**

Run: `make verify`
Expected: PASS, **124 genes**, featureCounts invoked with `-s 2 -p -Q 0`. If the counts matrix
moved, the migration changed a decision and the plan must stop.

- [ ] **Step 3: Delete the old surface**

Remove `value_for`, `producer_for`, and the `param`/`producer_of` target fields. A grep for
`producer_of` outside the audit fixtures must return nothing.

- [ ] **Step 4: Turn the twenty rule attempts into tests**

`docs/internal/audits/fixtures/rule-attempts/` says its value is recording what the format could
not express, and that a future task repairing the format **turns them into tests**. This is that
task. Add `tests/test_rule_corpus.py` asserting each of the twenty either loads or is refused with
the expected code, and update the fixtures' README to say they are now wired in.

- [ ] **Step 5: Route every coded refusal to `mendel explain` (issue #36, A75)**

This plan adds ten codes on a path that prints them bare. Verified on 2026-08-15:

```
$ uv run mendel build --registry <a layer with a computed then> ...
mendel: a rule table will not load —
MD0300: …/bad.yml, decision param:min_mqs
```

Nothing tells the reader `mendel explain MD0300` exists, and the machinery is already built.
Folded in here rather than filed again, because writing ten codes and then fixing them is
strictly worse than writing them right. In `mendel_compiler/cli.py`'s `main()`:

```python
_CODE = re.compile(r"\bMD0\d{3}\b")


def _with_pointer(message: str) -> str:
    """A coded refusal names the code and says how to read the long form.

    23 `ValueError` sites embed a real code and the CLI printed the raw message, so the one
    verb that explains them was undiscoverable from the failure that needed it. Audit A75,
    issue #36.
    """
    found = _CODE.search(message)
    return f"{message}\n  run: mendel explain {found.group()}" if found else message
```

Wrap the `print(..., file=sys.stderr)` calls in the refusal paths with it. Test:

```python
def test_a_coded_refusal_tells_the_reader_how_to_read_it(capsys, a_bad_rule_layer):
    assert main(["build", "--goal", GOAL, "--registry", a_bad_rule_layer, "--out", "x"]) == 1
    assert "run: mendel explain MD0300" in capsys.readouterr().err


def test_an_uncoded_refusal_gains_no_pointer(capsys):
    assert "mendel explain" not in _with_pointer("something went wrong")
```

Watch it fail by returning `message` unchanged; confirm the first test fails and the second
still passes.

- [ ] **Step 6: Update the documents**

`rule-tables-and-port-logic.md` §13's three reasoned limits are now closed or renamed; say which.
`CLAUDE.md`'s tier table gains the **Produces** column, because dropping it is what let the tiers
drift. Add a journal entry.

- [ ] **Step 6: Sync `comeni-registry`, and make drift green**

`registry/` here IS the published layer. `roles/`, the `roles:` field on twelve contracts, and
the rewritten `rules/rnaseq.yml` all cross now — not earlier, because A26 makes an unknown
directory a fatal load error for any Mendel that predates this plan.

```bash
make drift                      # expect: the roles: additions, and rules/rnaseq.yml
cp -r registry/roles       ../../../comeni-registry/roles
cp -r registry/contracts/. ../../../comeni-registry/contracts/
cp    registry/rules/*.yml ../../../comeni-registry/rules/
make drift                      # expect: no drift
```

Commit in `comeni-registry` **saying which way the copy went and why** — the two repositories
have no shared history, so nothing else records it. Tag it, since consumers pin tags.

**This is a breaking change to the published layer**, and the commit must say so: a layer
containing `roles/` cannot be loaded by a released Mendel older than Plan 1.15.

- [ ] **Step 7: Final commit**

```bash
make verify && uv run ruff check .
git add -A
git commit -m "feat: the rule format, re-derived — root 5 closed (A119-A124, A127, A108, A113)"
```

---

## Related issues, and what was checked

Decided 2026-08-15, after checking rather than reading — all fifteen open round-four and
design issues were verified against the code, and every one is unimplemented rather than
done-and-unclosed.

| Issue | Relationship to this plan |
|---|---|
| [#39](https://github.com/comeni-project/Comeni-Labs/issues/39) | **this plan is its closure.** `MD0300`'s own message already points at it |
| [#38](https://github.com/comeni-project/Comeni-Labs/issues/38) | stays open. The format works without `adapter_content`, `max_chromosome_length` and `rrna_fraction`; only a wider corpus needs them (spec §7.4) |
| [#36](https://github.com/comeni-project/Comeni-Labs/issues/36) | **folded into Task 11 Step 5.** This plan adds ten codes on the path A75 describes |
| [#32](https://github.com/comeni-project/Comeni-Labs/issues/32) | **checked and it is NOT a prerequisite.** An earlier draft said Task 8 needed it first. `Why` is not in the totality guard's `REPLACED` list — that guard compares the sixteen replaced types' fields against `Pipeline`'s names, and A68 bites on *deleting or renaming* a replaced type's field, which no task here does |
| [#35](https://github.com/comeni-project/Comeni-Labs/issues/35) | not touched. A rule defect already surfaces as *"a rule table will not load"*, not as A74's *"this goal is not valid"* |
| #24–#31, #33, #34 | not touched. **Four are PLAUSIBLE and unverified since round four** — their plan's first task must be reproducing them, not fixing them, which is what A119 taught this repository on 2026-08-15 |

## Self-review

**Spec coverage.** §1 → Task 7. §2 → Tasks 1–4. §3.1/3.2 → Task 2. §3.3 → **gap**: a derived fact
from a catch-all recording no `derived_from` is not given its own task; fold it into Task 2 Step 3
by applying `tier_of_row` to derivation rows as well, and add the assertion to Task 2's test.
§4.1 → Tasks 0, 4. §4.2 → Task 6. §4.3 → Task 4. §4.4 → Tasks 3, 7. §4.5 → Task 3. §4.6 → Task 1.
§5 → Tasks 4, 7, 9. §6 → Task 8. §7.1 → Tasks 9, 10. §7.2/§7.3/§7.4/§7.5 → deliberately unclosed,
carried in the spec. §8.2 → Task 5.

**Type consistency.** `Effect` is the StrEnum in `rules.py`; `Fired` is the runtime record, named
so it cannot be confused with it. `tier_of_row(when: dict)` takes the `when` mapping, not the row —
consistent in Tasks 3, 7 and 9. `PremiseOrigin` is the enum; `Why.premise_origin` serialises it as
`str`, which matches how `ValueSource` is already carried.

**Known gap, stated rather than hidden.** §7.3 — a role is not an interchangeable set, and
`implementation` decisions are validated against role membership rather than substitutability.
`index_building` is the live instance: two contracts, different produced types. Task 4 will accept
a rule that Task 5's router cannot route. That is carried deliberately because the shipped registry
has no `implementation` rule on `index_building`, but **a lab writing one gets an unroutable
pipeline and a confusing message**, and it should be the first task of whatever follows this plan.
