"""A person's structural intent (A1) as selected decisions: each round-trips through the goal,
and a withdrawn one is not in it."""

from comeni_core.declared.measurement import MeasurementRegistry
from comeni_core.goal.asked import Goal
from mendel_authoring.decisions import (
    Decisions,
    ExclusionChoice,
    RoleChoice,
    SourceChoice,
)
from support.paths import REGISTRY

STAR = "nf-core/star/align@2.7.11b"
COUNTS = "nf-core/subread/featurecounts@2.1.1"


def test_decisions_round_trip_the_three_intents():
    goal = Goal.model_validate({
        "want": ["counts.matrix"],
        "constraints": {
            "absent_roles": [{"role": "trimming"}],
            "exclusions": [{"site": {"type_id": "alignment.bam"}, "contract": STAR}],
            "sources": [{"consumer": COUNTS, "port": "bam",
                         "producer": "nf-core/samtools/sort@1.24"}],
        },
    })
    fresh = Decisions.from_goal(goal).goal(MeasurementRegistry.load(REGISTRY))
    assert fresh.model_dump(mode="json") == goal.model_dump(mode="json")


def test_withdrawn_intents_are_not_in_the_goal():
    selected = Decisions(
        roles=[RoleChoice(role="trimming", absent=False)],
        exclusions=[ExclusionChoice(site={"type_id": "alignment.bam"}, contract=STAR,
                                    excluded=False)],
        sources=[SourceChoice(consumer=COUNTS, port="bam", producer=None)],
    )
    constraints = selected.goal(MeasurementRegistry.load(REGISTRY)).constraints
    assert (constraints.absent_roles, constraints.exclusions, constraints.sources) == ([], [], [])


QUAST = "nf-core/quast@5.3.0"


def test_an_optional_input_choice_round_trips_through_the_goal():
    """#460: a person switching a tool's optional input on is a decision like a source pin."""
    from mendel_authoring.decisions import OptionalInputChoice

    goal = Goal.model_validate({"want": ["qc.report"], "constraints": {
        "inputs": [{"contract": QUAST, "port": "fasta", "state": "optional"}]}})
    fresh = Decisions.from_goal(goal).goal(MeasurementRegistry.load(REGISTRY))
    assert fresh.model_dump(mode="json") == goal.model_dump(mode="json")
    withdrawn = Decisions(optional_inputs=[OptionalInputChoice(contract=QUAST, port="fasta",
                                                               state=None)])
    assert withdrawn.goal(MeasurementRegistry.load(REGISTRY)).constraints.inputs == []


def test_a_tool_kept_whole_round_trips_through_the_goal():
    from mendel_authoring.decisions import WholeChoice

    decisions = Decisions(wholes=[WholeChoice(contract="lab/search@1.0.0"),
                                  WholeChoice(contract="lab/other@1.0.0", whole=False)])
    goal = decisions.goal(MeasurementRegistry.load(REGISTRY))
    assert goal.constraints.whole == ["lab/search@1.0.0"]
    assert Decisions.from_goal(goal).wholes == [WholeChoice(contract="lab/search@1.0.0")]
