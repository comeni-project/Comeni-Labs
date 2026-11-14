"""Rule parsing, stacking, validation, matching, provenance, and domain contracts."""

import pathlib

import pytest
from comeni_core.declared.measurement import MeasurementRegistry
from comeni_core.declared.registry import Registry
from comeni_core.declared.vocabulary import Vocabulary
from mendel_resolver.goal import Goal
from mendel_resolver.premises import Premise, PremiseOrigin
from mendel_resolver.rules import RuleTable, RuleValidationError, _comparison
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
    """Build the premise mapping consumed by ``when`` predicates."""
    return {
        key: Premise(id=key, value=value, origin=PremiseOrigin.MEASURED)
        for key, value in facts.items()
    }


CONTRACT = """
id: nf-core/subread/featurecounts@2.1.1
roles: [quantification]
nf_process: SUBREAD_FEATURECOUNTS
nf_include: modules/nf-core/subread/featurecounts/main
consumes: [{name: bam, type_id: alignment.bam::coordinate_sorted}]
produces: [{name: counts, type_id: counts.matrix::gene_level}]
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
      # Overlapping, not repeated: a repeated row is dead and refused (MD0323, #461). The point
      # under test is that where two rows match, the *first* wins.
      - {when: {read_length: ">= 100"}, then: 2}
      - {when: {read_length: ">= 50"}, then: 1}
      - {when: {read_length: "< 50"}, then: 0}
""")
    pin = table.value_for(["quantification"], "strandedness", P(read_length=150))
    assert pin.value == 2, "the first matching row wins, not the last"
    assert table.value_for(["quantification"], "strandedness", P(read_length=75)).value == 1


def test_a_comparison_string_works(world):
    table = _rules(world, """
version: 1
decisions:
  - decides: {effect: param, of: quantification, name: strandedness}
    because: "a fixture; MD0301 requires every row to justify something"
    rows:
      - {when: {read_length: ">= 70", strandedness: reverse}, then: 2}
      # The rest of the cases, so the table is complete (MD0311 over several facts, #461).
      - {when: {read_length: "< 70"}, then: 0}
      - {when: {strandedness: {not: reverse}}, then: 0}
""")
    assert table.value_for(
        ["quantification"], "strandedness", P(read_length=150, strandedness="reverse")
    ).value == 2
    assert (
        table.value_for(
            ["quantification"], "strandedness", P(read_length=50, strandedness="reverse")
        ).value == 0
    )


