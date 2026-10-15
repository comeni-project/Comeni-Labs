"""Typed words anywhere become changes the engine records or offers (Part I.0 spec §5.3, §7.2).

Supersedes #171's *a typed reply pre-fills and records nothing*: a typed answer that quotes the
person is recorded; one that does not is offered, as before, and only the click records it."""

import asyncio
import json

from comeni_ai import Client, ModelAccess
from mendel_api.services import authoring_jobs, decisions, suggestions
from mendel_api.services import session as facade
from mendel_api.stages import describe
from mendel_api_tests.building import (  # noqa: F401
    _answer_all,
    _resolving,
    authoring_setup,
)
from mendel_api_tests.gathering import _facts, _gathering, _payload, _pending_for
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


def _typed(monkeypatch, sid: str, text: str, reply: dict) -> None:
    _model(monkeypatch, reply)
    seq = facade.perform(commands.Say(sid, text)).result
    asyncio.run(authoring_jobs.answer_authoring_turn({}, sid, seq))


def _draft(sid: str) -> str:
    return facade.read(sid)["draft_id"]


def _value(sid: str, subject: str):
    return next((f.value for f in decisions.read(_draft(sid)).facts if f.subject == subject), None)


def test_a_quoted_typed_answer_is_recorded_and_the_next_question_follows(clean, monkeypatch):
    sid = _gathering(want=["counts.matrix"])
    _pending_for(sid, "read_length")
    _typed(
        monkeypatch,
        sid,
        "they're 150 bp",
        {"facts": [{"subject": "read_length", "value": 150, "quote": "150 bp"}]},
    )
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
    _typed(
        monkeypatch,
        sid,
        "actually the reads are 50 bp",
        {"say": "Noted.", "facts": [{"subject": "read_length", "value": 50, "quote": "50 bp"}]},
    )
    assert _value(sid, "read_length") == before
    [offered] = suggestions.pending(sid)
    assert offered.heard and offered.says == "read length is 50"
    result = asyncio.run(suggestions.apply(sid, offered.id, by="ana"))
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
        ("paired", False)
    ]


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
    _typed(
        monkeypatch, sid, "why do you need a genome?", {"say": "Your reads are aligned against it."}
    )
    assert (_facts(sid), facade.pending_id(sid)) == before
    assert facade.read(sid)["turns"][-1]["blocks"][0]["text"] == (
        "Your reads are aligned against it."
    )


def test_a_click_before_the_job_starts_still_wins(clean, monkeypatch):
    """Review I3: the baseline was read when the job started, so a click made while a busy
    worker had not yet reached the turn was overwritten. It is the decisions as they stood when
    the person spoke."""
    sid = _gathering(want=["counts.matrix"])
    pid = _pending_for(sid, "paired")
    seq = facade.perform(commands.Say(sid, "single-end, I think")).result
    facade.perform(commands.AnswerGap(pid, "yes", None, "ana"))  # the click, before the job
    _model(monkeypatch, {"facts": [{"subject": "paired", "value": False, "quote": "single-end"}]})
    asyncio.run(authoring_jobs.answer_authoring_turn({}, sid, seq))
    assert _value(sid, "paired") is True
    assert [(v.change.subject, v.change.value) for v in suggestions.pending(sid)] == [
        ("paired", False)
    ]


def test_a_refusal_says_what_it_refused(clean, monkeypatch):
    """Issue 325, from the walk: the notice kept only *"the reply names something this registry
    does not declare"*, so nobody could tell what. The walk's reply, word for word."""
    sid = _gathering(want=["counts.matrix"])
    _pending_for(sid, "read_length")
    _typed(
        monkeypatch,
        sid,
        "I already said: 2x100, so 100 bp",
        {"parameters": [{"name": "sequenced_read_length", "value": "100"}]},
    )
    [notice] = _notices(sid)
    assert notice["code"] == "MI0204"
    assert "setting sequenced_read_length" in notice["text"]


def test_the_model_is_told_what_the_waiting_question_asks(clean, monkeypatch):
    """Issue 324: with the read-length question waiting, the prompt names `read_length`, so a
    typed answer has an id to land on."""
    sent: list[str] = []

    class Seen:
        def send(self, access, prompt) -> str:
            sent.append(prompt if isinstance(prompt, str)
                        else "\n".join(m["content"] for m in prompt))
            return json.dumps({"say": "Noted."})

    monkeypatch.setattr(
        authoring_jobs, "_client",
        lambda *_: Client(ModelAccess(model="fake/test"), transport=Seen()),
    )
    sid = _gathering(want=["counts.matrix"])
    _pending_for(sid, "read_length")
    seq = facade.perform(commands.Say(sid, "100 bp")).result
    asyncio.run(authoring_jobs.answer_authoring_turn({}, sid, seq))
    assert sent and '"subject": "read_length"' in sent[-1]


def _notices(sid: str) -> list[dict]:
    return [block for turn in facade.read(sid)["turns"] for block in turn["blocks"]
            if block.get("kind") == "notice"]


def _said(sid: str) -> list[str]:
    return [block["text"] for turn in facade.read(sid)["turns"] for block in turn["blocks"]
            if block.get("kind") == "narrative" and turn["role"] == "assistant"]


def test_one_refused_item_sets_itself_aside_and_the_rest_is_kept(clean, monkeypatch):
    """Issue 326 (operator: B), the walk's scene 3: a correct fact beside an undeclared setting
    lost both, and the model's words. The fact is kept, the words shown, the setting named."""
    sid = _gathering(want=["counts.matrix"])
    _pending_for(sid, "read_length")
    _typed(
        monkeypatch,
        sid,
        "they're 100 bp",
        {"say": "Got it, 100 bp.",
         "facts": [{"subject": "read_length", "value": 100, "quote": "100 bp"}],
         "parameters": [{"name": "sequenced_read_length", "value": "100"}]},
    )
    assert _value(sid, "read_length") == 100
    assert "Got it, 100 bp." in _said(sid)
    [notice] = _notices(sid)
    assert notice["notice"] == "validation" and notice["code"] == "MI0204"
    assert "setting sequenced_read_length" in notice["text"]


def test_words_naming_what_was_set_aside_are_not_shown(clean, monkeypatch):
    """The reply text shows unless it names something refused: it would speak of a thing that
    does not exist here as if it did."""
    sid = _gathering(want=["counts.matrix"])
    _pending_for(sid, "read_length")
    _typed(
        monkeypatch,
        sid,
        "set it to 100",
        {"say": "I set sequenced_read_length to 100.",
         "parameters": [{"name": "sequenced_read_length", "value": "100"}]},
    )
    assert not any("sequenced_read_length" in text for text in _said(sid))
    assert [n["code"] for n in _notices(sid)] == ["MI0204"]
