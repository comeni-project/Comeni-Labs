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


def test_cached_input_tokens_are_read_when_the_provider_reports_them():
    """Walk 2026-11-15: the agent's calls recorded no cached tokens on any route, so a provider
    that caches the repeated prompt would still show it as paid in full."""
    openai = {"choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
              "usage": {"prompt_tokens": 4000, "completion_tokens": 5,
                        "prompt_tokens_details": {"cached_tokens": 3500}}}
    assert reply_of(ACCESS, openai, started=0.0).usage.cached_tokens == 3500
    anthropic = {"choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
                 "usage": {"prompt_tokens": 4000, "completion_tokens": 5,
                           "cache_read_input_tokens": 3200}}
    assert reply_of(ACCESS, anthropic, started=0.0).usage.cached_tokens == 3200


def test_a_claude_model_is_asked_to_cache_the_system_prompt():
    """Walk 2026-11-15: every round resends the prompt and the tools. Claude caches only what a
    request marks; the system prompt is marked, and the tools before it are cached with it.
    Other providers are sent the messages as they are, and the caller's list is not changed."""
    from comeni_ai.client import _cacheable

    messages = [{"role": "system", "content": "the prompt"}, {"role": "user", "content": "hi"}]
    marked = _cacheable("anthropic/claude-sonnet-5", messages)
    assert marked[0]["content"] == [{"type": "text", "text": "the prompt",
                                     "cache_control": {"type": "ephemeral"}}]
    assert marked[1] == messages[1] and messages[0]["content"] == "the prompt"
    assert _cacheable("chatgpt/gpt-6.1-sol", messages) is messages