def test_a_comparison_with_a_non_numeric_operand_is_refused():
    with pytest.raises(RuleValidationError, match="not a number"):
        _comparison(">= many")


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
    assert "nf-core/subread/featurecounts@2.1.1" in message, (
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
      - {when: {read_length: ">= 70"}, then: nf-core/subread/featurecounts@2.1.1}
      # MD0311: `>= 70` alone leaves everything below it matching nothing.
      - {when: {read_length: "< 70"}, then: nf-core/subread/featurecounts@2.1.1}
""")
    pin = table.implementation_for("quantification", P(read_length=150))
    assert pin.value == "nf-core/subread/featurecounts@2.1.1"
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
      - {when: {read_length: ">= 70"}, then: nf-core/subread/featurecounts@2.1.1}
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
      - {when: {strandedness: reverse}, then: nf-core/subread/featurecounts@2.1.1}
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
id: nf-core/star/align@2.7.11b
roles: [alignment]
nf_process: STAR_ALIGN
nf_include: modules/nf-core/star/align/main
consumes: [{name: reads, type_id: fastq.reads}]
produces: [{name: bam, type_id: alignment.bam}]
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


# Exhaustiveness over a declared domain.


def _decision(rows: str, *, target: str = "{effect: implementation, of: alignment}") -> str:
    return f"""
version: 1
decisions:
  - decides: {target}
    because: "a fixture; every row cites its own tool"
    rows:
{rows}
"""


STAR = "nf-core/star/align@2.7.11b"
FC = "nf-core/subread/featurecounts@2.1.1"


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


def test_rows_over_several_premises_are_checked_for_completeness(two_roles):
    """#461 reverses the earlier decision to leave this out. The check is exact, not an
    approximation: comparisons only cut an ordered fact at their literals, so one point in each
    interval and at each literal tries every case, and an enum's values are finite."""
    with pytest.raises(RuleValidationError, match="MD0311"):
        _rules(two_roles, _decision(
            f'      - {{when: {{read_length: ">= 70", strandedness: reverse}}, then: {STAR}, '
            f'cite: "a"}}'
        ))


# Parameter domains and type-checking of ``then`` values.


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
consumes: [{name: bam, type_id: alignment.bam::coordinate_sorted}]
produces: [{name: counts, type_id: counts.matrix::gene_level}]
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


# ── a setting from a fact (#461) ──────────────────────────────────────────────────────────

FROM_FACT = """
version: 1
derives:
  - {fact: s_level, kind: integer, source: read_length, transform: [{op: at_most, by: 2}],
     cite: "a fixture"}
decisions:
  - decides: {effect: param, of: quantification, name: strandedness}
    rows:
      - {when: {}, then: {fact: s_level}, cite: "a fixture"}
"""


def test_a_setting_takes_its_value_from_a_fact(world):
    table = _rules(world, FROM_FACT)
    pin = table.value_for(["quantification"], "strandedness", P(s_level=2))
    assert pin is not None and pin.value == 2
    assert "s_level" in [record.id for record in pin.premise]


def test_a_fact_reference_with_no_value_does_not_fire(world):
    """Review focus 1: never `null` reaching the tool; the decision falls through."""
    table = _rules(world, FROM_FACT)
    assert table.value_for(["quantification"], "strandedness", P(read_length=150)) is None


def test_a_fact_reference_must_fit_the_domain(world):
    """Review focus 2: a number into an integer setting, a fact nobody declares, and a fact
    choosing a tool are all refused at load."""
    (world["layer"] / "measurements" / "gc.yml").write_text(
        _declared(world["layer"] / "measurements" / "gc.yml", "kind: number\n"))
    world["measurements"] = MeasurementRegistry.load(world["layer"])
    as_number = FROM_FACT.replace("then: {fact: s_level}", "then: {fact: gc}")
    with pytest.raises(RuleValidationError, match="MD0300"):
        _rules(world, as_number)
    unknown = FROM_FACT.replace("then: {fact: s_level}", "then: {fact: nowhere}")
    with pytest.raises(RuleValidationError, match="(?s)MD0310.*nowhere"):
        _rules(world, unknown)
    choosing = """
version: 1
decisions:
  - decides: {effect: implementation, of: quantification}
    rows:
      - {when: {}, then: {fact: read_length}, cite: "a fixture"}
"""
    with pytest.raises((RuleValidationError, ValueError), match="(?s)MD0300.*fact"):
        _rules(world, choosing)


def test_a_derived_fact_must_fit_the_domain_too(world):
    """A `number` derivation into an integer setting, refused once derivations are known."""
    as_number = FROM_FACT.replace("{fact: s_level, kind: integer,", "{fact: s_level, kind: number,")
    with pytest.raises(RuleValidationError, match="(?s)MD0300.*s_level"):
        _rules(world, as_number)


# ── hit policy (#461) ──────────────────────────────────────────────────────────────────────

UNIQUE = """
version: 1
decisions:
  - decides: {effect: param, of: quantification, name: strandedness}
    hit: unique
    cite: "a fixture"
    rows:
      - {when: {read_length: ">= 100"}, then: 1}
      - {when: {strandedness: reverse}, then: 2}
      - {when: {read_length: "< 100", strandedness: {not: reverse}}, then: 0}
"""


def test_first_is_the_default_and_is_not_written():
    """The registry's rule files say nothing of a hit policy and read as they did."""
    from mendel_resolver import layers
    from support.paths import REGISTRY

    decisions = layers.load(REGISTRY).rules.decisions
    assert decisions, "the registry declares no decision: this measures nothing"
    for decision in decisions:
        assert decision.hit == "first"
        assert "hit" not in decision.model_dump()


def test_unique_with_two_matching_rows_is_a_tie(world):
    table = _rules(world, UNIQUE)
    both = P(read_length=150, strandedness="reverse")
    assert table.value_for(["quantification"], "strandedness", both) is None
    assert [p.value for p in table.ties_for(["quantification"], "strandedness", both)] == [1, 2]
    one = P(read_length=150, strandedness="forward")
    assert table.value_for(["quantification"], "strandedness", one).value == 1
    assert table.ties_for(["quantification"], "strandedness", one) == []


def test_unique_with_two_matching_rows_is_a_tier_4_question(world):
    """Review focus 4: a tie is asked, with both values, never settled by row order."""
    from comeni_core.plan.decision import ParamDecision
    from mendel_resolver.goal import GoalInput
    from mendel_resolver.resolve import resolve

    table = _rules(world, UNIQUE)
    goal = Goal(have=[GoalInput(type_id="alignment.bam", states={"coordinate_sorted"})],
                want=["counts.matrix"],
                profile=world["measurements"].profile({"read_length": 150,
                                                       "strandedness": "reverse"}))
    ir = resolve(goal, world["registry"], table, world["measurements"],
                 vocabulary=world["vocabulary"])
    asked = [d for d in ir.decisions if isinstance(d, ParamDecision)
             and d.subject == "strandedness"]
    assert asked and sorted(asked[0].candidates) == [1, 2]


def test_a_fact_read_twice_is_recorded_once(world):
    """Task 1 review: a row testing and taking the same fact listed it twice in pipeline.yml."""
    body = FROM_FACT.replace("{when: {}, then: {fact: s_level}",
                             "{when: {s_level: present}, then: {fact: s_level}")
    pin = _rules(world, body).value_for(["quantification"], "strandedness", P(s_level=2))
    assert [record.id for record in pin.premise] == ["s_level"]


def test_unique_is_for_settings_only(world):
    """Task 2 review: a tie between tools fell through to registry priority with no question.
    Until a tie can be asked there, `unique` decides a setting and nothing else."""
    body = """
version: 1
decisions:
  - decides: {effect: presence, of: quantification}
    hit: unique
    cite: "a fixture"
    rows:
      - {when: {read_length: ">= 100"}, then: present}
      - {when: {read_length: "< 100"}, then: absent}
"""
    with pytest.raises(RuleValidationError, match="(?s)MD0300.*unique"):
        _rules(world, body)


def test_a_tie_shows_in_the_preview_as_a_question(world):
    """Task 2 review: the forge preview showed a tie as no effect at all."""
    from comeni_core.plan.tiers import Tier

    table = _rules(world, UNIQUE)
    [fired] = table.effects_for(P(read_length=150, strandedness="reverse"))
    assert fired.value is None and fired.tier is Tier.AMBIGUOUS
    assert "both match" in fired.because


def test_an_answer_outside_a_tie_is_not_taken(world):
    """Task 2 review: the tied values are a closed set; an answer outside it is demoted."""
    from comeni_core.plan.decision import ParamDecision
    from mendel_resolver.goal import GoalInput
    from mendel_resolver.ports import Resolution
    from mendel_resolver.resolve import resolve

    class Answers3:
        def resolve(self, ambiguity):
            return Resolution(value=3, how="model", by="test", why="made up", confidence=1.0)

    table = _rules(world, UNIQUE)
    goal = Goal(have=[GoalInput(type_id="alignment.bam", states={"coordinate_sorted"})],
                want=["counts.matrix"],
                profile=world["measurements"].profile({"read_length": 150,
                                                       "strandedness": "reverse"}))
    ir = resolve(goal, world["registry"], table, world["measurements"],
                 vocabulary=world["vocabulary"], resolver=Answers3())
    [asked] = [d for d in ir.decisions if isinstance(d, ParamDecision)
               and d.subject == "strandedness"]
    assert asked.chosen is None


# ── table checks over several facts (#461) ────────────────────────────────────────────────


def _paired(world):
    (world["layer"] / "measurements" / "paired.yml").write_text(
        _declared(world["layer"] / "measurements" / "paired.yml", "kind: boolean\n"))
    world["measurements"] = MeasurementRegistry.load(world["layer"])
    return world


def _table(rows: str, hit: str = "first") -> str:
    return ("version: 1\ndecisions:\n"
            "  - decides: {effect: param, of: quantification, name: strandedness}\n"
            f"    hit: {hit}\n    cite: \"a fixture\"\n    rows:\n{rows}")


def test_a_two_fact_table_with_a_gap_is_refused(world):
    rows = ('      - {when: {read_length: ">= 100", paired: true}, then: 0}\n'
            '      - {when: {read_length: "< 100", paired: true}, then: 1}\n'
            '      - {when: {read_length: ">= 100", paired: false}, then: 2}\n')
    with pytest.raises(RuleValidationError, match="(?s)MD0311.*paired.*False"):
        _rules(_paired(world), _table(rows))


def test_a_two_fact_table_that_covers_every_case_loads(world):
    rows = ('      - {when: {read_length: ">= 100", paired: true}, then: 0}\n'
            '      - {when: {read_length: "< 100"}, then: 1}\n'
            '      - {when: {paired: false}, then: 2}\n')
    assert len(_rules(_paired(world), _table(rows)).decisions) == 1


def test_overlapping_rows_under_unique_are_legal_and_asked(world):
    """An overlap under `unique` is the case a person decides; under `first` row order would."""
    rows = ('      - {when: {read_length: ">= 100"}, then: 1}\n'
            '      - {when: {read_length: ">= 50"}, then: 2}\n'
            '      - {when: {read_length: "< 50"}, then: 0}\n')
    assert len(_rules(world, _table(rows, "unique")).decisions) == 1


def test_a_row_no_case_reaches_first_is_dead(world):
    rows = ('      - {when: {read_length: ">= 50"}, then: 1}\n'
            '      - {when: {read_length: ">= 100"}, then: 2}\n'
            '      - {when: {read_length: "< 50"}, then: 0}\n')
    with pytest.raises(RuleValidationError, match="(?s)MD0323.*row 2"):
        _rules(world, _table(rows))


def test_an_extensible_enum_over_several_facts_still_needs_a_catch_all(world):
    """Review focus 5: an overlay may add a value, so covering today's values is not enough."""
    (world["layer"] / "measurements" / "strandedness.yml").write_text(_declared(
        world["layer"] / "measurements" / "strandedness.yml",
        "kind: enum\nvalues: [forward, reverse, unstranded]\nextensible: true\n"))
    world["measurements"] = MeasurementRegistry.load(world["layer"])
    rows = "".join(f"      - {{when: {{strandedness: {v}, read_length: \">= 1\"}}, then: 0}}\n"
                   for v in ("forward", "reverse", "unstranded"))
    rows += '      - {when: {read_length: "< 1"}, then: 1}\n'
    with pytest.raises(RuleValidationError, match="(?s)MD0311.*overlay adds"):
        _rules(world, _table(rows))


def test_too_many_cases_is_refused(world):
    """700 boundaries two apart on read_length (1401 points) times three strandedness values:
    past the 4096 bound, refused before any case is tried."""
    rows = "".join(f'      - {{when: {{read_length: "== {n}", strandedness: reverse}}, then: 0}}\n'
                   for n in range(1, 1401, 2))
    rows += '      - {when: {}, then: 1}\n'
    with pytest.raises(RuleValidationError, match="MD0324"):
        _rules(world, _table(rows))


# ── a rule's value against the tool's constraints (#461, #460) ───────────────────────────

MODAL = """
id: lab/modal@1.0.0
roles: [quantification]
nf_process: MODAL
nf_include: modules/lab/modal/main
consumes: [{name: bam, type_id: alignment.bam::coordinate_sorted}]
produces: [{name: counts, type_id: counts.matrix::gene_level}]
params:
  - name: mode
    via: ext
    key: args
    template: "--mode {value}"
    domain: {kind: enum, values: [fast, careful]}
    default: careful
    because: "the tool's default"
constraints:
  - {when: {param.mode: fast}, forbids: [bam],
     because: "fast mode reads unsorted input only"}
provenance: {source: hand, drafted_by: hand, approved_by: r, approved_at: "2026-11-10"}
"""


def test_a_rule_value_the_tool_forbids_is_refused(world):
    contracts = world["layer"] / "contracts"
    (contracts / "modal.yml").write_text(_declared(contracts / "modal.yml", MODAL))
    world["registry"] = Registry.load(world["layer"], world["vocabulary"])
    body = """
version: 1
decisions:
  - decides: {effect: param, of: quantification, name: mode,
              when_implementation: [lab/modal@1.0.0]}
    rows:
      - {when: {}, then: fast, cite: "a fixture"}
"""
    with pytest.raises(RuleValidationError, match="(?s)MD0325.*fast mode reads unsorted"):
        _rules(world, body)
    careful = body.replace("then: fast", "then: careful")
    assert len(_rules(world, careful).decisions) == 1


def test_a_rule_value_is_checked_with_the_other_settings_defaults(world):
    """Task 4 review: other settings counted as unset, so a row testing one as `absent`
    matched at load although its default means the build never meets it."""
    contracts = world["layer"] / "contracts"
    modal = MODAL.replace(
        '''  - {when: {param.mode: fast}, forbids: [bam],''',
        '''  - {when: {param.mode: fast, param.index: absent}, forbids: [bam],''').replace(
        "constraints:", "  - {name: index, via: ext, key: args, template: '--index {value}',\n"
                        "     default: auto, because: the tool's default}\nconstraints:")
    assert modal != MODAL
    (contracts / "modal.yml").write_text(_declared(contracts / "modal.yml", modal))
    world["registry"] = Registry.load(world["layer"], world["vocabulary"])
    body = """
version: 1
decisions:
  - decides: {effect: param, of: quantification, name: mode,
              when_implementation: [lab/modal@1.0.0]}
    rows:
      - {when: {}, then: fast, cite: "a fixture"}
"""
    assert len(_rules(world, body).decisions) == 1


# ── Task 3 review: the table check's cases are exact ──────────────────────────────────────


def _check(world, rows: list[dict], hit: str = "first") -> list[str]:
    from mendel_resolver.rules.format import Decision
    from mendel_resolver.rules.validate import check_table

    decision = Decision.model_validate({
        "decides": {"effect": "param", "of": "quantification", "name": "strandedness"},
        "hit": hit, "cite": "a fixture", "rows": rows})
    return [f.split(":")[0] for f in check_table(
        decision, measurements=world["measurements"], derived={})]


def test_no_integer_lies_between_two_adjacent_cuts(world):
    rows = [{"when": {"read_length": "<= 1", "paired": True}, "then": 0},
            {"when": {"read_length": ">= 2", "paired": True}, "then": 1},
            {"when": {"paired": False}, "then": 2}]
    assert _check(_paired(world), rows) == []


def test_membership_and_negation_cut_an_ordered_fact(world):
    world = _paired(world)
    reached = [{"when": {"read_length": {"in": [50]}, "paired": True}, "then": 0},
               {"when": {"read_length": {"not": 50}, "paired": True}, "then": 1},
               {"when": {"paired": False}, "then": 2}]
    assert _check(world, reached) == []
    missing = [{"when": {"read_length": {"not": 50}, "paired": True}, "then": 1},
               {"when": {"paired": False}, "then": 2}]
    assert _check(world, missing) == ["MD0311"]


def test_a_catch_all_after_a_complete_table_is_not_dead(world):
    """It decides when the fact is not known, which a profile may well be."""
    rows = [{"when": {"read_length": ">= 70"}, "then": 0},
            {"when": {"read_length": "< 70"}, "then": 1},
            {"when": {}, "then": 2}]
    assert _check(world, rows) == []


def test_an_overlay_value_meets_negation_and_presence(world):
    (world["layer"] / "measurements" / "strandedness.yml").write_text(_declared(
        world["layer"] / "measurements" / "strandedness.yml",
        "kind: enum\nvalues: [forward, reverse, unstranded]\nextensible: true\n"))
    world["measurements"] = MeasurementRegistry.load(world["layer"])
    world = _paired(world)
    rows = [{"when": {"strandedness": "reverse", "paired": True}, "then": 0},
            {"when": {"strandedness": {"not": "reverse"}, "paired": True}, "then": 1},
            {"when": {"paired": False}, "then": 2}]
    assert _check(world, rows) == []


def test_a_fractional_boundary_on_an_integer_fact_is_refused(world):
    """Final review: `>= 69.5` on read_length crashed the check (69 compared with "69.5");
    no integer lies at 69.5, so the boundary is a typo for 69 or 70."""
    rows = ('      - {when: {read_length: ">= 69.5"}, then: 0}\n'
            '      - {when: {read_length: "< 69.5"}, then: 1}\n')
    with pytest.raises(RuleValidationError, match="(?s)MD0310.*69.5"):
        _rules(world, _table(rows))


# ── coverage: a decision may require all of the data (#465) ─────────────────────────────


def _coverage_table(coverage: str | None) -> str:
    said = f"    coverage: {coverage}\n" if coverage else ""
    return ("version: 1\ndecisions:\n"
            "  - decides: {effect: param, of: quantification, name: strandedness}\n"
            f"{said}    cite: \"a fixture\"\n    rows:\n"
            '      - {when: {read_length: ">= 70"}, then: 2}\n'
            '      - {when: {read_length: "< 70"}, then: 1}\n')


def _read(value, coverage: str | None, origin=PremiseOrigin.MEASURED) -> dict[str, Premise]:
    return {"read_length": Premise(id="read_length", value=value, origin=origin,
                                   coverage=coverage)}


def test_a_head_premise_does_not_satisfy_coverage_all(world):
    table = _rules(world, _coverage_table("all"))
    assert table.value_for(["quantification"], "strandedness", _read(150, "head")) is None


def test_a_premise_read_in_full_satisfies_coverage_all(world):
    table = _rules(world, _coverage_table("all"))
    pin = table.value_for(["quantification"], "strandedness", _read(150, "all"))
    assert pin is not None and pin.value == 2
    assert pin.premise[0].coverage == "all"


def test_an_asserted_premise_satisfies_coverage_all(world):
    """A person's word is not an estimate of the data: it is what they say the data is."""
    table = _rules(world, _coverage_table("all"))
    pin = table.value_for(["quantification"], "strandedness",
                          _read(150, None, PremiseOrigin.ASSERTED))
    assert pin is not None and pin.value == 2


def test_without_coverage_a_head_premise_decides(world):
    table = _rules(world, _coverage_table(None))
    pin = table.value_for(["quantification"], "strandedness", _read(150, "head"))
    assert pin is not None and pin.premise[0].coverage == "head"


def test_coverage_is_left_out_of_the_dump_when_unset(world):
    decision = _rules(world, _coverage_table(None)).decisions[0]
    assert "coverage" not in decision.model_dump()
    assert _rules(world, _coverage_table("all")).decisions[0].model_dump()["coverage"] == "all"


def test_effects_respect_coverage_all(world):
    table = _rules(world, _coverage_table("all"))
    assert table.effects_for(_read(150, "head")) == []


def test_an_implementation_rule_needing_all_the_data_misses_on_an_estimate(world):
    """Task 4 review: the miss is asked of the person, never settled by priority (#174)."""
    table = _rules(world, """
version: 1
decisions:
  - decides: {effect: implementation, of: quantification}
    coverage: all
    because: "a fixture"
    rows:
      - {when: {read_length: ">= 70"}, then: nf-core/subread/featurecounts@2.1.1}
      - {when: {read_length: "< 70"}, then: nf-core/subread/featurecounts@2.1.1}
""")
    head = _read(150, "head")
    assert table.implementation_for("quantification", head) is None
    missed = table.unapplied_implementation(["quantification"], head)
    assert missed is not None and missed[1] == ["read_length"]
    assert table.unapplied_implementation(["quantification"], _read(150, "all")) is None


# ── deferred minors (issue 486) ─────────────────────────────────────────────────────────────


def test_a_second_catch_all_is_dead(world):
    rows = [{"when": {}, "then": 0}, {"when": {}, "then": 1}]
    assert _check(world, rows) == ["MD0323"]
    assert _check(world, rows[:1]) == []


def test_not_with_a_list_is_refused_at_load(world):
    body = """
version: 1
decisions:
  - decides: {effect: param, of: quantification, name: strandedness}
    rows:
      - {when: {strandedness: {not: [forward, reverse]}}, then: 1, cite: "a fixture"}
"""
    with pytest.raises(RuleValidationError, match="(?s)MD0305.*strandedness.*`in`"):
        _rules(world, body)


def test_an_enum_fact_must_take_only_the_settings_values(world):
    contracts = world["layer"] / "contracts"
    (contracts / "modal.yml").write_text(_declared(contracts / "modal.yml", MODAL))
    world["registry"] = Registry.load(world["layer"], world["vocabulary"])
    (world["layer"] / "measurements" / "speed.yml").write_text(
        _declared(world["layer"] / "measurements" / "speed.yml",
                  "kind: enum\nvalues: [fast, slow]\n"))
    world["measurements"] = MeasurementRegistry.load(world["layer"])
    body = """
version: 1
decisions:
  - decides: {effect: param, of: quantification, name: mode,
              when_implementation: [lab/modal@1.0.0]}
    rows:
      - {when: {}, then: {fact: speed}, cite: "a fixture"}
"""
    with pytest.raises(RuleValidationError, match="(?s)MD0300.*'slow'"):
        _rules(world, body)


def test_a_derived_facts_misfit_names_its_layer(world):
    as_number = FROM_FACT.replace("{fact: s_level, kind: integer,", "{fact: s_level, kind: number,")
    with pytest.raises(RuleValidationError) as refused:
        _rules(world, as_number)
    assert f"rules of layer {world['layer'].name!r}" in str(refused.value)


def test_a_rule_value_checked_against_every_filler(world):
    """MD0325 with no `when_implementation`: every tool filling the role is checked."""
    contracts = world["layer"] / "contracts"
    (contracts / "fc.yml").unlink()  # modal is the role's one filler, so it may be left unnamed
    (contracts / "modal.yml").write_text(_declared(contracts / "modal.yml", MODAL))
    world["registry"] = Registry.load(world["layer"], world["vocabulary"])
    body = """
version: 1
decisions:
  - decides: {effect: param, of: quantification, name: mode}
    rows:
      - {when: {}, then: fast, cite: "a fixture"}
"""
    with pytest.raises(RuleValidationError, match="(?s)MD0325.*lab/modal"):
        _rules(world, body)


def test_a_rule_value_forbidden_only_with_an_optional_input_is_not_refused(world):
    """Load assumes an optional input may be left out, so a row is refused only where every
    build would stop."""
    contracts = world["layer"] / "contracts"
    optional = MODAL.replace(
        "consumes: [{name: bam, type_id: alignment.bam::coordinate_sorted}]",
        "consumes: [{name: bam, type_id: alignment.bam::coordinate_sorted},\n"
        "           {name: extra, type_id: alignment.bam::coordinate_sorted, required: false}]",
    ).replace("forbids: [bam]", "forbids: [extra]").replace(
        "params:", "nf_inputs: [{ports: [bam]}, {ports: [extra], absent: 2}]\nparams:")
    assert optional != MODAL
    (contracts / "modal.yml").write_text(_declared(contracts / "modal.yml", optional))
    world["registry"] = Registry.load(world["layer"], world["vocabulary"])
    body = """
version: 1
decisions:
  - decides: {effect: param, of: quantification, name: mode,
              when_implementation: [lab/modal@1.0.0]}
    rows:
      - {when: {}, then: fast, cite: "a fixture"}
"""
    assert len(_rules(world, body).decisions) == 1


def test_premises_read_expand_derivations_transitively_once_each():
    from mendel_resolver.rules.format import DecisionRow
    from mendel_resolver.rules.table import _premises_read

    def premise(name, *sources):
        return Premise(id=name, value=1, origin=PremiseOrigin.MEASURED,
                       derived_from=list(sources))

    premises = {"a": premise("a", "b", "c"), "b": premise("b", "c"), "c": premise("c")}
    row = DecisionRow(when={"a": ">= 1", "b": ">= 1", "gone": "absent"}, then=1, cite="x")
    assert [p.id for p in _premises_read(row, premises)] == ["a", "b", "c"]
    premises["b"] = premise("b", "missing")  # a source with no premise adds nothing
    assert [p.id for p in _premises_read(row, premises)] == ["a", "b", "c"]
