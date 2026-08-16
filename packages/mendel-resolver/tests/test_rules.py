import pathlib

import pytest
from comeni_core.declared.measurement import MeasurementRegistry
from comeni_core.declared.registry import Registry
from comeni_core.declared.vocabulary import Vocabulary
from mendel_resolver.goal import Goal
from mendel_resolver.premises import Premise, PremiseOrigin
from mendel_resolver.rules import RuleTable, RuleValidationError
from pydantic import ValidationError

_KIND_OF_DIR = {
    "contracts": "contract",
    "vocabularies": "vocabulary",
    "measurements": "measurement",
    "roles": "role",
    "rules": "rule",
}


def _declared(path, body: str) -> str:
    """Prepend what a fixture's file declares, derived from the directory it is written into.

    Since comeni-registry#1 a declared file says what it is and the loader no longer reads the
    directory. These fixtures still *write* into kind-named directories, which is now only a
    habit — and the habit is what tells this helper which line to add, so the fixtures keep
    their shape and their subject stays readable.

    Idempotent, because several fixtures write a file twice to check that something changed.
    """
    path = pathlib.Path(path)
    # Walk *ancestors*, not just the immediate parent: real layers nest, and
    # `tools/nf-core/fastqc/fastqc.contract.yml` sits two levels down from the directory that
    # names it.
    kind = next(
        (_KIND_OF_DIR[p.name] for p in path.parents if p.name in _KIND_OF_DIR), None
    )
    if kind is None or body.lstrip().startswith("declares:"):
        return body
    header = f"declares: {kind}\n"
    if kind in ("vocabulary", "measurement"):
        header += f"id: {path.name.removesuffix('.yml').removesuffix('.yaml')}\n"
    return header + body


def P(**facts) -> dict[str, Premise]:
    """A premise set, which is what `when` reads since Plan 1.15 Task 1."""
    return {
        key: Premise(id=key, value=value, origin=PremiseOrigin.MEASURED)
        for key, value in facts.items()
    }


CONTRACT = """
id: nf-core/subread/featurecounts@2.0.6
roles: [quantification]
nf_process: SUBREAD_FEATURECOUNTS
nf_include: modules/nf-core/subread/featurecounts/main
consumes: [{name: bam, type_id: alignment.bam, state_required: [coordinate_sorted]}]
produces: [{name: counts, type_id: counts.matrix, state: [gene_level]}]
params:
  - name: strandedness
    tier_hint: 3
    # featureCounts' `-s` takes 0, 1 or 2. Declaring that is what turns `MD0300` from a
    # character class over measurement names into a type check.
    domain: {kind: integer, minimum: 0, maximum: 2}
    via: ext
    key: args
    template: "--x {value}"
priority: 0
provenance: {source: hand, drafted_by: hand, approved_by: r, approved_at: "2026-08-03"}
"""

GOOD = """
version: 1
decisions:
  - decides: {effect: param, of: quantification, name: strandedness}
    because: "featureCounts -s follows library strandedness"
    cite: "Liao et al. 2014, doi:10.1093/bioinformatics/btt656"
    rows:
      - {when: {strandedness: reverse},    then: 2}
      - {when: {strandedness: forward},    then: 1}
      - {when: {strandedness: unstranded}, then: 0}
"""


@pytest.fixture
def world(tmp_path):
    vocab_dir = tmp_path / "vocabularies"
    vocab_dir.mkdir()
    (vocab_dir / "alignment.bam.yml").write_text(
        _declared(vocab_dir / "alignment.bam.yml", "states: [coordinate_sorted]\n")
    )
    (vocab_dir / "counts.matrix.yml").write_text(
        _declared(vocab_dir / "counts.matrix.yml", "states: [gene_level]\n")
    )
    contracts = tmp_path / "contracts"
    contracts.mkdir()
    (contracts / "fc.yml").write_text(_declared(contracts / "fc.yml", CONTRACT))
    measurements = tmp_path / "measurements"
    measurements.mkdir()
    (measurements / "strandedness.yml").write_text(
        _declared(
            measurements / "strandedness.yml",
            "kind: enum\nvalues: [forward, reverse, unstranded]\n")
    )
    (measurements / "read_length.yml").write_text(
        _declared(measurements / "read_length.yml", "kind: integer\nminimum: 1\n")
    )
    vocabulary = Vocabulary.load(tmp_path)
    return {
        "vocabulary": vocabulary,
        "registry": Registry.load(tmp_path, vocabulary),
        "measurements": MeasurementRegistry.load(tmp_path),
        "layer": tmp_path,
        "rules": tmp_path / "rules",
    }


