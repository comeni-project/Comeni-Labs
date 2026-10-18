"""Selected decisions compose one goal without losing shape or evidence."""

from importlib import import_module

import pytest
from comeni_core.declared.measurement import MeasurementRegistry
from comeni_core.goal.asked import Goal
from support.paths import REGISTRY


def _module():
    return import_module("mendel_authoring.decisions")


def test_selected_decisions_round_trip_named_inputs_and_all_constraints():
    d = _module()
    goal = Goal.model_validate(
        {
            "have": [
                {"type_id": "annotation.gtf", "name": "reference", "states": ["gene_level"]},
                {"type_id": "annotation.gtf", "name": "sample"},
            ],
            "want": ["counts.matrix", "qc.report"],
            "constraints": {
                "required_states": [{"type_id": "counts.matrix", "states": ["gene_level"]}],
                "params": [{"name": "threads", "value": 4}],
                "producers": [
                    {"site": {"type_id": "alignment.bam"}, "contract": "nf-core/hisat2/align@2.2.2"}
                ],
            },
            "profile": {"read_length": 150},
        }
    )
    selected = d.Decisions.from_goal(goal)
    fresh = selected.goal(MeasurementRegistry.load(REGISTRY))
    assert fresh.model_dump(mode="json") == goal.model_dump(mode="json")
    assert [i.name for i in fresh.have] == ["reference", "sample"]


def test_unknown_and_withdrawn_values_are_not_in_the_goal():
    d = _module()
    selected = d.Decisions(
        inputs=[
            d.InputDecision(key="reads", type_id="fastq.reads"),
            d.InputDecision(key="genome", type_id="genome.fasta", present=False),
        ],
        wants=[d.WantDecision(type_id="counts.matrix")],
        facts=[d.FactDecision(subject="read_length", origin=d.FactOrigin.OPEN)],
        producers=[d.ProducerChoice(site={"type_id": "alignment.bam"}, contract=None)],
        parameters=[d.ParameterChoice(name="threads", value=None)],
    )
    goal = selected.goal(MeasurementRegistry.load(REGISTRY))
    assert [i.type_id for i in goal.have] == ["fastq.reads"]
    assert goal.profile.measurements == []
    assert goal.constraints.producers == []
    assert goal.constraints.params == []


@pytest.mark.parametrize(
    ("origin", "expected"),
    [
        ("person_said", "said"),
        ("measured", "measured"),
        ("model_read", "model"),
    ],
)
def test_a_selection_preserves_the_evidence_origin(origin, expected):
    d = _module()
    fact = d.FactDecision(subject="read_length", value=100, origin=origin)
    goal = d.Decisions(facts=[fact]).goal(MeasurementRegistry.load(REGISTRY))
    [measured] = goal.profile.measurements
    assert measured.source.value == expected
    assert measured.value == 100


def test_selecting_an_inspection_keeps_its_pieces_and_counts():
    d = _module()
    fact = d.FactDecision(
        subject="read_length",
        value=100,
        origin="measured",
        pieces=["fastq@1.0.0", "read_length@1.0.0"],
        evidence={"records": 32},
    )
    goal = d.Decisions(facts=[fact]).goal(MeasurementRegistry.load(REGISTRY))
    [measured] = goal.profile.measurements
    assert measured.pieces == ["fastq@1.0.0", "read_length@1.0.0"]
    assert measured.evidence.records == 32


def test_unknown_cannot_hide_a_value_and_live_attribution_cannot_be_legacy_unknown():
    d = _module()
    with pytest.raises(ValueError, match="unknown"):
        d.FactDecision(subject="read_length", value=100, origin="open")
    with pytest.raises(ValueError, match="legacy"):
        d.Attribution(kind="unknown", who="ana")
    assert d.Attribution(kind="unknown", who="", legacy=True).legacy


def test_composition_refuses_a_measurement_outside_its_declaration():
    d = _module()
    with pytest.raises(ValueError):
        d.Decisions(facts=[d.FactDecision(subject="read_length", value="nonsense")]).goal(
            MeasurementRegistry.load(REGISTRY)
        )


def test_import_never_collapses_two_unnamed_inputs_of_the_same_type():
    d = _module()
    goal = Goal(
        have=[{"type_id": "fastq.reads"}, {"type_id": "fastq.reads"}], want=["counts.matrix"]
    )
    selected = d.Decisions.from_goal(goal)
    assert len({i.key for i in selected.inputs}) == 2
    assert selected.goal(MeasurementRegistry.load(REGISTRY)) == goal


def test_unrepresentable_required_state_records_are_refused_instead_of_silently_dropped():
    d = _module()
    goal = Goal(
        want=["counts.matrix"],
        constraints={"required_states": [{"type_id": "alignment.bam", "states": ["sorted"]}]},
    )
    with pytest.raises(ValueError, match="required"):
        d.Decisions.from_goal(goal)


def test_composition_preserves_required_state_order_independently_of_wanted_output_order():
    goal = Goal(
        want=["counts.matrix", "alignment.bam"],
        constraints={
            "required_states": [
                {"type_id": "alignment.bam", "states": ["coordinate_sorted"]},
                {"type_id": "counts.matrix", "states": ["gene_level"]},
            ]
        },
    )
    restored = _module().Decisions.from_goal(goal).goal(MeasurementRegistry.load(REGISTRY))
    assert restored.model_dump(mode="json") == goal.model_dump(mode="json")
