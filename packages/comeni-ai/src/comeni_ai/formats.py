"""Provider-specific ways to communicate a reply schema.

Unverified providers receive the schema in the prompt. Verified provider formats may enforce it
server-side, but :class:`comeni_ai.client.Client` still validates every returned body locally.
"""

import copy

HOSTED_ENUM_CAP = 500
"""Maximum allowed values before hosted strict schemas fall back to in-prompt mode."""


class ReplyFormat:
    """The base: what a call adds to the request, and whether the schema is in the prompt."""

    name = "in_prompt"
    verified = True
    in_prompt = True

    def extra(self, schema: dict, shape_name: str) -> dict:
        """The keyword arguments added to `litellm.completion`. None for the prompt."""
        return {}


class InPrompt(ReplyFormat):
    """Always-available format that writes the schema into the prompt."""


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
    """Ollama JSON-schema format passed through LiteLLM and verified by provider probes."""

    name = "ollama"
    verified = True


class OpenAIFormat(_Enforced):
    """OpenAI strict-mode adapter; unit-tested but not provider-verified."""

    name = "openai"
    verified = False

    def over_cap(self, schema: dict) -> bool:
        return _enum_values(schema) > HOSTED_ENUM_CAP

    def extra(self, schema: dict, shape_name: str) -> dict:
        return {} if self.over_cap(schema) else super().extra(schema, shape_name)

    def _body(self, schema: dict) -> dict:
        return _strict(copy.deepcopy(schema))


class AnthropicFormat(_Enforced):
    """Anthropic response-format adapter; unit-tested but not provider-verified.

    LiteLLM represents this format as a tool, so verification must also cover cache markers and
    per-request allowed values.
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


def with_choices(schema: dict, choices: dict[str, list]) -> dict:
    """Return a copy of ``schema`` with allowed values applied at named field paths.

    Nullable fields retain their null branch. Unknown paths raise rather than silently leaving
    a request unconstrained.
    """
    out = copy.deepcopy(schema)
    for path, values in choices.items():
        if not values:
            # Empty array choices allow no items. Empty scalar enums are avoided because some
            # servers reject that schema, so a scalar remains unconstrained.
            array = _array_on(out, out, path.split("."))
            if array is not None:
                array["maxItems"] = 0
            continue
        for target in _targets(out, out, path.split("."), path):
            target["enum"] = list(values)
    return out


def _targets(root: dict, node: dict, parts: list[str], path: str) -> list[dict]:
    node = _deref(root, node)
    if node.get("type") == "array":
        return _targets(root, node["items"], parts, path)
    if "anyOf" in node:
        return [
            target
            for branch in node["anyOf"]
            if branch.get("type") != "null"
            for target in _targets(root, branch, parts, path)
        ]
    if not parts:
        return [node]
    properties = node.get("properties", {})
    if parts[0] not in properties:
        raise KeyError(f"{path}: no field {parts[0]!r} here")
    return _targets(root, properties[parts[0]], parts[1:], path)


def _array_on(root: dict, node: dict, parts: list[str], found: dict | None = None):
    """Return the nearest array along a field path, if one exists."""
    node = _deref(root, node)
    if node.get("type") == "array":
        found = node
        node = _deref(root, node["items"])
    if "anyOf" in node:
        branches = [b for b in node["anyOf"] if b.get("type") != "null"]
        return _array_on(root, branches[0], parts, found) if branches else found
    if not parts:
        return found
    properties = node.get("properties", {})
    if parts[0] not in properties:
        raise KeyError(f"{'.'.join(parts)}: no field {parts[0]!r} here")
    return _array_on(root, properties[parts[0]], parts[1:], found)


def _deref(root: dict, node: dict) -> dict:
    ref = node.get("$ref")
    if ref is None:
        return node
    return root["$defs"][ref.rsplit("/", 1)[-1]]
