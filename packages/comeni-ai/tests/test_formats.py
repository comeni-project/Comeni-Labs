"""Which reply format a model gets, and what each one sends (#194)."""

import pytest
from comeni_ai.formats import (
    HOSTED_ENUM_CAP,
    AnthropicFormat,
    InPrompt,
    OllamaFormat,
    OpenAIFormat,
    reply_format_for,
    with_choices,
)
from pydantic import BaseModel

SCHEMA = {
    "type": "object",
    "properties": {
        "asks": {"type": "string", "maxLength": 20, "title": "Asks"},
        "already_option": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": None},
    },
    "required": ["asks"],
}


def test_ollama_is_enforced_and_verified():
    for model in ("ollama_chat/gemma3:12b", "ollama/llama3"):
        chosen = reply_format_for(model, enforcing=True)
        assert isinstance(chosen, OllamaFormat) and not chosen.in_prompt


def test_unverified_and_unknown_providers_get_the_schema_in_the_prompt():
    for model in ("openai/gpt-4o", "anthropic/claude-x", "groq/llama3", "gpt-4o"):
        assert isinstance(reply_format_for(model, enforcing=True), InPrompt), model


def test_a_transport_that_cannot_pass_a_format_gets_the_prompt():
    assert isinstance(reply_format_for("ollama_chat/gemma3:12b", enforcing=False), InPrompt)


def test_in_prompt_sends_nothing_extra():
    assert InPrompt().extra(SCHEMA, "AskedGap") == {} and InPrompt().in_prompt


def test_ollama_sends_the_schema_as_the_response_format():
    sent = OllamaFormat().extra(SCHEMA, "AskedGap")
    assert sent["response_format"]["type"] == "json_schema"
    assert sent["response_format"]["json_schema"]["name"] == "AskedGap"
    assert sent["response_format"]["json_schema"]["schema"] == SCHEMA


def test_openai_rewrites_for_strict_mode():
    schema = OpenAIFormat().extra(SCHEMA, "AskedGap")["response_format"]["json_schema"]
    body = schema["schema"]
    assert schema["strict"] is True
    assert sorted(body["required"]) == ["already_option", "asks"]
    assert body["additionalProperties"] is False
    assert "default" not in body["properties"]["already_option"]


def test_openai_makes_an_optional_field_nullable_rather_than_dropping_it():
    body = OpenAIFormat().extra(
        {"type": "object", "properties": {"n": {"type": "integer", "default": 3}}},
        "S",
    )["response_format"]["json_schema"]["schema"]
    assert {"type": "null"} in body["properties"]["n"]["anyOf"]


def test_openai_over_the_cap_answers_as_in_prompt():
    values = [str(i) for i in range(HOSTED_ENUM_CAP + 1)]
    big = {"type": "object", "properties": {"x": {"enum": values}}}
    assert OpenAIFormat().extra(big, "S") == {}
    assert OpenAIFormat().over_cap(big)


def test_the_scaffolds_are_not_verified_yet():
    assert not OpenAIFormat().verified and not AnthropicFormat().verified
    assert OllamaFormat().verified


# ── allowed values (spec §6) ──────────────────────────────────────────────────────────────

class _Item(BaseModel):
    subject: str


class _Shape(BaseModel):
    want: list[str]
    stated: list[_Item] = []
    already_option: str | None = None


def _schema():
    return _Shape.model_json_schema()


def test_a_list_field_gets_an_enum_on_its_items():
    out = with_choices(_schema(), {"want": ["counts.matrix", "qc.report"]})
    assert out["properties"]["want"]["items"]["enum"] == ["counts.matrix", "qc.report"]


def test_a_field_behind_a_ref_gets_its_enum_and_the_original_is_untouched():
    original = _schema()
    out = with_choices(original, {"stated.subject": ["paired"]})
    assert out["$defs"]["_Item"]["properties"]["subject"]["enum"] == ["paired"]
    assert "enum" not in original["$defs"]["_Item"]["properties"]["subject"]


def test_a_nullable_field_keeps_null_as_its_way_out():
    out = with_choices(_schema(), {"already_option": ["yes", "no"]})
    branches = out["properties"]["already_option"]["anyOf"]
    assert {"type": "null"} in branches
    assert any(b.get("enum") == ["yes", "no"] for b in branches)


def test_an_unknown_path_raises_rather_than_constraining_nothing():
    with pytest.raises(KeyError, match="nope"):
        with_choices(_schema(), {"nope": ["x"]})
