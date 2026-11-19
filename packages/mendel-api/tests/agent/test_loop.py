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
    return _call("reply", message=text)


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
        ("tool", "read_goal", True), ("tool", "reply", True), ("message", None, None)]
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
            if name == "read_goal":
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
        ("message", True, None), ("tool", None, False), ("tool", None, False),
        ("message", False, None)]
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
    tools = [b for b in _turn(session_id, seq).blocks if b["kind"] == "tool"
             and b["name"] != "reply"]
    assert [(t["name"], t.get("node")) for t in tools] == [
        ("resolve", None), ("read_step", "star_align"), ("read_goal", None)]


def test_a_step_link_is_only_a_step_the_pipeline_has(clean, monkeypatch):
    """Plan 2 review I6: a refused call, or a node the pipeline does not have, links nothing; and
    a lookup that fails ends the turn failed, never stuck working."""
    session_id, seq, _ = _started(monkeypatch, [
        _call("read_step", node="star_alignn"), _say("Read it.")])
    [line] = [b for b in _turn(session_id, seq).blocks if b["kind"] == "tool"
             and b["name"] != "reply"]
    assert line.get("node") is None

    def broken(*args):
        raise RuntimeError("bad blueprint")

    monkeypatch.setattr(loop, "_node_of", broken)
    session_id, seq, _ = _started(monkeypatch, [_call("read_goal"), _say("never")])
    turn = _turn(session_id, seq)
    assert turn.state == "failed" and not any(b.get("running") for b in turn.blocks)


def test_a_tool_free_reply_is_the_answer_and_ends_the_turn(clean, monkeypatch):
    """Builder protocol v4 (operator override, 2026-11-17): a reply without tools is the
    answer. No reminder is inserted and no second call is made, whatever its wording."""
    text = ("I'm checking the uploaded yeast samples and the current analysis before choosing "
            "a gene-counting workflow.")
    session_id, seq, script = _started(monkeypatch, [AgentReply(text=text)])
    turn = _turn(session_id, seq)
    assert turn.state == "answered" and len(script.sent) == 1
    assert [(b["kind"], b["text"], b["narration"]) for b in turn.blocks] == [
        ("message", text, False)]
    assert script.tool_choices == [None], "required tool choice is not sent"


def test_an_explicit_reply_ends_the_turn(clean, monkeypatch):
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
        def converse(self, access, messages, tools, *, tool_choice=None, cache_key=None):
            raise ModelUnavailableError(coded("MA0007", "fake/test: unreachable"))

    monkeypatch.setattr(loop, "model_access", lambda: object())
    session_id = loop.start_session(drafts.create(DraftGraph(), "agent", "ana"), who="ana")
    seq = loop.add_person_turn(session_id, "hello")
    loop.run_turn(session_id, seq, transport=Down())
    turn = _turn(session_id, seq)
    assert turn.state == "failed"
    assert turn.blocks[-1]["notice"] == "refusal" and turn.blocks[-1]["code"] == "MA0007"


def test_a_reached_usage_limit_says_so_rather_than_did_not_answer(clean, monkeypatch):
    """Walk 2026-11-16: the person read "The AI did not answer. Try again." for a limit that
    lasts hours."""
    class Limited:
        def converse(self, access, messages, tools, *, tool_choice=None, cache_key=None):
            raise ModelUnavailableError(coded(
                "MA0010", "the model's usage limit is reached; it resets at 22:28 UTC"))

    monkeypatch.setattr(loop, "model_access", lambda: object())
    session_id = loop.start_session(drafts.create(DraftGraph(), "agent", "ana"), who="ana")
    seq = loop.add_person_turn(session_id, "hello")
    loop.run_turn(session_id, seq, transport=Limited())
    notice = _turn(session_id, seq).blocks[-1]
    assert notice["code"] == "MA0010"
    assert notice["text"] == (
        "The model's usage limit is reached; it resets at 22:28 UTC. Try again then.")


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


def test_each_model_call_records_protocol_v4_and_its_tool_definitions(clean, monkeypatch):
    session_id, seq, _ = _started(monkeypatch, [_call("read_goal"), _say("Here it is.")])
    with session_scope() as db:
        import json
        recorded = db.scalars(select(AiInvocation).where(
            AiInvocation.session_id == session_id).order_by(AiInvocation.started_at)).all()
    assert len(recorded) == 2
    assert all(i.prompt_id == "builder.agent.v6" and i.prompt_version == "v6" for i in recorded)
    assert all({"tool_specs", "tool_choice"} <= set(i.input_digests) for i in recorded)
    assert [json.loads(i.response)["tool_choice"] for i in recorded] == [None, None]


@pytest.mark.parametrize("message", ["", "   \n ", "x" * 16001, 42, None])
def test_invalid_reply_arguments_do_not_end_the_turn(clean, monkeypatch, message):
    session_id, seq, script = _started(monkeypatch, [
        _call("reply", message=message), _say("Valid answer."),
    ])
    turn = _turn(session_id, seq)
    assert turn.state == "answered" and len(script.sent) == 2
    assert turn.blocks[0]["name"] == "reply" and turn.blocks[0]["ok"] is False
    assert turn.blocks[-1]["text"] == "Valid answer." and not turn.blocks[-1]["narration"]


