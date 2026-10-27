"""Messages sent while a reply is running wait in line (one builder plan 3, #392).

The composer never locks, so a second message can arrive before the first is answered. Each is
answered in the order sent, read against the session as it stands when its turn comes."""

import asyncio
import json

import arq
import pytest
from comeni_ai import Client, ModelAccess
from mendel_api.services import authoring_jobs, decisions
from mendel_api.services import session as facade
from mendel_api_tests.gathering import _gathering, _pending_for
from mendel_api_tests.gathering import clean as clean
from mendel_authoring import commands


def _model(monkeypatch, reply: dict) -> None:
    class Once:
        def send(self, access, prompt: str) -> str:
            return json.dumps(reply)

    monkeypatch.setattr(
        authoring_jobs,
        "_client",
        lambda *_: Client(ModelAccess(model="fake/test"), transport=Once()),
    )


def _state(sid: str, seq: int) -> str:
    return next(t["state"] for t in facade.read(sid)["turns"] if t["seq"] == seq)


def _value(sid: str, subject: str):
    draft = facade.read(sid)["draft_id"]
    return next((f.value for f in decisions.read(draft).facts if f.subject == subject), None)


def _answer(sid: str, seq: int) -> None:
    asyncio.run(authoring_jobs.answer_authoring_turn({}, sid, seq))


def test_a_second_message_waits_for_the_first_reply(clean, monkeypatch):
    sid = _gathering(want=["counts.matrix"])
    _model(monkeypatch, {"say": "Both describe where genes are."})
    first = facade.perform(commands.Say(sid, "what is a GTF?")).result
    second = facade.perform(commands.Say(sid, "and a GFF?")).result
    assert second > first
    with pytest.raises(arq.Retry):
        _answer(sid, second)
    assert _state(sid, second) == "pending"
    _answer(sid, first)
    _answer(sid, second)
    assert [_state(sid, s) for s in (first, second)] == ["answered", "answered"]


def test_a_queued_message_is_grounded_on_the_draft_when_it_is_read(clean, monkeypatch):
    # The first reply records a heard fact, which moves the draft; the second is still answered.
    sid = _gathering(want=["counts.matrix"])
    _pending_for(sid, "read_length")
    _model(monkeypatch, {"facts": [{"subject": "read_length", "value": 150, "quote": "150 bp"}]})
    first = facade.perform(commands.Say(sid, "they're 150 bp")).result
    second = facade.perform(commands.Say(sid, "thanks")).result
    _answer(sid, first)
    assert _value(sid, "read_length") == 150
    _model(monkeypatch, {"say": "You're welcome."})
    _answer(sid, second)
    assert _state(sid, second) == "answered"