def _rules(world, body):
    world["rules"].mkdir(exist_ok=True)
    (world["rules"] / "r.yml").write_text(_declared(world["rules"] / "r.yml", body))
    return RuleTable.load(
        world["layer"],
        registry=world["registry"],
        vocabulary=world["vocabulary"],
        measurements=world["measurements"],
    )


def test_a_matching_row_yields_its_value_and_provenance(world):
    table = _rules(world, GOOD)
    pin = table.value_for(["quantification"], "strandedness", P(strandedness="reverse"))
    assert pin.value == 2
    assert "Liao" in pin.decision.cite


def test_no_matching_row_falls_through(world):
    table = _rules(world, GOOD)
    assert table.value_for(["quantification"], "strandedness", {}) is None


def test_row_order_decides(world):
    table = _rules(world, """
version: 1
decisions:
  - decides: {effect: param, of: quantification, name: strandedness}
    because: "a fixture; MD0301 requires every row to justify something"
    rows:
      - {when: {strandedness: reverse}, then: 2}
      - {when: {strandedness: reverse}, then: 1}
      # The other two branches exist only to satisfy MD0311 — the point under test is that
      # the *first* matching row wins, which needs two rows that both match.
      - {when: {strandedness: forward}, then: 1}
      - {when: {strandedness: unstranded}, then: 0}
""")
    pin = table.value_for(["quantification"], "strandedness", P(strandedness="reverse"))
    assert pin.value == 2, "the first matching row wins, not the last"


def test_a_comparison_string_works(world):
    table = _rules(world, """
version: 1
decisions:
  - decides: {effect: param, of: quantification, name: strandedness}
    because: "a fixture; MD0301 requires every row to justify something"
    rows:
      - {when: {read_length: ">= 70", strandedness: reverse}, then: 2}
""")
    assert table.value_for(
        ["quantification"], "strandedness", P(read_length=150, strandedness="reverse")
    )
    assert (
        table.value_for(
            ["quantification"], "strandedness", P(read_length=50, strandedness="reverse")
        )
        is None
    )


def test_a_rule_for_a_parameter_no_contract_declares_will_not_load(world):
    """The bug this whole format exists to prevent: `subject: aligner` fired never.

    `MD0308` since Plan 1.15: the question is no longer "does any contract declare this
    parameter" but "does every contract that can fill this role declare it". The second is
    strictly stronger and is A123 — a value declared by one filler and not another is dead
    whenever the other wins, which is issue #10's deadness reached through the rule format.
    """
    with pytest.raises(RuleValidationError) as exc:
        _rules(world, """
version: 1
decisions:
  - decides: {effect: param, of: quantification, name: aligner}
    because: "a fixture; MD0301 requires every row to justify something"
    rows:
      - {when: {read_length: ">= 70"}, then: star}
""")
    message = str(exc.value)
    assert "MD0308" in message
    assert "aligner" in message
    assert "nf-core/subread/featurecounts@2.0.6" in message, (
        "the error must name the filler that would make the value dead"
    )


def test_a_rule_naming_an_undeclared_measurement_will_not_load(world):
    with pytest.raises(RuleValidationError, match="organism"):
        _rules(world, """
version: 1
decisions:
  - decides: {effect: param, of: quantification, name: strandedness}
    because: "a fixture; MD0301 requires every row to justify something"
    rows:
      - {when: {organism: human}, then: 2}
""")


