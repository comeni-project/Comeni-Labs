"""Evidence never replaces a selected answer without the chat's explicit decision."""

import pytest
from mendel_api.db import session_scope
from mendel_api.models import PipelineAuthoringSession, PipelineDraft
from mendel_api.services import decisions, session
from mendel_api_tests.disagreements import (
    _answer,
    _conflict,
)
from mendel_api_tests.samples import _facts, _gathering, _measured, _pending_for
from mendel_api_tests.samples import clean as clean
from mendel_authoring import commands as c


def test_the_chat_asks_and_reload_keeps_the_unselected_measurement(clean):
    sid = _conflict()
    pending = session.read(sid)["pending_proposal"]
    assert pending["kind"] == "disagreement"
    assert pending["payload"]["subject"] == "paired"
    assert set(pending["payload"]["options"]) == {
        "keep_current",
        "use_measurement",
        "correct",
        "unknown",
    }
    assert next(f for f in _facts(sid) if f["subject"] == "paired")["value"] is False
    with session_scope() as db:
        draft_id = db.get(PipelineAuthoringSession, sid).draft_id
    assert any(
        h["value"] is True and not h["selected"] for h in decisions.history(draft_id, "paired")
    )


@pytest.mark.parametrize(
    ("option", "value", "expected", "origin"),
    [
        ("keep_current", None, False, "person_said"),
        ("use_measurement", None, True, "measured"),
        ("correct", False, False, "person_said"),
        ("unknown", None, None, "open"),
    ],
)
def test_an_explicit_choice_preserves_origin_and_history(clean, option, value, expected, origin):
    sid = _conflict()
    _answer(sid, option, value)
    fact = next(f for f in _facts(sid) if f["subject"] == "paired")
    assert fact["value"] == expected and fact["source"] == origin
    pending = session.read(sid)["pending_proposal"]
    assert pending is None or pending["kind"] != "disagreement"


def test_invalid_correction_keeps_the_question_and_never_records_an_answer(clean):
    sid = _conflict()
    before = session.read(sid)
    with pytest.raises(ValueError):
        _answer(sid, "correct", "invented")
    assert session.read(sid) == before


def test_multiple_conflicts_are_asked_once_in_delivery_order(clean):
    sid = _gathering(["counts.matrix"])
    pid = _pending_for(sid, "paired")
    with session_scope() as db:
        draft_id = db.get(PipelineAuthoringSession, sid).draft_id
    decisions.set_fact(draft_id, "paired", False, who="ana")
    decisions.set_fact(draft_id, "read_length", 50, who="ana")
    session.perform(
        c.SampleInspected(
            pid, _measured(read_length=150, paired=True).model_dump(mode="json"), "ana"
        )
    )
    asked = []
    for _ in range(2):
        pending = session.read(sid)["pending_proposal"]
        assert pending["kind"] == "disagreement"
        asked.append(pending["payload"]["subject"])
        _answer(sid, "keep_current")
    assert set(asked) == {"read_length", "paired"} and len(set(asked)) == 2
    assert session.read(sid)["pending_proposal"]["kind"] != "disagreement"
    assert not decisions.pending_evidence(draft_id)


def test_two_measurements_have_truthful_sources_and_do_not_replace_each_other(clean):
    sid = _gathering(["counts.matrix"])
    pid = _pending_for(sid, "paired")
    session.perform(c.SampleInspected(pid, _measured(paired=False).model_dump(mode="json"), "ana"))
    pid = session.pending_id(sid)
    session.perform(
        c.SampleInspected(
            pid, _measured(read_length=150, paired=True).model_dump(mode="json"), "ana"
        )
    )
    offer = session.read(sid)["pending_proposal"]["payload"]
    assert offer["current_origin"] == offer["observed_origin"] == "measured"
    assert next(f for f in _facts(sid) if f["subject"] == "paired")["value"] is False


def test_an_equal_measurement_preserves_origin_and_is_not_reasked_after_correction(clean):
    sid = _gathering(["counts.matrix"])
    session.perform(c.AnswerGap(_pending_for(sid, "paired"), "no", None, "ana"))
    pid = _pending_for(sid, "read_length")
    session.perform(
        c.SampleInspected(
            pid, _measured(read_length=150, paired=False).model_dump(mode="json"), "ana"
        )
    )
    assert next(f for f in _facts(sid) if f["subject"] == "paired")["source"] == "person_said"
    from mendel_api_tests.corrections import _correct

    _correct(sid, "paired", True)
    pending = session.read(sid)["pending_proposal"]
    assert pending is None or pending["kind"] != "disagreement"


def test_a_question_answered_twice_records_only_one_choice(clean):
    sid = _conflict()
    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, sid)
        draft = db.get(PipelineDraft, row.draft_id)
        command = c.AnswerDisagreement(
            session.pending_id(sid),
            "keep_current",
            None,
            "ana",
            draft.decision_revision,
            draft.revision,
            row.row_version,
        )
    session.perform(command)
    before = session.read(sid)
    with pytest.raises(ValueError, match="MI0203"):
        session.perform(command)
    assert session.read(sid) == before


