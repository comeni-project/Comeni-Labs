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


def test_the_agent_narrates_and_the_running_tool_shows_while_it_runs(clean, monkeypatch):
    """#504: what the agent says beside a tool call is narration, drawn with the trail; the tool
    it is running is written before it returns, so the page can say what is happening."""
    seen: list[list[dict]] = []
    real = loop.call

    def watching(ctx, name, arguments):
        with session_scope() as db:
            turn = db.scalars(select(PipelineAuthoringTurn).where(
                PipelineAuthoringTurn.session_id == ctx.session_id)
                .order_by(PipelineAuthoringTurn.seq.desc())).first()
            seen.append(list(turn.blocks))
        return real(ctx, name, arguments)

    monkeypatch.setattr(loop, "call", watching)
    session_id, seq, _ = _started(monkeypatch, [
        AgentReply(text="Let me see what you asked for.",
                   calls=[ToolCall(id="c-read_goal", name="read_goal", arguments={})]),
        _say("Nothing is built yet.")])
    [during] = seen
    assert during[-1]["kind"] == "tool" and during[-1]["running"] is True
    assert during[-1]["label"] == "Reading the goal"
    assert (during[0]["kind"], during[0]["narration"]) == ("message", True)
    blocks = _turn(session_id, seq).blocks
    assert [(b["kind"], b.get("narration"), b.get("running")) for b in blocks] == [
        ("message", True, None), ("tool", None, False), ("message", False, None)]
    assert blocks[1]["label"] == "Read the goal"


def test_a_tool_that_crashes_fails_the_turn_and_nothing_stays_running(clean, monkeypatch):
    """#463 review: an error that is no engine refusal must not leave the turn pending forever,
    with its tool line still saying it is running and the page polling for an answer."""
    def broken(ctx, name, arguments):
        raise RuntimeError("the database went away")

    monkeypatch.setattr(loop, "call", broken)
    session_id, seq, _ = _started(monkeypatch, [_call("read_goal"), _say("never")])
    turn = _turn(session_id, seq)
    assert turn.state == "failed"
    assert not any(b.get("running") for b in turn.blocks), "nothing says it is still running"
    [notice] = [b for b in turn.blocks if b["kind"] == "notice"]
    assert notice["code"] == "MI0220" and "database" not in notice["text"]


def test_a_tool_name_the_engine_cannot_print_is_a_refusal(clean):
    from mendel_api.agent.tools import ToolContext, call

    result = call(ToolContext(draft_id="d", session_id=None, who="ana", expected_revision=0),
                  "read_goal\n" + "x" * 300, {})
    assert result.ok is False and "no tool" in result.refusal


def test_a_tool_line_names_the_step_it_touched(clean, monkeypatch):
    """#499: the pipeline file links an answer to the steps the agent read or changed, from the
    tools it called — a link the engine derives, never one the model writes."""
    from mendel_api.services import decisions
    from mendel_resolver.goal import Goal
    from support.example import example_mapping

    monkeypatch.setattr(loop, "model_access", lambda: object())
    session_id = loop.start_session(drafts.create(DraftGraph(), "agent", "ana"), who="ana")
    with session_scope() as db:
        from mendel_api.models import PipelineAuthoringSession
        draft = db.get(PipelineAuthoringSession, session_id).draft_id
    decisions.import_goal(draft, Goal.model_validate(example_mapping()), who="ana")
    seq = loop.add_person_turn(session_id, "build it, then look at the aligner")
    from comeni_ai.agent import ScriptedAgentTransport
    loop.run_turn(session_id, seq, transport=ScriptedAgentTransport([
        _call("resolve"), _call("read_step", node="star_align"), _call("read_goal"),
        _say("Read it.")]))
    tools = [b for b in _turn(session_id, seq).blocks if b["kind"] == "tool"]
    assert [(t["name"], t.get("node")) for t in tools] == [
        ("resolve", None), ("read_step", "star_align"), ("read_goal", None)]


def test_a_step_link_is_only_a_step_the_pipeline_has(clean, monkeypatch):
    """Plan 2 review I6: a refused call, or a node the pipeline does not have, links nothing; and
    a lookup that fails ends the turn failed, never stuck working."""
    session_id, seq, _ = _started(monkeypatch, [
        _call("read_step", node="star_alignn"), _say("Read it.")])
    [line] = [b for b in _turn(session_id, seq).blocks if b["kind"] == "tool"]
    assert line.get("node") is None

    def broken(*args):
        raise RuntimeError("bad blueprint")

    monkeypatch.setattr(loop, "_node_of", broken)
    session_id, seq, _ = _started(monkeypatch, [_call("read_goal"), _say("never")])
    turn = _turn(session_id, seq)
    assert turn.state == "failed" and not any(b.get("running") for b in turn.blocks)


def test_a_reply_that_only_announces_a_plan_is_told_to_go_ahead(clean, monkeypatch):
    """Walk 2026-11-15: GPT answered "I'll check the current setup, then build…" with no tool
    call, and the turn ended with nothing built. A first reply that only announces what it will
    do is told once to do it; the turn then goes on."""
    session_id, seq, script = _started(monkeypatch, [
        _say("I'll check the current setup, then build the workflow."),
        _call("read_goal"), _say("Nothing is wanted yet; tell me what you have.")])
    turn = _turn(session_id, seq)
    assert [b["kind"] for b in turn.blocks] == ["message", "tool", "message"]
    assert turn.blocks[0]["narration"] is True, "the announcement is narration, not the answer"
    nudged = script.sent[1][-1]
    assert nudged["role"] == "user" and "go ahead" in nudged["content"].lower()


def test_a_plain_answer_without_tools_ends_the_turn(clean, monkeypatch):
    session_id, seq, script = _started(monkeypatch, [_say("A counts matrix has one row per gene.")])
    assert _turn(session_id, seq).state == "answered" and len(script.sent) == 1


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
