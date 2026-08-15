import pytest
from comeni_core.measurement import MeasurementRegistry
from comeni_core.registry import Registry
from comeni_core.vocabulary import Vocabulary
from mendel_resolver.goal import Goal
from mendel_resolver.premises import Premise, PremiseOrigin
from mendel_resolver.rules import RuleTable, RuleValidationError
from pydantic import ValidationError


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
params: [{name: strandedness, tier_hint: 3, via: ext, key: args, template: "--x {value}"}]
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
    (vocab_dir / "alignment.bam.yml").write_text("states: [coordinate_sorted]\n")
    (vocab_dir / "counts.matrix.yml").write_text("states: [gene_level]\n")
    contracts = tmp_path / "contracts"
    contracts.mkdir()
    (contracts / "fc.yml").write_text(CONTRACT)
    measurements = tmp_path / "measurements"
    measurements.mkdir()
    (measurements / "strandedness.yml").write_text(
        "kind: enum\nvalues: [forward, reverse, unstranded]\n"
    )
    (measurements / "read_length.yml").write_text("kind: integer\nminimum: 1\n")
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
    (world["rules"] / "r.yml").write_text(body)
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
      - {when: {strandedness: reverse}, then: 99}
      - {when: {strandedness: reverse}, then: 2}
""")
    pin = table.value_for(["quantification"], "strandedness", P(strandedness="reverse"))
    assert pin.value == 99


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
    (world["rules"] / "second.yml").write_text(GOOD)
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
    (world["rules"] / "r.yml").write_text(GOOD)
    overlay = tmp_path / "lab"
    (overlay / "rules").mkdir(parents=True)
    (overlay / "rules" / "r.yml").write_text("""
version: 1
decisions:
  - decides: {effect: param, of: quantification, name: strandedness}
    because: "a fixture; MD0301 requires every row to justify something"
    rows:
      - {when: {strandedness: reverse}, then: 0}
""")
    table = RuleTable.load(
        [world["layer"], overlay],
        registry=world["registry"],
        vocabulary=world["vocabulary"],
        measurements=world["measurements"],
    )
    assert table.value_for(["quantification"], "strandedness", P(strandedness="reverse")).value == 0
    assert table.value_for(["quantification"], "strandedness", P(strandedness="forward")) is None


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
    (m / "read_length.yml").write_text("kind: integer\nminimum: 1\n")
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
