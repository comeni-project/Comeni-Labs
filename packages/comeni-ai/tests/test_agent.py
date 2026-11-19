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
    assert messages[0]["content"] == "the prompt" and messages[1]["content"] == "hi"
    assert _cacheable("chatgpt/gpt-6.1-sol", messages) is messages


def test_each_round_marks_where_the_next_one_can_read_from_the_cache():
    """#554. Only the system prompt was marked, so every later round of a turn re-sent the
    history and the turn's tool results uncached. The last user or tool message is marked too:
    the next round, which adds to the end, reads everything before it from the cache. Claude
    through OpenRouter is marked as well; it matched none of the prefixes."""
    from comeni_ai.client import _cacheable

    mark = {"type": "ephemeral"}
    rounds = [
        {"role": "system", "content": "the prompt"},
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": None, "tool_calls": [{"id": "c1"}]},
        {"role": "tool", "tool_call_id": "c1", "content": "the result"},
    ]
    for model in ("anthropic/claude-sonnet-5", "openrouter/anthropic/claude-sonnet-5"):
        marked = _cacheable(model, rounds)
        assert marked[0]["content"][0]["cache_control"] == mark
        assert marked[-1]["content"] == [{"type": "text", "text": "the result",
                                          "cache_control": mark}]
        assert marked[-1]["tool_call_id"] == "c1"
        assert marked[1] == rounds[1] and marked[2] == rounds[2], "only the last is marked"
    assert rounds[-1]["content"] == "the result", "the caller's list is not changed"
    asked = _cacheable("anthropic/claude-sonnet-5", rounds[:2])
    assert asked[-1]["content"] == [{"type": "text", "text": "hi", "cache_control": mark}]
    ending_in_a_call = _cacheable("anthropic/claude-sonnet-5", rounds[:3])
    assert ending_in_a_call[-1] == rounds[2], "an assistant's tool call is left as it is"


def test_a_reached_usage_limit_says_so_and_when_it_resets():
    """Walk 2026-11-16: a subscription's usage limit came back as MA0007 "rejected, or could not
    be reached", and the builder offered a Retry that could not work for hours. The provider's
    body names when the window resets; the message says that time."""
    from comeni_ai.client import _limited

    body = ('RateLimitError: {"error":{"type":"usage_limit_reached","message":"The usage limit '
            'has been reached","resets_at":1794868080,"resets_in_seconds":10510}}')
    assert _limited(Exception(body)) == "the model's usage limit is reached; it resets at 22:28 UTC"
    assert _limited(Exception("429 Too Many Requests")) == "the model's usage limit is reached"


def test_an_openai_shaped_route_is_told_which_conversation_a_call_continues():
    """#555. LiteLLM gave each ChatGPT-subscription call its own session id (the per-call
    `litellm_call_id`), so every round looked like a new conversation to the provider's prompt
    cache. The caller's stable key goes as `litellm_session_id` there and as
    `prompt_cache_key` to OpenAI; a provider that takes neither is sent neither. `converse`
    spreads exactly this into `litellm.completion`; the live transport is not named in a test
    (`tests/guards/test_no_live_model.py`)."""
    from comeni_ai.client import _continuing

    key = "c0ffee" * 5
    assert _continuing("chatgpt/gpt-6.1-sol", key) == {"litellm_session_id": key}
    assert _continuing("openai/gpt-6.1", key) == {"prompt_cache_key": key}
    assert _continuing("anthropic/claude-sonnet-5", key) == {}
    assert _continuing("chatgpt/gpt-6.1-sol", None) == {}

def test_a_scripted_transport_keeps_the_cache_key_it_was_sent():
    script = ScriptedAgentTransport([AgentReply(text="ok")])
    script.converse(ACCESS, [{"role": "user", "content": "hi"}], [ADD], cache_key="k")
    assert script.keys == ["k"]
