"""Validated generation and the provider transport beneath it.

Every entry point validates returned JSON against a caller-supplied Pydantic model. Invalid or
empty replies return ``None`` with a coded explanation in ``Client.last_refusal``; replies are
never repaired into partial values. Provider-enforced response formats may move a schema out of
the prompt, but local validation still runs for every response.

The transport protocols form the network seam used by real providers, fakes, and recorded
fixtures.
"""

import json
import re
from typing import Protocol, TypeVar, runtime_checkable

from comeni_core.diagnostics import coded
from pydantic import BaseModel, ConfigDict, ValidationError

from comeni_ai.access import ModelAccess, NoModelError
from comeni_ai.formats import InPrompt, ReplyFormat, reply_format_for, with_choices

T = TypeVar("T", bound=BaseModel)

_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.S)


__all__ = [
    "Client",
    "LiteLLMTransport",
    "Metered",
    "ModelUnavailableError",
    "NoModelError",
    "Transport",
    "Usage",
]


class ModelUnavailableError(ValueError):
    """The provider rejected credentials or the request, or could not be reached."""


@runtime_checkable
class Transport(Protocol):
    """Minimal prompt-delivery interface implemented by real and test transports."""

    def send(
        self,
        access: ModelAccess,
        prompt: "str | list[dict]",
        response_format: dict | None = None,
    ) -> str:
        """Send a prompt, optionally with a provider response format."""
        ...


