"""A fact a chosen tool reads and nobody supplied is a tier-4 record (#338)."""

from comeni_core.plan.decision import DecisionKind, DecisionRecord, FactDecision
from comeni_core.plan.ir import PipelineIR
from comeni_core.plan.tiers import Tier
from pydantic import TypeAdapter


def _open() -> FactDecision:
    return FactDecision(
        key="featurecounts.fact.strandedness",
        subject="strandedness",
        reason="nf-core/subread/featurecounts reads strandedness, and it is not known",
        resolved_by="flag-only",
        candidates=["forward", "reverse", "unstranded"],
        unknown=["strandedness"],
    )


def test_it_is_tier_four_and_round_trips_as_a_decision_record():
    record = _open()
    assert record.kind is DecisionKind.FACT and record.tier is Tier.AMBIGUOUS
    adapter = TypeAdapter(DecisionRecord)
    assert adapter.validate_python(adapter.dump_python(record, mode="json")) == record


def test_it_is_listed_for_review():
    ir = PipelineIR(decisions=[_open()])
    assert "featurecounts.fact.strandedness" in ir.needs_review()
