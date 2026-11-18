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


def test_a_reached_usage_limit_says_so_and_when_it_resets():
    """Walk 2026-11-16: a subscription's usage limit came back as MA0007 "rejected, or could not
    be reached", and the builder offered a Retry that could not work for hours. The provider's
    body names when the window resets; the message says that time."""
    from comeni_ai.client import _limited

    body = ('RateLimitError: {"error":{"type":"usage_limit_reached","message":"The usage limit '
            'has been reached","resets_at":1794868080,"resets_in_seconds":10510}}')
    assert _limited(Exception(body)) == "the model's usage limit is reached; it resets at 22:28 UTC"
    assert _limited(Exception("429 Too Many Requests")) == "the model's usage limit is reached"


def _sent(monkeypatch, model: str, cache_key: str | None) -> dict:
    """What `converse` hands LiteLLM for `model`, without calling a provider."""
    import litellm
    from comeni_ai.client import LiteLLMTransport

    seen = {}

    def completion(**kwargs):
        seen.update(kwargs)
        return _response('{"a": 2}')

    monkeypatch.setattr(litellm, "completion", completion)
    LiteLLMTransport().converse(ModelAccess(model=model), [{"role": "user", "content": "hi"}],
                                [ADD], cache_key=cache_key)
    return seen


def test_an_openai_shaped_route_is_told_which_conversation_a_call_continues(monkeypatch):
    """#555. LiteLLM gave each ChatGPT-subscription call its own session id (the per-call
    `litellm_call_id`), so every round looked like a new conversation to the provider's prompt
    cache. The caller's stable key goes as `litellm_session_id` there and as
    `prompt_cache_key` to OpenAI; a provider that takes neither is sent neither."""
    key = "c0ffee" * 5
    chatgpt = _sent(monkeypatch, "chatgpt/gpt-6.1-sol", key)
    assert chatgpt.get("litellm_session_id") == key and "prompt_cache_key" not in chatgpt
    openai = _sent(monkeypatch, "openai/gpt-6.1", key)
    assert openai.get("prompt_cache_key") == key and "litellm_session_id" not in openai
    claude = _sent(monkeypatch, "anthropic/claude-sonnet-5", key)
    assert "prompt_cache_key" not in claude and "litellm_session_id" not in claude
    unkeyed = _sent(monkeypatch, "chatgpt/gpt-6.1-sol", None)
    assert "litellm_session_id" not in unkeyed


def test_a_scripted_transport_keeps_the_cache_key_it_was_sent():
    script = ScriptedAgentTransport([AgentReply(text="ok")])
    script.converse(ACCESS, [{"role": "user", "content": "hi"}], [ADD], cache_key="k")
    assert script.keys == ["k"]