def test_an_implementation_rule_must_name_a_contract_that_fills_the_role(world):
    """R20 — the shape a lab writing overlay rules meets first.

    The old message was *"nf-core/hisat2/align@2.2.2 is not in the registry"*, which is true
    and unhelpful: the author's mistake is about the *role*, and a contract that is present
    but fills something else got the same treatment as one that is absent. Naming the
    contracts that do fill it is what the author can act on.
    """
    with pytest.raises(RuleValidationError, match="does not fill role 'quantification'"):
        _rules(world, """
version: 1
decisions:
  - decides: {effect: implementation, of: quantification}
    because: "a fixture; MD0301 requires every row to justify something"
    rows:
      - {when: {read_length: "< 70"}, then: nf-core/hisat2/align@2.2.2}
""")


def test_an_implementation_rule_returns_the_pinned_contract(world):
    table = _rules(world, """
version: 1
decisions:
  - decides: {effect: implementation, of: quantification}
    because: "a fixture; MD0301 requires every row to justify something"
    rows:
      - {when: {read_length: ">= 70"}, then: nf-core/subread/featurecounts@2.0.6}
      # MD0311: `>= 70` alone leaves everything below it matching nothing.
      - {when: {read_length: "< 70"}, then: nf-core/subread/featurecounts@2.0.6}
""")
    pin = table.implementation_for("quantification", P(read_length=150))
    assert pin.value == "nf-core/subread/featurecounts@2.0.6"
    # The provenance travels with the value. Reading it was optional until A22, and the
    # one caller that had to remember did not.
    assert pin.from_layer is not None


def test_a_decision_on_a_role_nothing_fills_is_refused(world):
    """A119's other half, and the reason a role beats a type id as a key: the author is
    told the *job* has no worker, which is a sentence about their pipeline. The old format
    could only say `alignment.bam` had no producer, which is a sentence about a graph."""
    with pytest.raises(RuleValidationError, match="No contract in this stack fills role"):
        _rules(world, """
version: 1
decisions:
  - decides: {effect: implementation, of: alignment}
    because: "a fixture; MD0301 requires every row to justify something"
    rows:
      - {when: {read_length: ">= 70"}, then: nf-core/subread/featurecounts@2.0.6}
""")


def test_two_decisions_for_one_target_in_one_file_is_MD0309(world):
    """A119, which is what makes the key worth changing. Two decisions sharing a key do not
    both apply: `Policy.REPLACE` keeps one and drops the other, silently, at exit 0.

    Caught in `parse` rather than by `stack()` because the message can then name the file and
    the key, and because a file is the unit an author is looking at when they write the
    second one.
    """
    with pytest.raises(RuleValidationError, match="MD0309"):
        _rules(world, GOOD + """
  - decides: {effect: param, of: quantification, name: strandedness}
    because: "a fixture; MD0301 requires every row to justify something"
    rows:
      - {when: {strandedness: reverse}, then: 3}
""")


def test_two_files_in_one_layer_sharing_a_target_is_refused_by_stack(world):
    """A plain `ValueError` from `stack()`, not `RuleValidationError`.

    Duplicate keys across files inside one layer are refused by the one stacking mechanism,
    for every kind, with one message. Keeping a per-kind exception type here would mean the
    rule that invariant 8 rests on had one implementation per kind again — root B.

    So the two checks are not redundant: `MD0309` is per file and this is per layer, and
    neither can see the other's case.
    """
    world["rules"].mkdir(exist_ok=True)
    (world["rules"] / "second.yml").write_text(_declared(world["rules"] / "second.yml", GOOD))
    with pytest.raises(ValueError, match="is declared in .* and in .*, both under layer"):
        _rules(world, GOOD)


def test_a_comparison_on_an_enum_will_not_load(world):
    with pytest.raises(RuleValidationError, match="enum"):
        _rules(world, """
version: 1
decisions:
  - decides: {effect: param, of: quantification, name: strandedness}
    because: "a fixture; MD0301 requires every row to justify something"
    rows:
      - {when: {strandedness: ">= 70"}, then: 2}
""")


def test_only_a_param_effect_carries_a_name(world):
    """`{effect: implementation, of: X, name: Y}` is not a smaller version of anything — a
    name on an effect that decides the role itself has no meaning, and accepting it would
    change the key silently, which is `MD0309`'s whole subject."""
    with pytest.raises(RuleValidationError, match="MD0307"):
        _rules(world, """
version: 1
decisions:
  - decides: {effect: implementation, of: quantification, name: strandedness}
    because: "a fixture; MD0301 requires every row to justify something"
    rows:
      - {when: {strandedness: reverse}, then: nf-core/subread/featurecounts@2.0.6}
""")


