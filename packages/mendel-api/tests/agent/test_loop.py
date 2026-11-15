"""The builder agent's loop (#463): tool calls, a reply, refusals back to the model, limits,
failures, and a question that ends the turn. A scripted transport stands in for the model."""

import pytest
from comeni_ai.agent import AgentReply, ScriptedAgentTransport, ToolCall
from comeni_ai.client import ModelUnavailableError
from comeni_core.diagnostics import coded
from comeni_core.plan.draft import DraftGraph
from mendel_api.agent import loop
from mendel_api.db import session_scope
from mendel_api.models import AiInvocation, PipelineAuthoringTurn
from mendel_api.services import drafts
from mendel_api.settings import settings
from mendel_api_tests.building import clean as clean
from mendel_api_tests.database import reachable
from sqlalchemy import select

pytestmark = pytest.mark.skipif(not reachable(), reason="no database")


def _call(name, **arguments) -> AgentReply:
    return AgentReply(calls=[ToolCall(id=f"c-{name}", name=name, arguments=arguments)])


def _say(text) -> AgentReply:
    return AgentReply(text=text)


def _turn(session_id, seq) -> PipelineAuthoringTurn:
    with session_scope() as db:
        return db.scalar(select(PipelineAuthoringTurn).where(
            PipelineAuthoringTurn.session_id == session_id, PipelineAuthoringTurn.seq == seq))


def _started(monkeypatch, replies, text="gene counts from my RNA-seq reads"):
    monkeypatch.setattr(loop, "model_access", lambda: object())
    script = ScriptedAgentTransport(replies)
    session_id = loop.start_session(drafts.create(DraftGraph(), "agent", "ana"), who="ana")
    seq = loop.add_person_turn(session_id, text)
    loop.run_turn(session_id, seq, transport=script)
    return session_id, seq, script


def test_a_turn_calls_tools_then_replies(clean, monkeypatch):
    session_id, seq, _ = _started(monkeypatch, [_call("read_goal"), _say("Here is what I built")])
    turn = _turn(session_id, seq)
    assert turn.state == "answered"
    assert [(b["kind"], b.get("name"), b.get("ok")) for b in turn.blocks] == [
        ("tool", "read_goal", True), ("message", None, None)]
    assert turn.blocks[-1]["text"] == "Here is what I built"
    with session_scope() as db:
        calls = db.scalars(select(AiInvocation).where(AiInvocation.session_id == session_id)).all()
    assert [(c.agent, c.purpose, c.state) for c in calls] == [("builder", "agent", "succeeded")] * 2


def test_a_tool_refusal_goes_back_to_the_model(clean, monkeypatch):
    session_id, seq, script = _started(
        monkeypatch, [_call("want", type_id="no.such.type", because="test"), _say("Sorry")])
    sent_back = [m for m in script.sent[1] if m["role"] == "tool"]
    assert sent_back and "MI0204" in sent_back[-1]["content"]
    assert _turn(session_id, seq).state == "answered"


def test_the_turn_stops_at_the_step_limit(clean, monkeypatch):
    monkeypatch.setattr(settings, "agent_max_steps", 3)
    session_id, seq, _ = _started(monkeypatch, [_call("read_goal")] * 4)
    turn = _turn(session_id, seq)
    assert turn.state == "answered"
    assert turn.blocks[-1]["kind"] == "notice" and turn.blocks[-1]["notice"] == "limit"
    again = loop.add_person_turn(session_id, "go on")
    loop.run_turn(session_id, again, transport=ScriptedAgentTransport([_say("Going on")]))
    assert _turn(session_id, again).state == "answered"


def test_a_provider_failure_fails_the_turn_with_its_code(clean, monkeypatch):
    class Down:
        def converse(self, access, messages, tools):
            raise ModelUnavailableError(coded("MA0007", "fake/test: unreachable"))

    monkeypatch.setattr(loop, "model_access", lambda: object())
    session_id = loop.start_session(drafts.create(DraftGraph(), "agent", "ana"), who="ana")
    seq = loop.add_person_turn(session_id, "hello")
    loop.run_turn(session_id, seq, transport=Down())
    turn = _turn(session_id, seq)
    assert turn.state == "failed"
    assert turn.blocks[-1]["notice"] == "refusal" and turn.blocks[-1]["code"] == "MA0007"


def test_asking_ends_the_turn_with_the_question(clean, monkeypatch):
    session_id, seq, script = _started(
        monkeypatch, [_call("ask", question="Do you have a GTF?", shape="yes_no")])
    turn = _turn(session_id, seq)
    assert turn.state == "answered"
    assert turn.blocks[-1]["kind"] == "ask"
    assert turn.blocks[-1]["question"] == "Do you have a GTF?"
    assert len(script.sent) == 1, "the agent waits for the person after asking"


def test_no_model_configured_says_so_and_calls_nothing(clean, monkeypatch):
    monkeypatch.setattr(loop, "model_access", lambda: None)
    script = ScriptedAgentTransport([_say("never sent")])
    session_id = loop.start_session(drafts.create(DraftGraph(), "agent", "ana"), who="ana")
    seq = loop.add_person_turn(session_id, "gene counts")
    assert loop.run_turn(session_id, seq, transport=script) == "failed"
    [notice] = _turn(session_id, seq).blocks
    assert (notice["notice"], notice["code"]) == ("refusal", "MI0106")
    assert "Settings" in notice["text"]
    assert script.sent == [], "nothing reaches a provider without a model"


def test_the_conversation_crosses_as_the_declared_payload(clean, monkeypatch):
    """The person's words and the agent's own reach the model as `AgentRequest`'s turns."""
    from comeni_core.egress.agent import AgentRequest, Speaker

    session_id, seq, script = _started(monkeypatch, [_say("Gene counts, then.")])
    later = loop.add_person_turn(session_id, "and trim the reads first")
    loop.run_turn(session_id, later, transport=ScriptedAgentTransport([_say("Done.")]))
    sent = loop.conversation(session_id, later + 1)
    assert isinstance(sent, AgentRequest)
    assert [(t.speaker, t.content) for t in sent.turns] == [
        (Speaker.PERSON, "gene counts from my RNA-seq reads"),
        (Speaker.AGENT, "Gene counts, then."),
        (Speaker.PERSON, "and trim the reads first"), (Speaker.AGENT, "Done.")]
