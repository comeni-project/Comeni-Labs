"""Closed offers and arrow data are checked in their entirety."""

from importlib import import_module

import pytest
from pydantic import ValidationError


def test_arrow_data_is_closed_and_checked_against_the_arrow():
    p = import_module("mendel_authoring.payloads")
    with pytest.raises(ValidationError):
        p.SampleAnswered(answered=True, goal={})
    with pytest.raises(ValueError, match="payload"):
        p.check("understood", p.SampleAnswered(answered=True))
    assert p.check("upload_sample", p.SampleAnswered(answered=False)).answered is False
    with pytest.raises(ValidationError):
        p.GapAnswered(answered="guessed")


def test_an_entire_envelope_rejects_extra_keys_and_a_wrong_variant():
    e = import_module("mendel_api.authoring.envelopes")
    payload = {
        "offer": "pacing", "context": {"draft_revision": 3, "decision_revision": 2,
                                         "session_version": 1, "registry": ""},
        "options": {"together": "Together"},
        "block": {"kind": "question", "id": "pace", "asks": "How?", "why_open": "",
                  "options": [{"id": "together", "label": "Together"}]},
    }
    assert e.parse(payload, kind="pacing").context.draft_revision == 3
    with pytest.raises(ValidationError):
        e.parse({**payload, "override_anything": True}, kind="pacing")
    with pytest.raises(ValueError, match="variant"):
        e.parse(payload, kind="step")


def test_envelope_options_and_question_subject_cannot_disagree():
    e = import_module("mendel_api.authoring.envelopes")
    payload = {
        "offer": "gap", "context": {"draft_revision": 3, "decision_revision": 2,
                                     "session_version": 1, "registry": ""},
        "subject": "read_length", "kind": "measurement", "why": "needed",
        "options": {"value": "Tell me"},
        "block": {"kind": "question", "id": "gap", "asks": "How long?", "why_open": "",
                  "options": [{"id": "rogue", "label": "Tell me"}]},
    }
    with pytest.raises(ValueError, match="options"):
        e.parse(payload, kind="gap")
    payload["block"]["options"][0]["id"] = "value"
    envelope = e.parse(payload, kind="gap")
    with pytest.raises(ValueError, match="subject"):
        e.answer(envelope, option="value", subject="paired")
    with pytest.raises(ValueError, match="offered"):
        e.answer(envelope, option="rogue", subject="read_length")
    with pytest.raises(ValueError, match="MI0201"):
        e.answer(envelope, option="value", subject="read_length", decision_revision=3)


def test_stored_offer_is_refused_after_its_selected_decision_context_changes():
    from mendel_api.services import decisions, session
    from mendel_authoring import commands as c
    from mendel_postgres import reachable

    if not reachable():
        pytest.skip("needs throwaway Postgres")
    sid = session.perform(c.Begin("counts", "ana")).result[0]
    session.perform(c.Understood(sid, {"want": ["counts.matrix"]}))
    offered = session.read(sid)["pending_proposal"]
    decisions.set_fact(session.read(sid)["draft_id"], "read_length", 100, who="ana")
    with pytest.raises(ValueError, match="MI0201"):
        session.perform(c.AnswerGap(offered["id"], "have_it", None, "ana"))
    assert session.read(sid)["pending_proposal"]["id"] == offered["id"]