def test_a_param_effect_without_a_name_is_refused(world):
    with pytest.raises(RuleValidationError, match="MD0307"):
        _rules(world, """
version: 1
decisions:
  - decides: {effect: param, of: quantification}
    because: "a fixture; MD0301 requires every row to justify something"
    rows:
      - {when: {strandedness: reverse}, then: 2}
""")


def test_a_presence_effect_says_present_or_absent_and_nothing_else(world):
    """`presence: absent` is English. `producer_of: fastq.reads` with `then: null` was the
    old way to spell it, and it reads as a null pointer rather than as a claim."""
    with pytest.raises(RuleValidationError, match="MD0307"):
        _rules(world, """
version: 1
decisions:
  - decides: {effect: presence, of: quantification}
    because: "a fixture; MD0301 requires every row to justify something"
    rows:
      - {when: {strandedness: reverse}, then: maybe}
""")


def test_a_higher_layer_replaces_a_whole_decision_block(world, tmp_path):
    """Whole-block replacement, not row merging: one block is the effective decision."""
    world["rules"].mkdir(exist_ok=True)
    (world["rules"] / "r.yml").write_text(_declared(world["rules"] / "r.yml", GOOD))
    overlay = tmp_path / "lab"
    (overlay / "rules").mkdir(parents=True)
    # A real layer carries a manifest, and since comeni-registry#1 that is also what marks it
    # as a layer of its own — without it the base layer, which is `tmp_path`, would glob this
    # overlay's files as though they were its own.
    (overlay / "registry.yml").write_text("name: lab\n")
    (overlay / "rules" / "r.yml").write_text(_declared(overlay / "rules" / "r.yml", """
version: 1
decisions:
  - decides: {effect: param, of: quantification, name: strandedness}
    because: "a fixture; MD0301 requires every row to justify something"
    rows:
      # Rotated so all three differ from the base block's 2/1/0. `forward` matching in both
      # would leave one third of the assertion unable to tell which block answered.
      - {when: {strandedness: reverse}, then: 0}
      - {when: {strandedness: forward}, then: 2}
      - {when: {strandedness: unstranded}, then: 1}
"""))
    table = RuleTable.load(
        [world["layer"], overlay],
        registry=world["registry"],
        vocabulary=world["vocabulary"],
        measurements=world["measurements"],
    )
    # Every value comes from the overlay's block, none from the base's. The original
    # discriminator was `forward` resolving to `None` — the base had a row for it and the
    # overlay did not — which stopped working when `MD0311` made the overlay cover the whole
    # enum. Distinct values are the better test anyway: they prove which block answered,
    # where an absence only proved that one row was gone.
    answers = {
        state: table.value_for(["quantification"], "strandedness", P(strandedness=state)).value
        for state in ("reverse", "forward", "unstranded")
    }
    assert answers == {"reverse": 0, "forward": 2, "unstranded": 1}


def test_goal_has_nowhere_to_put_a_sample_identifier():
    """Invariant 15. Not a rule the user must follow — an absence they cannot fill."""
    with pytest.raises(ValidationError):
        Goal(want=["counts.matrix"], samples=["patient_4471023_R1.fastq.gz"])


def test_profile_rejects_unknown_measurements(tmp_path):
    """Invariant 15, moved rather than weakened.

    `DataProfile` used to hold four hardcoded fields, so `extra="forbid"` alone refused
    `sample_name`. Measurements are declared data now, so the model cannot know what is
    declared and the mapping shorthand is no longer a validation boundary — which is why
    `MeasurementRegistry.profile()` is the only sanctioned constructor,
    `tests/test_construction.py` enforces that, and `mendel build` re-builds every goal's
    profile through it. This asserts the door itself is shut.
    """
    (m := tmp_path / "measurements").mkdir()
    (m / "read_length.yml").write_text(
        _declared(
            m / "read_length.yml",
            "kind: integer\nminimum: 1\n"))
    registry = MeasurementRegistry.load(tmp_path)
    with pytest.raises(KeyError, match="sample_name"):
        registry.profile({"read_length": 150, "sample_name": "SILVA_biopsy_01"})


