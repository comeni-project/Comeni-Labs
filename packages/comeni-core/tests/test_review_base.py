"""Shared question and answer contracts used by authoring and resolution models."""

import pytest
from comeni_core.review.answer import Answer, ValueSource
from comeni_core.review.question import Candidate, Question
from pydantic import ValidationError


def _q(**kw) -> Question:
    base = {"subject": "produces[0].type_id", "what": "what this port carries"}
    return Question(**{**base, **kw})


def test_a_question_with_no_candidates_accepts_anything():
    """Nothing is known, so nothing can be refused."""
    assert _q().legal("anything at all")


def test_a_closed_question_refuses_a_value_it_did_not_offer():
    q = _q(candidates=[Candidate(value="qc.report")], closed=True)
    assert q.legal("qc.report")
    assert not q.legal("alignment.bam")


def test_an_open_question_accepts_a_value_it_did_not_offer():
    """Open candidates guide the reviewer without defining a closed vocabulary."""
    q = _q(candidates=[Candidate(value="reads")], closed=False)
    assert q.legal("multiqc_files")


def test_a_list_value_is_checked_member_by_member():
    """`roles` holds several values from one closed set, so the candidates are the legal
    *members* rather than the legal *values*."""
    q = _q(candidates=[Candidate(value="qc_per_sample"), Candidate(value="bam_sorting")])
    assert q.legal(["qc_per_sample"])
    assert q.legal(["qc_per_sample", "bam_sorting"])
    assert not q.legal(["qc_per_sample", "not_a_role"])


def test_a_question_forbids_extra_fields():
    """A field misspelled at a call site must not vanish. A32."""
    with pytest.raises(ValidationError):
        _q(candidatez=[])


def test_the_base_carries_no_behaviour_beyond_legality():
    """Blocking and workflow state belong to containers, not the shared value model."""
    allowed = {"legal"}
    behaviour = {
        name
        for name in vars(Question)
        if callable(getattr(Question, name, None)) and not name.startswith("_")
    }
    assert behaviour <= allowed, f"unexpected behaviour on the base: {behaviour - allowed}"


def test_derived_is_a_source_and_hand_is_not():
    """Derived source facts remain distinct from human, resolver, and measured values."""
    assert ValueSource.DERIVED == "derived"
    assert ValueSource.HUMAN == "human"
    assert not hasattr(ValueSource, "HAND")


def test_every_pre_existing_spelling_is_preserved():
    """Serialized artifacts and stored rows depend on these stable enum values."""
    assert {
        ValueSource.RESOLVER,
        ValueSource.SAID,
        ValueSource.HUMAN,
        ValueSource.MODEL,
        ValueSource.MEASURED,
    } == {"resolver", "said", "human", "model", "measured"}


def test_tiers_still_exports_value_source():
    """The compatibility import from ``plan.tiers`` retains object identity."""
    from comeni_core.plan.tiers import ValueSource as FromTiers

    assert FromTiers is ValueSource


def test_an_answer_records_who_settled_it_and_why():
    a = Answer(value="qc.report", by="rafael", how=ValueSource.HUMAN, why="it is a report")
    assert a.value == "qc.report"
    assert a.how is ValueSource.HUMAN


def test_an_answer_forbids_extra_fields():
    with pytest.raises(ValidationError):
        Answer(value="x", by="y", how=ValueSource.HUMAN, why="z", confidence=1.0)


def test_an_ambiguity_is_a_question():
    from comeni_core.plan.decision import Ambiguity

    assert issubclass(Ambiguity, Question)


def test_a_resolution_is_an_answer():
    from comeni_core.plan.decision import Resolution

    assert issubclass(Resolution, Answer)


def test_a_resolution_still_narrows_its_value():
    """``Resolution`` narrows the base answer's unrestricted value to ``ParamValue``."""
    from comeni_core.plan.decision import Resolution

    with pytest.raises(ValidationError):
        Resolution(value=object(), by="x", how=ValueSource.RESOLVER, why="y")


def test_a_resolution_keeps_its_confidence():
    """Confidence belongs to resolution rather than every kind of answer."""
    from comeni_core.plan.decision import Resolution

    assert "confidence" in Resolution.model_fields
    assert "confidence" not in Answer.model_fields


def test_goal_is_no_longer_a_source():
    """The closed enum uses ``said`` for person-stated values."""
    import pytest

    with pytest.raises(ValueError):
        ValueSource("goal")


def test_said_is_what_is_written():
    from comeni_core.goal.profile import Measured

    assert Measured(measurement="paired", value=True).model_dump(mode="json")["source"] == "said"
