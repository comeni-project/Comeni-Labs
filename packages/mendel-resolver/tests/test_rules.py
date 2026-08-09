import pytest
from comeni_core.measurement import MeasurementRegistry
from comeni_core.registry import Registry
from comeni_core.vocabulary import Vocabulary
from mendel_resolver.goal import DataProfile, Goal
from mendel_resolver.rules import RuleTable, RuleValidationError
from pydantic import ValidationError

CONTRACT = """
id: nf-core/subread/featurecounts@2.0.6
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
  - decides: {param: strandedness}
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
    pin = table.value_for("strandedness", DataProfile(strandedness="reverse"))
    assert pin.value == 2
    assert "Liao" in pin.decision.cite


def test_no_matching_row_falls_through(world):
    table = _rules(world, GOOD)
    assert table.value_for("strandedness", DataProfile()) is None


def test_row_order_decides(world):
    table = _rules(world, """
version: 1
decisions:
  - decides: {param: strandedness}
    rows:
      - {when: {strandedness: reverse}, then: 99}
      - {when: {strandedness: reverse}, then: 2}
""")
    assert table.value_for("strandedness", DataProfile(strandedness="reverse")).value == 99


def test_a_comparison_string_works(world):
    table = _rules(world, """
version: 1
decisions:
  - decides: {param: strandedness}
    rows:
      - {when: {read_length: ">= 70", strandedness: reverse}, then: 2}
""")
    assert table.value_for("strandedness", DataProfile(read_length=150, strandedness="reverse"))
    assert (
        table.value_for("strandedness", DataProfile(read_length=50, strandedness="reverse"))
        is None
    )


def test_a_rule_for_a_parameter_no_contract_declares_will_not_load(world):
    """The bug this whole format exists to prevent: `subject: aligner` fired never."""
    with pytest.raises(RuleValidationError) as exc:
        _rules(world, """
version: 1
decisions:
  - decides: {param: aligner}
    rows:
      - {when: {read_length: ">= 70"}, then: star}
""")
    message = str(exc.value)
    assert "aligner" in message
    assert "strandedness" in message, "the error must say what the author *can* write"


def test_a_rule_naming_an_undeclared_measurement_will_not_load(world):
    with pytest.raises(RuleValidationError, match="organism"):
        _rules(world, """
version: 1
decisions:
  - decides: {param: strandedness}
    rows:
      - {when: {organism: human}, then: 2}
""")


def test_a_producer_rule_must_name_a_contract_that_exists(world):
    with pytest.raises(RuleValidationError, match="hisat2"):
        _rules(world, """
version: 1
decisions:
  - decides: {producer_of: counts.matrix}
    rows:
      - {when: {read_length: "< 70"}, then: nf-core/hisat2/align@2.2.2}
""")


def test_a_producer_rule_returns_the_pinned_contract(world):
    table = _rules(world, """
version: 1
decisions:
  - decides: {producer_of: counts.matrix}
    rows:
      - {when: {read_length: ">= 70"}, then: nf-core/subread/featurecounts@2.0.6}
""")
    pin = table.producer_for("counts.matrix", DataProfile(read_length=150))
    assert pin.value == "nf-core/subread/featurecounts@2.0.6"
    # The provenance travels with the value. Reading it was optional until A22, and the
    # one caller that had to remember did not.
    assert pin.from_layer is not None


def test_a_producer_rule_naming_a_contract_that_produces_something_else(world):
    with pytest.raises(RuleValidationError, match="does not produce"):
        _rules(world, """
version: 1
decisions:
  - decides: {producer_of: alignment.bam}
    rows:
      - {when: {read_length: ">= 70"}, then: nf-core/subread/featurecounts@2.0.6}
""")


def test_two_decisions_for_one_target_in_one_layer_is_an_error(world):
    """A plain `ValueError` from `stack()`, not `RuleValidationError`.

    Duplicate keys inside one layer are refused by the one stacking mechanism, for all four
    kinds, with one message. Keeping a per-kind exception type here would mean the rule that
    invariant 8 rests on had four implementations again — which is what root B is about.
    """
    with pytest.raises(ValueError, match="declared twice"):
        _rules(world, GOOD + """
  - decides: {param: strandedness}
    rows:
      - {when: {strandedness: reverse}, then: 3}
""")


def test_a_comparison_on_an_enum_will_not_load(world):
    with pytest.raises(RuleValidationError, match="enum"):
        _rules(world, """
version: 1
decisions:
  - decides: {param: strandedness}
    rows:
      - {when: {strandedness: ">= 70"}, then: 2}
""")


def test_a_decision_must_decide_exactly_one_thing(world):
    with pytest.raises(RuleValidationError, match="exactly one"):
        _rules(world, """
version: 1
decisions:
  - decides: {param: strandedness, producer_of: counts.matrix}
    rows:
      - {when: {strandedness: reverse}, then: 2}
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
  - decides: {param: strandedness}
    rows:
      - {when: {strandedness: reverse}, then: 0}
""")
    table = RuleTable.load(
        [world["layer"], overlay],
        registry=world["registry"],
        vocabulary=world["vocabulary"],
        measurements=world["measurements"],
    )
    assert table.value_for("strandedness", DataProfile(strandedness="reverse")).value == 0
    assert table.value_for("strandedness", DataProfile(strandedness="forward")) is None


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