def test_late_inspection_is_retained_once_and_never_auto_selects_new_unknown_values(clean):
    sid = _gathering(["counts.matrix"])
    pid = _pending_for(sid, "read_length")
    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, sid)
        draft = db.get(PipelineDraft, row.draft_id)
        version, workflow, draft_id = draft.decision_revision, row.row_version, draft.id
    session.perform(c.AnswerGap(pid, "value", 100, "ana"))
    result = c.SampleInspected(
        pid,
        _measured(read_length=150).model_dump(mode="json"),
        "ana",
        expected_decision_revision=version,
        expected_session_version=workflow,
    )
    session.perform(result)
    assert next(f for f in _facts(sid) if f["subject"] == "read_length")["value"] == 100
    history = decisions.history(draft_id, "read_length")
    before = session.read(sid)
    session.perform(result)
    assert decisions.history(draft_id, "read_length") == history
    assert session.read(sid) == before


def test_a_late_model_answer_retains_evidence_once_without_selecting_unknown_facts(clean):
    from mendel_api.authoring.types import CharacteriseReply, ReadMeasurement
    from mendel_api.stages import samples

    sid = _gathering(["counts.matrix"])
    pid = _pending_for(sid, "read_length")
    attempt = samples.start_reading(pid)
    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, sid)
        draft = db.get(PipelineDraft, row.draft_id)
        versions = dict(
            expected_decision_revision=draft.decision_revision,
            expected_session_version=row.row_version,
        )
        draft_id = draft.id
    session.perform(c.AnswerGap(pid, "value", 100, "ana"))
    reply = CharacteriseReply(
        type_id="fastq.reads",
        measurements=[
            ReadMeasurement(id="read_length", value=150, evidence="150"),
            ReadMeasurement(id="n_samples", value=99, evidence="99"),
        ],
    )
    command = c.ReadingAnswered(
        pid, attempt, reply.model_dump(mode="json"), "ana", False, **versions
    )
    session.perform(command)
    assert not any(f["subject"] == "n_samples" and f["value"] == 99 for f in _facts(sid))
    history = decisions.history(draft_id, "n_samples")
    assert len(history) == 1 and history[0]["selected"] is False
    assert history[0]["origin"] == "model_read"
    view = session.read(sid)
    session.perform(command)
    assert decisions.history(draft_id, "n_samples") == history
    assert session.read(sid) == view


def test_http_disagreement_choice_is_scoped_and_requires_context(clean):
    from fastapi.testclient import TestClient
    from mendel_api.main import create_app

    sid = _conflict()
    pid = session.pending_id(sid)
    client = TestClient(create_app())
    url = f"/api/pipeline/authoring/{sid}/disagreements/{pid}"
    assert client.post(url, json={"option": "keep_current"}).status_code == 422
    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, sid)
        draft = db.get(PipelineDraft, row.draft_id)
        body = {
            "option": "use_measurement",
            "expected_decision_revision": draft.decision_revision,
            "expected_draft_revision": draft.revision,
            "expected_session_version": row.row_version,
        }
    answer = client.post(url, json=body)
    assert answer.status_code == 200, answer.text
    assert next(f for f in _facts(sid) if f["subject"] == "paired")["value"] is True


def test_a_model_read_value_has_its_own_source_in_the_disagreement(clean):
    sid = _gathering(["counts.matrix"])
    pid = _pending_for(sid, "paired")
    with session_scope() as db:
        row = db.get(PipelineAuthoringSession, sid)
        draft_id = row.draft_id
    observation = decisions.observe(draft_id, "paired", False, origin="model_read")
    decisions.select_observation(draft_id, "paired", observation, who="ana")
    session.perform(
        c.SampleInspected(
            pid, _measured(paired=True, read_length=150).model_dump(mode="json"), "ana"
        )
    )
    offer = session.read(sid)["pending_proposal"]["payload"]
    assert offer["current_origin"] == "model_read"
    assert offer["observed_origin"] == "measured"


def test_invalid_measurements_never_create_selectable_evidence(clean):
    from mendel_api.services import inspect

    sid = _gathering(["counts.matrix"])
    pid = _pending_for(sid, "paired")
    bad = _measured(paired="invalid")
    bad.facts.append(inspect.InspectedFact(measurement="invented", value=99))
    session.perform(c.SampleInspected(pid, bad.model_dump(mode="json"), "ana"))
    with session_scope() as db:
        draft_id = db.get(PipelineAuthoringSession, sid).draft_id
    assert decisions.history(draft_id, "invented") == []
    assert not any(h["selected"] is False for h in decisions.history(draft_id, "paired"))


def test_a_correction_while_an_async_sample_is_pending_says_to_retry(clean):
    from mendel_api.stages import samples
    from mendel_api_tests.corrections import _correct

    sid = _gathering(["counts.matrix"])
    pid = _pending_for(sid, "read_length")
    samples.start_reading(pid)
    before = session.read(sid)
    with pytest.raises(ValueError, match="MI0215"):
        _correct(sid, "paired", False)
    assert session.read(sid) == before
