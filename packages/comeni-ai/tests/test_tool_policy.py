"""Exercise the provider boundary with mocked completions only."""

import litellm
import pytest
from comeni_ai import ModelAccess
from comeni_ai.tool_policy import complete

ACCESS = ModelAccess(model="openai/test")


def parameters(access=ACCESS):
    return {
        "model": access.model,
        "messages": [{"role": "user", "content": "hello"}],
        "tools": [{"type": "function", "function": {"name": "reply"}}],
    }


@pytest.mark.parametrize(
    "model,base,supported,required,expected",
    [
        ("openai/test", None, ["tools", "tool_choice"], True, "required"),
        ("anthropic/test", None, ["tools", "tool_choice"], True, "required"),
        ("chatgpt/test", None, ["tools", "tool_choice"], True, "required"),
        ("openai/test", "https://api.openai.com/v1", ["tool_choice"], True, "required"),
        ("openai/test", None, ["tools"], True, None),
        ("openai/test", None, ["tool_choice"], False, None),
        ("ollama_chat/test", None, ["tool_choice"], True, None),
        ("openai/local", "http://localhost:1234/v1", ["tool_choice"], True, None),
    ],
)
def test_required_choice_is_optional_and_capability_aware(
    monkeypatch,
    model,
    base,
    supported,
    required,
    expected,
):
    sent = []
    monkeypatch.setattr(litellm, "get_supported_openai_params", lambda **kw: supported)
    monkeypatch.setattr(litellm, "completion", lambda **kw: (sent.append(kw), "response")[1])
    access = ModelAccess(model=model, base_url=base)
    result, effective = complete(access, parameters(access), required=required, unsupported=set())
    assert result == "response" and effective == expected
    assert len(sent) == 1 and sent[0].get("tool_choice") == expected
    if expected is None:
        assert "tool_choice" not in sent[0]


def test_a_specific_unsupported_parameter_retries_once_and_remembers_the_endpoint(monkeypatch):
    sent = []
    monkeypatch.setattr(litellm, "get_supported_openai_params", lambda **kw: ["tool_choice"])

    def provider(**kw):
        sent.append(kw)
        if "tool_choice" in kw:
            raise litellm.UnsupportedParamsError(
                "unsupported tool_choice=required", "openai", "test"
            )
        return "response"

    monkeypatch.setattr(litellm, "completion", provider)
    unsupported = set()
    assert complete(ACCESS, parameters(), required=True, unsupported=unsupported) == (
        "response",
        None,
    )
    assert len(sent) == 2 and "tool_choice" not in sent[1]
    complete(ACCESS, parameters(), required=True, unsupported=unsupported)
    assert len(sent) == 3 and "tool_choice" not in sent[2]
    assert unsupported == {(ACCESS.model, "")}
    # A different endpoint/model does not inherit that negative capability.
    other = ModelAccess(model="openai/other")
    complete(other, parameters(other), required=True, unsupported=unsupported)
    assert sent[3]["tool_choice"] == "required" and len(sent) == 5


@pytest.mark.parametrize(
    "failure",
    [
        litellm.BadRequestError("invalid tool schema", "openai", "test"),
        litellm.AuthenticationError("bad credentials", "openai", "test"),
        litellm.UnsupportedParamsError("unsupported temperature", "openai", "test"),
    ],
)
def test_other_provider_errors_are_not_retried(monkeypatch, failure):
    sent = []
    monkeypatch.setattr(litellm, "get_supported_openai_params", lambda **kw: ["tool_choice"])

    def provider(**kw):
        sent.append(kw)
        raise failure

    monkeypatch.setattr(litellm, "completion", provider)
    with pytest.raises(type(failure)):
        complete(ACCESS, parameters(), required=True, unsupported=set())
    assert len(sent) == 1