def test_a_path_cannot_enter_through_constraints():
    """Invariant 15, at the door an audit walked straight through.

    `constraints` was `dict[str, Any]`, so a filesystem path validated, reached main.nf
    labelled tier 1 review `none`, and suppressed the tier-4 flag it replaced. The build
    reported "0 requiring review" while carrying a patient path.
    """
    with pytest.raises(ValidationError):
        Goal(constraints={"seq_platform": "/data/patients/PT-4471023/S1_R1.fastq.gz"})


ALIGNER = """
id: nf-core/star/align@1.11.0
roles: [alignment]
nf_process: STAR_ALIGN
nf_include: modules/nf-core/star/align/main
consumes: [{name: reads, type_id: fastq.reads, state_required: []}]
produces: [{name: bam, type_id: alignment.bam, state: []}]
params:
  - {name: star_ignore_sjdbgtf, tier_hint: 2, via: ext, key: args, template: "--x {value}"}
  # No `domain`, which is legal and is what most contracts say today. `_computed_over`
  # remains the fallback for these, and this param is what keeps that path tested.
  - {name: seq_platform, tier_hint: 4, via: ext, key: args, template: "--y {value}"}
priority: 0
provenance: {source: hand, drafted_by: hand, approved_by: r, approved_at: "2026-08-15"}
"""


@pytest.fixture
def two_roles(world):
    """A second contract, so a decision can land on two roles at once."""
    (world["layer"] / "vocabularies" / "fastq.reads.yml").write_text(
        _declared(world["layer"] / "vocabularies" / "fastq.reads.yml", "states: [trimmed]\n")
    )
    # An extensible enum, so `test_an_extensible_enum_still_needs_a_catch_all` has a domain
    # that can grow. The shipped `purpose` is declared the same way and for the same reason.
    (world["layer"] / "measurements" / "purpose.yml").write_text(
        _declared(
            world["layer"] / "measurements" / "purpose.yml",
            "kind: enum\nvalues: [expression, variant_calling, junction_discovery, "
        "transcript_assembly]\nextensible: true\n")
    )
    (world["layer"] / "contracts" / "star.yml").write_text(
        _declared(world["layer"] / "contracts" / "star.yml", ALIGNER)
    )
    world["measurements"] = MeasurementRegistry.load(world["layer"])
    world["vocabulary"] = Vocabulary.load(world["layer"])
    world["registry"] = Registry.load(world["layer"], world["vocabulary"])
    return world


TWO_TOOLS = """
version: 1
decisions:
  - decides:
      - {effect: param, of: quantification, name: strandedness}
      - {effect: param, of: alignment, name: star_ignore_sjdbgtf}
    because: "splice junctions can be supplied at index time or at align time"
    cite: "STAR manual 2.2.3"
    rows: [{when: {}, then: 0, cite: "STAR manual 2.2.3"}]
"""


def test_one_decision_lands_on_two_tools(two_roles):
    """§4.2. A decision that *reads* another decision would buy evaluation order, the
    possibility of a cycle, and the loss of the single pass. "Where the annotation is used"
    is one choice with two flags, so it is one block with two targets."""
    table = _rules(two_roles, TWO_TOOLS)
    fired = table.effects_for({})
    assert {f.key() for f in fired} == {
        "param:quantification:strandedness",
        "param:alignment:star_ignore_sjdbgtf",
    }
    assert {f.cite for f in fired} == {"STAR manual 2.2.3"}, "one choice, one citation"


def test_both_targets_of_one_decision_are_validated(two_roles):
    """Not just the first. A target list is where a validator that loops over `decides`
    incorrectly still passes every single-target test in this file."""
    with pytest.raises(RuleValidationError, match="MD0306"):
        _rules(two_roles, """
version: 1
decisions:
  - decides:
      - {effect: param, of: quantification, name: strandedness}
      - {effect: implementation, of: nothing_fills_this}
    because: "a fixture"
    rows: [{when: {}, then: 0, cite: "a"}]
""")