class Usage(BaseModel):
    """Provider-reported metadata for one completed call.

    Optional counters remain ``None`` when the provider omits them. ``model`` records the model
    that answered, which may be a resolved snapshot rather than the requested alias.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    model: str
    duration_ms: int
    input_tokens: int | None = None
    output_tokens: int | None = None
    cached_tokens: int | None = None
    """Input tokens served from provider cache, or ``None`` when unreported."""
    finish_reason: str | None = None


@runtime_checkable
class Metered(Protocol):
    """Optional transport interface that returns provider usage with the response."""

    def deliver(
        self,
        access: ModelAccess,
        prompt: "str | list[dict]",
        response_format: dict | None = None,
    ) -> tuple[str, Usage]: ...


class Client:
    def __init__(self, access: ModelAccess, transport: "Transport | None" = None) -> None:
        self.access = access
        self._transport = transport if transport is not None else LiteLLMTransport()
        self.last_refusal: str | None = None
        """Coded reason the most recent call returned ``None``; cleared on success."""
        self.last_usage: Usage | None = None
        """Usage for the most recent call, cleared before each exchange."""
        self.last_response: str | None = None
        """Raw reply from the most recent call, retained even when validation rejects it."""
        self.last_format: str | None = None
        """Reply-format name used by the most recent call."""
        self.last_prompt: str | None = None
        """The exact text sent, for the caller that has to store a digest of it.

        `_prompt` composes the schema and the evidence around the instruction, so the
        instruction a caller passed in is *not* what crossed the wire — and a stored digest of
        the wrong string cannot be compared against a re-render later.
        """

    def generate(
        self,
        instruction: str,
        shape: type[T],
        evidence: list[str],
        choices: dict[str, list] | None = None,
    ) -> T | None:
        """Compose a prompt, send it, and validate the response as ``shape``."""
        chosen, schema = self._format(shape, choices)
        prompt = _prompt(instruction, schema, evidence, in_prompt=chosen.in_prompt)
        return self._send(prompt, prompt, shape, chosen, schema)

    def respond(
        self, prompt: str, shape: type[T], choices: dict[str, list] | None = None
    ) -> T | None:
        """Send an already composed prompt and validate the response as ``shape``.

        The prompt text is preserved. A provider response format may be attached separately.
        Call metadata is updated in the same way as :meth:`generate`.
        """
        chosen, schema = self._format(shape, choices)
        return self._send(prompt, prompt, shape, chosen, schema)

    def chat(
        self, system: str, user: str, shape: type[T], choices: dict[str, list] | None = None
    ) -> T | None:
        """Send a cacheable system prefix and a per-call user message.

        ``last_prompt`` stores both parts as one string so callers can digest the complete
        request. The user message ends with the JSON-only instruction.
        """
        chosen, schema = self._format(shape, choices)
        messages = _messages(self.access, system, user, schema, in_prompt=chosen.in_prompt)
        sent = "\n\n".join(_text_of(m["content"]) for m in messages)
        return self._send(messages, sent, shape, chosen, schema)

    def _format(
        self, shape: type[BaseModel], choices: dict[str, list] | None
    ) -> tuple[ReplyFormat, dict]:
        """Select the reply format and apply any server-enforced allowed values.

        Transports without format support retain the schema in the prompt. A format that cannot
        represent the schema also falls back to :class:`InPrompt`.
        """
        written = shape.model_json_schema()
        enforcing = getattr(self._transport, "enforces_formats", False)
        chosen = reply_format_for(self.access.model, enforcing=enforcing)
        # Apply allowed lists only to enforced schemas; in-prompt requests already state choices.
        schema = with_choices(written, choices) if choices and not chosen.in_prompt else written
        if not chosen.in_prompt and not chosen.extra(schema, shape.__name__):
            chosen, schema = InPrompt(), written
        self.last_format = chosen.name
        return chosen, schema

    def _send(
        self,
        payload: "str | list[dict]",
        sent: str,
        shape: type[T],
        chosen: ReplyFormat,
        schema: dict,
    ) -> T | None:
        extra = chosen.extra(schema, shape.__name__)
        if extra:
            # Include an enforced schema in the auditable prompt representation.
            sent += f"\n\n[reply format: {chosen.name}]\n" + json.dumps(
                schema, indent=2, sort_keys=True
            )
        return self._exchange(payload, sent, shape, extra.get("response_format"))

    def _exchange(
        self,
        payload: "str | list[dict]",
        sent: str,
        shape: type[T],
        response_format: dict | None = None,
    ) -> T | None:
        self._begin_exchange(sent)

        try:
            given = {"response_format": response_format} if response_format else {}
            if isinstance(self._transport, Metered):
                body, self.last_usage = self._transport.deliver(self.access, payload, **given)
            else:
                body = self._transport.send(self.access, payload, **given)
        except TimeoutError as failure:
            self.last_refusal = str(failure)
            return None
        self.last_response = body
        payload_json = _json_in(body)
        if payload_json is None:
            self.last_refusal = coded("MA0004", "the answer was empty")
            return None
        try:
            return shape.model_validate_json(payload_json)
        except ValidationError as failure:
            self.last_refusal = _why_refused(shape, failure)
            return None

    def _begin_exchange(self, sent: str) -> None:
        """Clear per-call results and retain the request about to be sent."""
        self.last_refusal = None
        self.last_usage = None
        self.last_response = None
        self.last_prompt = sent


CACHE_BREAK = "<!-- cache -->"
"""Separator between cacheable prompt blocks; the marker itself is not sent."""

_SCHEMA_INTRO = (
    "Answer with JSON only, matching this schema exactly. Output nothing else — no "
    "explanation, no commentary, no markdown outside the JSON:"
)
_CLOSING = "Answer with JSON only, matching the schema above."
_CLOSING_ENFORCED = "Answer with JSON only."


def _messages(
    access: ModelAccess, system: str, user: str, schema: dict, *, in_prompt: bool = True
) -> list[dict]:
    """Build system/user messages, including schema and supported cache markers.

    Server-enforced formats omit the schema from the prompt. Anthropic models receive explicit
    cache-control blocks; other providers receive plain text.
    """
    parts = [part.strip("\n") for part in system.split(CACHE_BREAK)]
    if in_prompt:
        written = json.dumps(schema, indent=2, sort_keys=True)
        parts[-1] = f"{parts[-1]}\n\n{_SCHEMA_INTRO}\n{written}"
    if access.model.startswith("anthropic/"):
        content: str | list[dict] = [
            {"type": "text", "text": part, "cache_control": {"type": "ephemeral"}}
            for part in parts
        ]
    else:
        content = "\n".join(parts)
    return [
        {"role": "system", "content": content},
        {
            "role": "user",
            "content": f"{user.rstrip()}\n\n{_CLOSING if in_prompt else _CLOSING_ENFORCED}",
        },
    ]


def _text_of(content: "str | list[dict]") -> str:
    return content if isinstance(content, str) else "\n".join(b["text"] for b in content)


def _prompt(instruction: str, schema: dict, evidence: list[str], *, in_prompt: bool = True) -> str:
    """Compose evidence, the instruction, and an optional JSON schema.

    Evidence comes first and the actionable instruction comes last. When the provider does not
    enforce a response format, the prompt includes the complete schema and its declared limits.
    """
    parts = []
    if evidence:
        parts += ["Evidence:", *(f"- {line}" for line in evidence), ""]
    if not in_prompt:
        # The server carries the schema; retain the JSON-only closing instruction.
        return "\n".join([*parts, instruction, "", _CLOSING_ENFORCED])
    parts += [instruction, "", _SCHEMA_INTRO, json.dumps(schema, indent=2, sort_keys=True)]
    return "\n".join(parts)


def _json_in(body: str) -> str | None:
    """The body, or the JSON inside a fenced block. Models fence constantly, and refusing a
    right answer for its wrapper is refusing a right answer."""
    fenced = _FENCE.search(body)
    candidate = (fenced.group(1) if fenced else body).strip()
    return candidate or None


def _why_refused(shape: type[BaseModel], failure: ValidationError) -> str:
    """Return a coded refusal naming safe field locations from a validation failure."""
    too_long = [e for e in failure.errors() if e["type"] == "string_too_long"]
    if too_long:
        fields = ", ".join(".".join(str(part) for part in e["loc"]) for e in too_long)
        return coded("MA0006", f"{fields} was longer than the field allows")
    # Report field locations without echoing the model-provided values.
    where = sorted({".".join(str(part) for part in e["loc"]) or "(root)" for e in failure.errors()})
    return coded("MA0004", f"the answer did not match {shape.__name__}: {', '.join(where)}")


class LiteLLMTransport:
    """Live LiteLLM transport, imported lazily when a request is delivered."""

    enforces_formats = True
    """Indicates support for provider response formats."""

    def send(
        self,
        access: ModelAccess,
        prompt: "str | list[dict]",
        response_format: dict | None = None,
    ) -> str:
        return self.deliver(access, prompt, response_format)[0]

    def deliver(
        self,
        access: ModelAccess,
        prompt: "str | list[dict]",
        response_format: dict | None = None,
    ) -> tuple[str, Usage]:
        import time

        import litellm

        started = time.monotonic()
        try:
            response = litellm.completion(
                model=access.model,
                messages=(
                    prompt if isinstance(prompt, list) else [{"role": "user", "content": prompt}]
                ),
                api_key=access.api_key,
                base_url=access.base_url,
                timeout=access.timeout_seconds,
                temperature=access.temperature,
                **({"response_format": response_format} if response_format else {}),
            )
        except litellm.AuthenticationError as failure:
            raise ModelUnavailableError(
                coded("MA0002", "the provider refused the credentials")
            ) from failure
        except litellm.Timeout as failure:
            raise TimeoutError(
                coded("MA0003", f"no answer within {access.timeout_seconds}s")
            ) from failure
        except Exception as failure:
            # Keep third-party failures behind the package's transport error contract.
            raise ModelUnavailableError(
                coded("MA0007", f"{access.model}: {failure}")
            ) from failure
        return response.choices[0].message.content or "", _usage(access, response, started)


def _usage(access: ModelAccess, response: object, started: float) -> Usage:
    """Normalize optional provider metadata without failing a successful response."""
    import time

    elapsed = int((time.monotonic() - started) * 1000)
    usage = getattr(response, "usage", None)
    details = getattr(usage, "prompt_tokens_details", None)
    choices = getattr(response, "choices", None) or []
    return Usage(
        model=getattr(response, "model", None) or access.model,
        duration_ms=elapsed,
        input_tokens=getattr(usage, "prompt_tokens", None),
        output_tokens=getattr(usage, "completion_tokens", None),
        cached_tokens=getattr(details, "cached_tokens", None),
        finish_reason=getattr(choices[0], "finish_reason", None) if choices else None,
    )
