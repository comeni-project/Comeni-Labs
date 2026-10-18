"""Regression checks for pipeline duplicate detection and indexed decision replay."""

from comeni_core.artifact.pipeline import Pipeline, _duplicates
from comeni_core.goal.asked import Constraints, Goal, ProducerPin, Site
from comeni_core.plan.decision import ProducerDecision


def test_duplicate_diagnostics_are_sorted_and_report_each_name_once():
    values = iter(["z", "b", "z", "a", "b", "z", "unique"])
    assert _duplicates(values) == ["b", "z"]
    assert _duplicates(iter([])) == []


def test_duplicate_detection_does_not_compare_every_pair():
    class CountedName(str):
        comparisons = 0
        __hash__ = str.__hash__

        def __eq__(self, other):
            type(self).comparisons += 1
            return super().__eq__(other)

    values = [CountedName(f"step_{i}") for i in range(1000)]
    assert _duplicates(values) == []
    assert CountedName.comparisons < 3000


def test_replay_scans_goal_pins_once_and_only_omits_matching_overrides():
    class CountedPins(list):
        scans = 0

        def __iter__(self):
            self.scans += 1
            return super().__iter__()

    pinned = "nf-core/hisat2/align@2.2.2"
    other = "nf-core/star/align@1.11.0"
    pins = CountedPins([ProducerPin(site=Site(type_id="alignment.bam"), contract=pinned)])
    constraints = Constraints().model_copy(update={"producers": pins})
    goal = Goal(constraints=constraints)
    decisions = [
        ProducerDecision(
            key=f"step_{i}.producer:alignment.bam",
            subject="producer:alignment.bam",
            reason="test selection",
            resolved_by="flag-only",
            chosen=other,
            human_override=pinned,
        )
        for i in range(100)
    ]
    different_contract = decisions[0].model_copy(
        update={"key": "different.producer:alignment.bam", "human_override": other}
    )
    unanswered = decisions[0].model_copy(
        update={"key": "unanswered.producer:alignment.bam", "human_override": None}
    )
    different_type = decisions[0].model_copy(
        update={"key": "different.producer:qc.report", "subject": "producer:qc.report"}
    )
    remaining = [different_contract, unanswered, different_type]
    pipeline = Pipeline.model_validate(
        {"intent": goal.intent, "facts": goal.facts, "decisions": [*decisions, *remaining]})
    # Validation may copy the pins; count the list the pipeline holds.
    pipeline = pipeline.model_copy(
        update={"intent": pipeline.intent.model_copy(update={"constraints": constraints})})
    pins.scans = 0

    assert pipeline.replayable_decisions() == remaining
    assert pins.scans == 1