def test_two_decisions_cannot_both_land_on_one_target_across_files(two_roles):
    """The gap a composite stacking key opens, closed after assembly.

    A multi-target decision is one unit for replacement, so its `stack()` key is the whole
    set — which means a second decision naming only *one* of those targets is a different
    key, stacks happily beside it, and both fire on the same target. `MD0309`'s per-file
    check cannot see it and `stack()`'s per-layer check cannot see it either.
    """
    two_roles["rules"].mkdir(exist_ok=True)
    (two_roles["rules"] / "other.yml").write_text(_declared(two_roles["rules"] / "other.yml", """
version: 1
decisions:
  - decides: {effect: param, of: alignment, name: star_ignore_sjdbgtf}
    because: "a fixture"
    rows: [{when: {}, then: 1, cite: "a"}]
"""))
    with pytest.raises(RuleValidationError, match="MD0309"):
        _rules(two_roles, TWO_TOOLS)


# --- Task 9: exhaustiveness over a declared domain (A124) --------------------------------


def _decision(rows: str, *, target: str = "{effect: implementation, of: alignment}") -> str:
    return f"""
version: 1
decisions:
  - decides: {target}
    because: "a fixture; every row cites its own tool"
    rows:
{rows}
"""


STAR = "nf-core/star/align@1.11.0"
FC = "nf-core/subread/featurecounts@2.0.6"


def test_two_complementary_comparisons_are_exhaustive(two_roles):
    """The shipped aligner rule: `>= 70` and `< 70`, no catch-all.

    A124 asks for completeness, and the obvious fix — demand a catch-all — would demote Kim
    et al.'s branch from tier 3 to tier 2 and take its premise with it. A pair of comparisons
    at the same boundary is exhaustive *by construction*, with no bound declared anywhere.
    """
    table = _rules(two_roles, _decision(
        f'      - {{when: {{read_length: ">= 70"}}, then: {STAR}, cite: "Dobin 2013"}}\n'
        f'      - {{when: {{read_length: "< 70"}},  then: {STAR}, cite: "Kim 2019"}}'
    ))
    assert len(table.decisions) == 1


def test_a_gap_in_an_ordered_domain_is_refused(two_roles):
    with pytest.raises(RuleValidationError, match="between 50 and 70"):
        _rules(two_roles, _decision(
            f'      - {{when: {{read_length: ">= 70"}}, then: {STAR}, cite: "a"}}\n'
            f'      - {{when: {{read_length: "< 50"}},  then: {STAR}, cite: "b"}}'
        ))


def test_an_overlap_is_not_a_gap(two_roles):
    """`>= 50` and `< 70` overlap between 50 and 70. First-match-wins makes that legal and
    the rows still cover the line, so completeness has nothing to say about it — a check
    that refused this would be enforcing a different property under the same name."""
    table = _rules(two_roles, _decision(
        f'      - {{when: {{read_length: ">= 50"}}, then: {STAR}, cite: "a"}}\n'
        f'      - {{when: {{read_length: "< 70"}},  then: {STAR}, cite: "b"}}'
    ))
    assert len(table.decisions) == 1


def test_an_enum_is_exhaustive_when_the_rows_cover_its_values(two_roles):
    """`strandedness` has exactly three values and `extensible` is false, so three rows are
    the whole domain and no catch-all is needed."""
    table = _rules(two_roles, _decision(
        f'      - {{when: {{strandedness: forward}},    then: {FC}, cite: "a"}}\n'
        f'      - {{when: {{strandedness: reverse}},    then: {FC}, cite: "b"}}\n'
        f'      - {{when: {{strandedness: unstranded}}, then: {FC}, cite: "c"}}',
        target="{effect: implementation, of: quantification}",
    ))
    assert len(table.decisions) == 1


def test_an_enum_missing_a_value_is_refused(two_roles):
    with pytest.raises(RuleValidationError, match="unstranded"):
        _rules(two_roles, _decision(
            f'      - {{when: {{strandedness: forward}}, then: {FC}, cite: "a"}}\n'
            f'      - {{when: {{strandedness: reverse}}, then: {FC}, cite: "b"}}',
            target="{effect: implementation, of: quantification}",
        ))