def test_reply_preserves_multiline_text_and_stops_the_tool_batch(clean, monkeypatch):
    session_id, seq, _ = _started(monkeypatch, [AgentReply(
        text="Work completed.", calls=[
            ToolCall(id="reply", name="reply",
                     arguments={"message": "  First line.\n\nSecond line.  "}),
            ToolCall(id="never", name="read_goal", arguments={}),
        ])])
    blocks = _turn(session_id, seq).blocks
    assert [b["name"] for b in blocks if b["kind"] == "tool"] == ["reply"]
    assert [(b["text"], b["narration"]) for b in blocks if b["kind"] == "message"] == [
        ("Work completed.", True), ("First line.\n\nSecond line.", False)]


def test_tool_rounds_still_stop_at_the_token_limit(clean, monkeypatch):
    from comeni_ai.client import Usage

    monkeypatch.setattr(settings, "agent_max_tokens", 10)
    usage = Usage(model="fake/test", duration_ms=1, input_tokens=11, output_tokens=1)
    reply = _call("read_goal").model_copy(update={"usage": usage})
    session_id, seq, script = _started(monkeypatch, [reply])
    assert len(script.sent) == 1
    assert _turn(session_id, seq).blocks[-1]["notice"] == "limit"


def test_a_sessions_turns_run_one_at_a_time(clean, monkeypatch):
    """#505: each message queues a turn, and with two AI jobs a worker took the second while
    the first was still writing to the draft. A turn now waits for the one before it."""
    import threading

    import sqlalchemy as sa
    from mendel_api.db import engine

    monkeypatch.setattr(loop, "model_access", lambda: object())
    session_id = loop.start_session(drafts.create(DraftGraph(), "agent", "ana"), who="ana")
    seq = loop.add_person_turn(session_id, "gene counts")
    done = threading.Event()
    with engine.connect() as first:  # the turn before, still running
        first.execute(sa.text("SELECT pg_advisory_lock(:k)"), {"k": loop.turn_key(session_id)})
        worker = threading.Thread(target=lambda: (
            loop.run_turn(session_id, seq, transport=ScriptedAgentTransport([_say("done")])),
            done.set()))
        worker.start()
        assert not done.wait(1.0), "the turn ran while the one before held the session"
        first.execute(sa.text("SELECT pg_advisory_unlock(:k)"), {"k": loop.turn_key(session_id)})
    worker.join(10)
    assert done.is_set() and _turn(session_id, seq).state == "answered"


def test_every_call_of_a_session_names_the_same_conversation(clean, monkeypatch):
    """#555. Each round and each turn of one session sends the provider the same cache key, so
    its prompt cache finds the prefix of the last round; another session sends another. The
    key is a digest: the session id itself does not leave."""
    session_id, seq, script = _started(monkeypatch, [_call("read_goal"), _say("Built")])
    again = loop.add_person_turn(session_id, "and now?")
    later = ScriptedAgentTransport([_say("Done")])
    loop.run_turn(session_id, again, transport=later)
    keys = script.keys + later.keys
    assert len(keys) == 3 and len(set(keys)) == 1 and keys[0], keys
    assert session_id not in keys[0]
    other, _, elsewhere = _started(monkeypatch, [_say("Hi")])
    assert elsewhere.keys[0] != keys[0]


def test_a_long_conversation_sends_only_its_recent_turns(clean, monkeypatch):
    """#558. Every earlier turn went to the model on every call, never bounded, so a long
    conversation grew without limit (about 600 tokens a turn in the audit's simulation). Only
    the last `agent_history_turns` turns are sent; the system prompt then says the rest is in
    the decisions, the same words however many were left out, so the cached prefix holds."""
    monkeypatch.setattr(settings, "agent_history_turns", 2)
    session_id, _, _ = _started(monkeypatch, [_say("First answer")], text="the first thing")
    for words in ("the second thing", "the third thing"):
        seq = loop.add_person_turn(session_id, words)
        loop.run_turn(session_id, seq, transport=ScriptedAgentTransport([_say("ok")]))
    last = loop.add_person_turn(session_id, "and now")
    script = ScriptedAgentTransport([_say("done")])
    loop.run_turn(session_id, last, transport=script)
    [sent] = script.sent
    system, *rest = sent
    assert system["role"] == "system" and system["content"].endswith(loop.EARLIER)
    said = [m["content"] for m in rest]
    assert "the first thing" not in said and said[-1] == "and now", said
    assert len(rest) == 2, "the last two turns, the person's new words among them"

    monkeypatch.setattr(settings, "agent_history_turns", 100)
    again = loop.add_person_turn(session_id, "once more")
    whole = ScriptedAgentTransport([_say("done")])
    loop.run_turn(session_id, again, transport=whole)
    assert not whole.sent[0][0]["content"].endswith(loop.EARLIER)
    assert "the first thing" in [m["content"] for m in whole.sent[0][1:]]
