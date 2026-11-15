"""A conversation with tools: the builder agent's transport (#463, the builder agent)."""

import pytest
from comeni_ai import ModelAccess
from comeni_ai.agent import AgentReply, ScriptedAgentTransport, ToolCall, ToolSpec
from comeni_ai.client import reply_of

ACCESS = ModelAccess(model="fake/test")
ADD = ToolSpec(name="add", description="Add two numbers",
               parameters={"type": "object", "properties": {"a": {"type": "number"}}})


def test_a_scripted_transport_answers_in_order_and_keeps_what_it_was_sent():
    first = AgentReply(text="", calls=[ToolCall(id="c1", name="add", arguments={"a": 2})])
    second = AgentReply(text="4", calls=[])
    script = ScriptedAgentTransport([first, second])
    assert script.converse(ACCESS, [{"role": "user", "content": "2+2?"}], [ADD]) == first
    asked = [{"role": "user", "content": "2+2?"}, {"role": "tool", "content": "4"}]
    assert script.converse(ACCESS, asked, [ADD]) == second
    assert script.sent[1] == asked
    with pytest.raises(AssertionError, match="the script ran out"):
        script.converse(ACCESS, asked, [ADD])


def _response(arguments: str, content=None) -> dict:
    return {
        "model": "fake/test",
        "choices": [{"finish_reason": "tool_calls", "message": {
            "content": content,
            "tool_calls": [{"id": "c1", "type": "function",
                            "function": {"name": "add", "arguments": arguments}}]}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 2},
    }


def test_a_native_tool_call_is_read_into_a_tool_call():
    reply = reply_of(ACCESS, _response('{"a": 2, "b": 2}'), started=0.0)
    assert reply.calls == [ToolCall(id="c1", name="add", arguments={"a": 2, "b": 2})]
    assert reply.text == ""
    assert reply.refusal is None
    assert reply.usage is not None and reply.usage.input_tokens == 10


def test_malformed_tool_arguments_are_a_coded_refusal():
    reply = reply_of(ACCESS, _response("{not json"), started=0.0)
    assert reply.calls[0].arguments == {}
    assert reply.text == ""
    assert reply.refusal is not None and reply.refusal.startswith("MA0004")


def test_a_tool_spec_is_sent_in_the_providers_shape():
    assert ADD.as_provider() == {"type": "function", "function": {
        "name": "add", "description": "Add two numbers", "parameters": ADD.parameters}}