def test_an_extensible_enum_still_needs_a_catch_all(two_roles):
    """An overlay may add a value, so coverage today is not coverage tomorrow. `purpose` is
    `extensible: true` for the same reason `organism` is — the list of things sequencing is
    for cannot be enumerated."""
    with pytest.raises(RuleValidationError, match="extensible"):
        _rules(two_roles, _decision(
            f'      - {{when: {{purpose: expression}},           then: {FC}, cite: "a"}}\n'
            f'      - {{when: {{purpose: variant_calling}},      then: {FC}, cite: "b"}}\n'
            f'      - {{when: {{purpose: junction_discovery}},   then: {FC}, cite: "c"}}\n'
            f'      - {{when: {{purpose: transcript_assembly}},  then: {FC}, cite: "d"}}',
            target="{effect: implementation, of: quantification}",
        ))


def test_a_catch_all_is_still_exhaustive(two_roles):
    """Still legal, just no longer *required*. That is the whole distinction A124's obvious
    fix would have lost."""
    table = _rules(two_roles, _decision(
        f'      - {{when: {{read_length: ">= 70"}}, then: {STAR}, cite: "a"}}\n'
        f'      - {{when: {{}},                     then: {STAR}, cite: "b"}}'
    ))
    assert len(table.decisions) == 1


def test_rows_over_several_premises_are_not_checked_for_completeness(two_roles):
    """Deliberately out of scope rather than approximated.

    Completeness over a *product* of domains is a different and much larger claim, and a
    check that half-computed it would refuse legitimate tables — which is worse than not
    checking, because the author cannot argue with it. Recorded here so the gap is a
    decision rather than an oversight.
    """
    table = _rules(two_roles, _decision(
        f'      - {{when: {{read_length: ">= 70", strandedness: reverse}}, then: {STAR}, '
        f'cite: "a"}}'
    ))
    assert len(table.decisions) == 1


# --- Task 10: a param declares its domain, and `then` is type-checked (A118) --------------


def test_a_then_outside_the_params_domain_is_refused(two_roles):
    """A118. `then: "read_length-1"` loaded, resolved at tier 3 with a real citation, and
    reached STAR as the literal string `read_length-1`.

    The only thing that ever refused it was `MD0201`, a shell-injection character class that
    permits `-`, and only on the spaced spelling. A declared domain turns the question from
    "does this look like arithmetic" into a type check.
    """
    with pytest.raises(RuleValidationError, match="accepts an integer"):
        _rules(two_roles, _decision(
            '      - {when: {}, then: "read_length-1", cite: "STAR manual 2.2.2"}',
            target="{effect: param, of: quantification, name: strandedness}",
        ))


def test_a_then_outside_a_declared_range_is_refused(two_roles):
    """The domain is a range as well as a kind. featureCounts' `-s` takes 0, 1 or 2, and a 3
    is not a smaller version of a valid flag — it is a flag the tool rejects at run time,
    after the pipeline has been built and gated."""
    with pytest.raises(RuleValidationError, match="maximum 2"):
        _rules(two_roles, _decision(
            '      - {when: {}, then: 3, cite: "a"}',
            target="{effect: param, of: quantification, name: strandedness}",
        ))


def test_a_then_inside_the_domain_still_loads(two_roles):
    table = _rules(two_roles, _decision(
        '      - {when: {}, then: 2, cite: "a"}',
        target="{effect: param, of: quantification, name: strandedness}",
    ))
    assert len(table.decisions) == 1


def test_a_legitimate_value_containing_a_measurement_name_still_loads(two_roles):
    """The negative that keeps the fallback honest.

    `paired` is a declared measurement, so a substring test would refuse `paired-end` — a
    legitimate value killed by a check nobody could disable. `seq_platform` declares no
    domain, so this exercises `_computed_over` rather than the type check.
    """
    table = _rules(two_roles, _decision(
        '      - {when: {}, then: "paired-end", cite: "a"}',
        target="{effect: param, of: alignment, name: seq_platform}",
    ))
    assert len(table.decisions) == 1


def test_a_computed_then_on_an_undeclared_param_is_still_refused(two_roles):
    """The fallback is kept rather than retired. Most contracts declare no domain today, and
    removing `_computed_over` would leave every one of them with no check at all — trading a
    heuristic for nothing, which is the wrong direction."""
    with pytest.raises(RuleValidationError, match="MD0300"):
        _rules(two_roles, _decision(
            '      - {when: {}, then: "read_length-1", cite: "a"}',
            target="{effect: param, of: alignment, name: seq_platform}",
        ))


