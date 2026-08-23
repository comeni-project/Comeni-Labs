"""A model's choice and a person's choice are different facts and must stay different fields.

The alternative — a model writing `human_override` — reproduces A130: an adapter writing
`resolver` on every value is indistinguishable from the ladder, and there is no way to check the
claim afterwards. `ValueSource.MODEL` exists precisely so a model has somewhere truthful to write.
"""

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
    """An override with no author is the indistinguishability this field exists to prevent."""
    with pytest.raises(ValidationError, match="model_override_by"):
        _producer(model_override="nf-core/hisat2/align@2.2.2")


def test_both_at_once_is_refused():
    """A person and a model cannot both have made one choice. If a person changed a model's
    answer, that is a human override and the model's is history, not a co-signature."""
    with pytest.raises(ValidationError, match="one author"):
        _producer(
            human_override="nf-core/star/align@1.11.0",
            model_override="nf-core/hisat2/align@2.2.2",
            model_override_by="claude-opus-5",
        )


def test_a_decision_with_neither_is_still_legal():
    """The overwhelming majority. The validator must not require what the resolver never sets."""
    assert _producer().model_override is None


def test_a_param_overridden_to_null_is_indistinguishable_and_that_is_recorded():
    """A156, closed in the direction that can be proven — the same shape as A130.

    `HumanParamValue` includes `None`, so a parameter a model deliberately set to null looks
    exactly like one it never touched. `model_fields_set` was tried and is worse than the hole:
    after `model_dump()` every field is in it, so presence-by-fields-set refuses every
    `pipeline.yml` ever written. This test pins the limit so nobody rediscovers it as a bug.
    """
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
    """The direction that IS checkable. A record claiming a model decided something while
    recording no decision is the likelier error and the one that misleads a reader."""
    with pytest.raises(ValidationError, match="author with no act"):
        _producer(model_override_by="claude-opus-5")


def test_a_decision_round_trips_through_model_dump():
    """The guard against the fix that was tried and rejected. If presence is ever read off
    `model_fields_set` again, this fails immediately."""
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
    """A new field on a record that lands in `pipeline.yml` is a break for `comeni-core`."""
    from comeni_core.artifact.pipeline import SCHEMA_VERSION

    assert SCHEMA_VERSION == 5
