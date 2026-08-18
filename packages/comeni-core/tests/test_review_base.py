"""The shared question, and the properties the two subclasses both rely on."""

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
    """`closed=False` means the candidates are guidance, not a vocabulary.

    Binding a port *name* to a list the forge invented is what made multiqc's `reports`
    unreachable — a legal name that simply was not offered.
    """
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
    """Spec §3.1: every behavioural difference lives in a container or a port, so a
    `blocks()` or `is_open()` on the base is the design smell this guards against."""
    allowed = {"legal"}
    behaviour = {
        name
        for name in vars(Question)
        if callable(getattr(Question, name, None)) and not name.startswith("_")
    }
    assert behaviour <= allowed, f"unexpected behaviour on the base: {behaviour - allowed}"


def test_derived_is_a_source_and_hand_is_not():
    """The forge's `Filler` folds in here: HAND was HUMAN under another name, and DERIVED
    (a fact read off a source file) is genuinely distinct from RESOLVER (the ladder settled
    it) and MEASURED (a tool looked at the data)."""
    assert ValueSource.DERIVED == "derived"
    assert ValueSource.HUMAN == "human"
    assert not hasattr(ValueSource, "HAND")


def test_every_pre_existing_spelling_is_preserved():
    """`pipeline.yml` carries these strings. Changing one is a SCHEMA_VERSION break, and
    this refactor is not allowed to be one."""
    assert {
        ValueSource.RESOLVER,
        ValueSource.GOAL,
        ValueSource.HUMAN,
        ValueSource.MODEL,
        ValueSource.MEASURED,
    } == {"resolver", "goal", "human", "model", "measured"}


def test_tiers_still_exports_value_source():
    """25 call sites import it from here, and the public surface must not move."""
    from comeni_core.plan.tiers import ValueSource as FromTiers

    assert FromTiers is ValueSource


def test_an_answer_records_who_settled_it_and_why():
    a = Answer(value="qc.report", by="rafael", how=ValueSource.HUMAN, why="it is a report")
    assert a.value == "qc.report"
    assert a.how is ValueSource.HUMAN


def test_an_answer_forbids_extra_fields():
    with pytest.raises(ValidationError):
        Answer(value="x", by="y", how=ValueSource.HUMAN, why="z", confidence=1.0)
