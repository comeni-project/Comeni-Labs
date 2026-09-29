"""How a provider is told the shape of a reply (#194).

**The schema is either written into the prompt or enforced by the server, never trusted.**
Every reply is still validated by `Client` against its shape: a format guarantees the shape a
model writes, never what it means. `InPrompt` is the behaviour before #194 and the default for
anything not verified — a provider's format is used only after a walk against it, because each
one honours `response_format` differently (LiteLLM's own `supports_response_schema` said *False*
for `ollama_chat/` while Ollama honoured the format).

Why at all: shown the schema as text, gemma3:12b answered with the schema itself — 4 of 18
phrasing calls, and 12 of 12 once its docstrings were stripped. Enforced, all three local models
answered in shape with no schema in the prompt at all.
"""

import copy

HOSTED_ENUM_CAP = 500
"""Past this many allowed values in one schema, a hosted provider is sent the schema in the
prompt instead: a strict schema over its limits is rejected rather than trimmed."""


class ReplyFormat:
    """The base: what a call adds to the request, and whether the schema is in the prompt."""

    name = "in_prompt"
    verified = True
    in_prompt = True

    def extra(self, schema: dict, shape_name: str) -> dict:
        """The keyword arguments added to `litellm.completion`. None for the prompt."""
        return {}


class InPrompt(ReplyFormat):
    """The schema written into the prompt, as before #194. Always available."""


class _Enforced(ReplyFormat):
    in_prompt = False

    def _body(self, schema: dict) -> dict:
        return schema

    def extra(self, schema: dict, shape_name: str) -> dict:
        return {
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": shape_name, "schema": self._body(schema), "strict": True},
            }
        }


class OllamaFormat(_Enforced):
    """Ollama's `format`, through LiteLLM. Verified by the 2026-09-29 probe on three models."""

    name = "ollama"
    verified = True


class OpenAIFormat(_Enforced):
    """OpenAI strict mode. **A scaffold**: unit-tested, not verified against the provider."""

    name = "openai"
    verified = False

    def over_cap(self, schema: dict) -> bool:
        return _enum_values(schema) > HOSTED_ENUM_CAP

    def extra(self, schema: dict, shape_name: str) -> dict:
        return {} if self.over_cap(schema) else super().extra(schema, shape_name)

    def _body(self, schema: dict) -> dict:
        return _strict(copy.deepcopy(schema))


class AnthropicFormat(_Enforced):
    """Sent as `response_format`, which LiteLLM turns into a tool. **A scaffold**, not verified.

    When verifying: the tool counts as prompt, so a per-question allowed list splits the cache
    per question, and part 3's cache markers must still reach the system blocks.
    """

    name = "anthropic"
    verified = False

    def extra(self, schema: dict, shape_name: str) -> dict:
        if _enum_values(schema) > HOSTED_ENUM_CAP:
            return {}
        return super().extra(schema, shape_name)


_BY_PREFIX: dict[str, type[_Enforced]] = {
    "ollama_chat/": OllamaFormat,
    "ollama/": OllamaFormat,
    "openai/": OpenAIFormat,
    "anthropic/": AnthropicFormat,
}


def reply_format_for(model: str, *, enforcing: bool) -> ReplyFormat:
    """The format for `model`: `InPrompt` unless the transport can pass one (`enforcing`) and
    the provider's format is verified."""
    if not enforcing:
        return InPrompt()
    for prefix, format_type in _BY_PREFIX.items():
        if model.startswith(prefix):
            chosen = format_type()
            return chosen if chosen.verified else InPrompt()
    return InPrompt()


def _enum_values(node: object) -> int:
    if isinstance(node, dict):
        own = len(node["enum"]) if isinstance(node.get("enum"), list) else 0
        return own + sum(_enum_values(v) for k, v in node.items() if k != "enum")
    if isinstance(node, list):
        return sum(_enum_values(item) for item in node)
    return 0


def _strict(node: object) -> object:
    """OpenAI strict mode: every property required, an optional one nullable, nothing extra."""
    if isinstance(node, list):
        return [_strict(item) for item in node]
    if not isinstance(node, dict):
        return node
    node = {k: _strict(v) for k, v in node.items() if k != "default"}
    if node.get("type") == "object" and "properties" in node:
        required = set(node.get("required", []))
        for key, prop in node["properties"].items():
            if key not in required and not _allows_null(prop):
                node["properties"][key] = {"anyOf": [prop, {"type": "null"}]}
        node["required"] = sorted(node["properties"])
        node["additionalProperties"] = False
    return node


def _allows_null(prop: dict) -> bool:
    return prop.get("type") == "null" or any(
        branch.get("type") == "null" for branch in prop.get("anyOf", [])
    )