SECOND_QUANTIFIER = """
id: comeni/htseq-count@2.0.5
roles: [quantification]
nf_process: HTSEQ_COUNT
nf_include: modules/comeni/htseq/count/main
consumes: [{name: bam, type_id: alignment.bam, state_required: [coordinate_sorted]}]
produces: [{name: counts, type_id: counts.matrix, state: [gene_level]}]
params:
  # The same parameter name, a different domain. htseq-count spells strandedness as words
  # where featureCounts spells it as 0/1/2 — a real disagreement between two tools, not a
  # contrived one.
  - name: strandedness
    tier_hint: 3
    # Quoted, because YAML 1.1 parses bare `yes` and `no` as booleans — which is htseq's
    # actual spelling and a real trap for a contract author.
    domain: {kind: enum, values: ["yes", "no", reverse]}
    via: ext
    key: args
    template: "--stranded {value}"
priority: 0
provenance: {source: hand, drafted_by: hand, approved_by: r, approved_at: "2026-08-15"}
"""


def test_two_implementations_disagreeing_about_a_domain_fall_back(two_roles):
    """Unanimity, not "take the first".

    `MD0308` has already proved every filler declares the parameter; two of them declaring
    *different* domains for it is a registry defect, and quietly taking the first would
    decide which contract is right by load order — invariant 10, in the one place where
    getting it wrong refuses a legitimate rule rather than merely reordering output.

    So the domains are dropped and `_computed_over` answers instead: it refuses less and
    invents nothing. Refusing the disagreement outright would be stronger and needs a code of
    its own; it is carried rather than smuggled in here.
    """
    (two_roles["layer"] / "contracts" / "htseq.yml").write_text(
        _declared(two_roles["layer"] / "contracts" / "htseq.yml", SECOND_QUANTIFIER)
    )
    two_roles["registry"] = Registry.load(two_roles["layer"], two_roles["vocabulary"])
    table = _rules(two_roles, _decision(
        '      - {when: {}, then: 2, cite: "legal for featureCounts, not for htseq-count"}',
        target="{effect: param, of: quantification, name: strandedness}",
    ))
    assert len(table.decisions) == 1


def test_narrowing_to_one_implementation_restores_its_domain(two_roles):
    """`when_implementation` is the author saying which tool the value is for, so the domain
    is that tool's again — and the check comes back with it."""
    (two_roles["layer"] / "contracts" / "htseq.yml").write_text(
        _declared(two_roles["layer"] / "contracts" / "htseq.yml", SECOND_QUANTIFIER)
    )
    two_roles["registry"] = Registry.load(two_roles["layer"], two_roles["vocabulary"])
    with pytest.raises(RuleValidationError, match="accepts yes, no, reverse"):
        _rules(two_roles, _decision(
            '      - {when: {}, then: 2, cite: "a"}',
            target=(
                "{effect: param, of: quantification, name: strandedness, "
                "when_implementation: [comeni/htseq-count@2.0.5]}"
            ),
        ))


def test_a_mapping_predicate_survives_the_model_as_well_as_the_evaluator(two_roles):
    """A121, the half Task 3 did not close.

    `predicates.matches` implements `not` and `in`, and `DecisionRow.when` was typed
    `dict[str, ParamValue]` — so a rule using either was refused by pydantic before the
    evaluator ever saw it. An evaluator handling a case the model cannot represent is the
    same defect as a model permitting one the evaluator ignores, and neither shows up until
    somebody writes the rule. The twenty-rule corpus is what wrote it.
    """
    table = _rules(two_roles, _decision(
        '      - {when: {strandedness: {not: unstranded}}, then: 2, cite: "a"}\n'
        '      - {when: {}, then: 0, cite: "b"}',
        target="{effect: param, of: quantification, name: strandedness}",
    ))
    answered = {
        state: table.value_for(["quantification"], "strandedness", P(strandedness=state)).value
        for state in ("reverse", "unstranded")
    }
    assert answered == {"reverse": 2, "unstranded": 0}
