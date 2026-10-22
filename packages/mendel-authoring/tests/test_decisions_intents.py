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

STAR = "nf-core/star/align@1.11.0"
COUNTS = "nf-core/subread/featurecounts@2.0.6"


def test_decisions_round_trip_the_three_intents():
    goal = Goal.model_validate({
        "want": ["counts.matrix"],
        "constraints": {
            "absent_roles": [{"role": "trimming"}],
            "exclusions": [{"site": {"type_id": "alignment.bam"}, "contract": STAR}],
            "sources": [{"consumer": COUNTS, "port": "bam",
                         "producer": "nf-core/samtools/sort@1.21.0"}],
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
