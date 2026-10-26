"""Model and human overrides remain distinct, attributable decision fields."""

import pytest
from comeni_core.plan.decision import ParamDecision, ProducerDecision, SourceDecision
from pydantic import ValidationError


def _producer(**kw):
    base = dict(
        key="producer:alignment.bam",
        subject="alignment.bam",
        reason="r",
        resolved_by="flag-only",
        chosen="nf-core/star/align@1.11.0",
    )
    return ProducerDecision(**{**base, **kw})


def test_a_model_choice_is_not_a_human_choice():
    d = _producer(model_override="nf-core/hisat2/align@2.2.2", model_override_by="claude-opus-5")
    assert d.human_override is None
    assert d.model_override == "nf-core/hisat2/align@2.2.2"
    assert d.model_override_by == "claude-opus-5"


def test_a_model_override_must_name_who():
    """A model override without its author is invalid."""
    with pytest.raises(ValidationError, match="model_override_by"):
        _producer(model_override="nf-core/hisat2/align@2.2.2")


def test_both_at_once_is_refused():
    """One decision cannot claim both a human and model author."""
    with pytest.raises(ValidationError, match="one author"):
        _producer(
            human_override="nf-core/star/align@1.11.0",
            model_override="nf-core/hisat2/align@2.2.2",
            model_override_by="claude-opus-5",
        )


def test_a_decision_with_neither_is_still_legal():
    """Ordinary resolver decisions require no override."""
    assert _producer().model_override is None


def test_a_param_overridden_to_null_is_indistinguishable_and_that_is_recorded():
    """A null parameter override is indistinguishable from absence by design."""
    d = ParamDecision(
        key="param:star.seq_platform",
        subject="star.seq_platform",
        reason="r",
        resolved_by="flag-only",
        chosen="ILLUMINA",
        model_override=None,
    )
    assert d.model_override is None
    assert d.model_override_by == ""


def test_an_author_naming_nothing_is_refused():
    """An author field without a corresponding override is invalid."""
    with pytest.raises(ValidationError, match="author with no act"):
        _producer(model_override_by="claude-opus-5")


def test_a_decision_round_trips_through_model_dump():
    """Authorship validation remains stable after serialized round trips."""
    d = _producer(model_override="nf-core/hisat2/align@2.2.2", model_override_by="claude-opus-5")
    assert ProducerDecision(**d.model_dump()) == d
    assert _producer() == ProducerDecision(**_producer().model_dump())


def test_the_edge_kind_carries_it_too():
    d = SourceDecision(
        key="source:counts.bam",
        subject="counts.bam",
        reason="r",
        resolved_by="flag-only",
        chosen="align.bam",
        model_override="sort.bam",
        model_override_by="claude-opus-5",
    )
    assert d.model_override_by == "claude-opus-5"


def test_the_schema_version_moved():
    """Artifacts carrying override fields use a compatible schema version."""
    from comeni_core.artifact.pipeline import SCHEMA_VERSION

    assert SCHEMA_VERSION >= 6  # 6 added the override; later versions keep it
