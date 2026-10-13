"""Typed words anywhere become changes the engine records or offers (Part I.0 spec §5.3, §7.2).

Supersedes #171's *a typed reply pre-fills and records nothing*: a typed answer that quotes the
person is recorded; one that does not is offered, as before, and only the click records it."""

import asyncio
import json

from comeni_ai import Client, ModelAccess
from mendel_api.services import authoring_jobs, decisions, suggestions
from mendel_api.services import session as facade
from mendel_api.stages import describe
from mendel_authoring import commands
from test_authoring_building import (  # noqa: F401
    _answer_all,
    _resolving,
    authoring_setup,
)
from test_authoring_gathering import _facts, _gathering, _payload, _pending_for
from test_authoring_gathering import clean as clean


def _model(monkeypatch, reply: dict) -> None:
    class Once:
        def send(self, access, prompt: str) -> str:
            return json.dumps(reply)

    monkeypatch.setattr(authoring_jobs, "_client",
                        lambda *_: Client(ModelAccess(model="fake/test"), transport=Once()))


def _typed(monkeypatch, sid: str, text: str, reply: dict) -> None:
    _model(monkeypatch, reply)
    seq = facade.perform(commands.Say(sid, text)).result
    asyncio.run(authoring_jobs.answer_authoring_turn({}, sid, seq))


def _draft(sid: str) -> str:
    return facade.read(sid)["draft_id"]


def _value(sid: str, subject: str):
    return next((f.value for f in decisions.read(_draft(sid)).facts if f.subject == subject),
                None)


def test_a_quoted_typed_answer_is_recorded_and_the_next_question_follows(clean, monkeypatch):
    sid = _gathering(want=["counts.matrix"])
    _pending_for(sid, "read_length")
    _typed(monkeypatch, sid, "they're 150 bp",
           {"facts": [{"subject": "read_length", "value": 150, "quote": "150 bp"}]})
    assert _value(sid, "read_length") == 150
    assert decisions.heard_of(_draft(sid))[("fact", "read_length")][0] == "150 bp"
    pending = facade.pending_id(sid)
    assert pending is None or _payload(pending)["subject"] != "read_length"


def test_an_unquoted_typed_answer_pre_fills_and_records_nothing(clean, monkeypatch):
    sid = _gathering(want=["counts.matrix"])
    pid = _pending_for(sid, "paired")
    before = _facts(sid)
    _typed(monkeypatch, sid, "yes, both ends", {"facts": [{"subject": "paired", "value": True}]})
    assert _facts(sid) == before
    assert [v.change.subject for v in suggestions.pending(sid)] == ["paired"]
    del pid


def test_once_confirmed_a_heard_change_waits_for_a_click_then_re_resolves(clean, monkeypatch):
    sid = _resolving()
    _answer_all(sid, authoring_setup.start_building(sid))
    before = _value(sid, "read_length")
    _typed(monkeypatch, sid, "actually the reads are 50 bp",
           {"say": "Noted.",
            "facts": [{"subject": "read_length", "value": 50, "quote": "50 bp"}]})
    assert _value(sid, "read_length") == before
    [offered] = suggestions.pending(sid)
    assert offered.heard and offered.says == "read length is 50"
    result = suggestions.apply(sid, offered.id, by="ana")
    assert _value(sid, "read_length") == 50
    assert result["phase"] == "building"


def test_a_reading_that_lands_after_a_click_is_offered_not_recorded(clean, monkeypatch):
    """Review Focus 2: the person clicked while the model read their typed words."""
    sid = _gathering(want=["counts.matrix"])
    pid = _pending_for(sid, "paired")
    seq = facade.perform(commands.Say(sid, "single-end, I think")).result
    context = describe.turn_context(sid, seq)  # read when the job starts
    facade.perform(commands.AnswerGap(pid, "yes", None, "ana"))  # the click lands
    _model(monkeypatch, {"facts": [{"subject": "paired", "value": False, "quote": "single-end"}]})
    authoring_jobs._follow_up(sid, seq, context)
    assert _value(sid, "paired") is True
    assert [(v.change.subject, v.change.value) for v in suggestions.pending(sid)] == [
        ("paired", False)]


def test_go_on_settles_the_waiting_step_and_does_nothing_at_a_question(clean, monkeypatch):
    sid = _resolving()
    first = authoring_setup.start_building(sid)
    _typed(monkeypatch, sid, "looks good, go on", {"say": "Carrying on.", "proceed": True})
    assert facade.pending_id(sid) != first

    gathering_sid = _gathering(want=["counts.matrix"])
    waiting = facade.pending_id(gathering_sid)
    _typed(monkeypatch, gathering_sid, "go on", {"proceed": True})
    assert facade.pending_id(gathering_sid) == waiting


def test_something_to_say_alone_records_nothing(clean, monkeypatch):
    sid = _gathering(want=["counts.matrix"])
    before = (_facts(sid), facade.pending_id(sid))
    _typed(monkeypatch, sid, "why do you need a genome?",
           {"say": "Your reads are aligned against it."})
    assert (_facts(sid), facade.pending_id(sid)) == before
    assert facade.read(sid)["turns"][-1]["blocks"][0]["text"] == (
        "Your reads are aligned against it.")
