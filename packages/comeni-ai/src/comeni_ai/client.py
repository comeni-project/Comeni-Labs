"""The one primitive, and the transport under it.

`generate` asks a model for something and **validates the answer against a declared shape
before any caller sees it.** That is the boundary this package exists to hold — not that a
model may not speak, but that nothing it says is taken on trust.

**An answer that will not validate is declined, never repaired.** A half-built value is worse
than an open hole, because the hole is visible to a reviewer and the half-built value is not.
`None` is a legal, expected answer.

**JSON is requested and validated here rather than delegated to a provider's structured-output
mode.** Invariant 13 says a local model must work identically, and schema support varies by
provider; one code path that always validates is the honest shape. A provider that supports
schemas natively is an optimisation on top, not a second path.

**`Transport` is a seam for the same reason `HoleFiller` is.** It lets every test run with no
network, and it is what the recorded fixtures plug into.
"""

import json
import re
from typing import Protocol, TypeVar, runtime_checkable

from comeni_core.diagnostics import coded
from pydantic import BaseModel, ConfigDict, ValidationError

from comeni_ai.access import ModelAccess, NoModelError

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
    """The provider refused credentials, rejected the request, or could not be reached.
    `MA0002` and `MA0007`."""


@runtime_checkable
class Transport(Protocol):
    """How a prompt reaches a model.

    `runtime_checkable` so a test can assert a fake satisfies it. **That check sees method
    names and not signatures** — it catches `send` being renamed out from under every fake,
    and it does not catch an argument changing. A type checker is what catches the second.
    """

    def send(self, access: ModelAccess, prompt: str) -> str: ...


class Usage(BaseModel):
    """What a provider said about a call it just served.

    **Every field but `model` and `duration_ms` is nullable, and that is the honest shape.**
    Token counts are a provider's courtesy, not a guarantee: a local Ollama endpoint may report
    none, and a `0` where the provider said nothing is a measurement nobody took. §2's audit
    rule asks for token counts *when the provider supplies them*, which is a different
    requirement from asking for them.

    **`model` is what answered, not what was asked for.** A provider may serve a dated
    snapshot for a floating alias, and a review record naming the alias cannot be reproduced.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    model: str
    duration_ms: int
    input_tokens: int | None = None
    output_tokens: int | None = None
    finish_reason: str | None = None


@runtime_checkable
class Metered(Protocol):
    """A transport that can also say what the call cost.

    **A second protocol rather than a wider `Transport`.** Every fake in the suite implements
    `send` and would have to grow a method it has nothing to say for; a recorded fixture has no
    honest duration to report at all. `Client` asks for `deliver` and falls back, so the
    metadata is present where a provider supplied it and absent where nothing did — which is
    the same distinction `Usage`'s nullable fields draw one level down.
    """

    def deliver(self, access: ModelAccess, prompt: str) -> tuple[str, Usage]: ...


class Client:
    def __init__(self, access: ModelAccess, transport: "Transport | None" = None) -> None:
        self.access = access
        self._transport = transport if transport is not None else LiteLLMTransport()
        self.last_refusal: str | None = None
        """Why the most recent `generate` returned `None`, coded, for a caller that wants to
        report it. `None` when the last call succeeded.

        **Cleared on success.** A stale refusal read after a later success would name the wrong
        call, and a caller reporting per hole reads this once per hole.
        """
        self.last_usage: Usage | None = None
        """What the most recent call cost, when the transport could say. `None` otherwise.

        **Cleared at the start of every `generate`, like `last_refusal`.** A usage record left
        over from a previous call would be attributed to this one by an audit row that reads it
        afterwards, which is worse than recording nothing.
        """
        self.last_prompt: str | None = None
        """The exact text sent, for the caller that has to store a digest of it.

        `_prompt` composes the schema and the evidence around the instruction, so the
        instruction a caller passed in is *not* what crossed the wire — and a stored digest of
        the wrong string cannot be compared against a re-render later.
        """

    def generate(self, instruction: str, shape: type[T], evidence: list[str]) -> T | None:
        """Ask, then validate. `None` when the model declines or its answer will not fit."""
        self.last_refusal = None
        self.last_usage = None
        prompt = _prompt(instruction, shape, evidence)
        self.last_prompt = prompt
        try:
            if isinstance(self._transport, Metered):
                body, self.last_usage = self._transport.deliver(self.access, prompt)
            else:
                body = self._transport.send(self.access, prompt)
        except TimeoutError as failure:
            self.last_refusal = str(failure)
            return None
        payload = _json_in(body)
        if payload is None:
            self.last_refusal = coded("MA0004", "the answer was empty")
            return None
        try:
            return shape.model_validate_json(payload)
        except ValidationError as failure:
            self.last_refusal = _why_refused(shape, failure)
            return None


def _prompt(instruction: str, shape: type[BaseModel], evidence: list[str]) -> str:
    """The shape is shown, not described. A model asked for a shape it never saw cannot
    produce it, and the JSON Schema is the shape's own account of itself — including any
    declared length limit, so the model is told the constraint rather than punished for not
    guessing it.

    **Evidence first, instruction last.** The first version put the instruction on top and the
    evidence under it, which works while the evidence is small and fails completely when it is
    not: given ~13,000 characters of documentation, `gemma3:12b` answered by *explaining the
    documentation* rather than choosing — twenty-nine holes, twenty-nine declines. The
    instruction has to be the last thing read, and it has to say that nothing but JSON is
    wanted, because "answer with JSON" alone leaves prose looking permitted alongside it."""
    parts = []
    if evidence:
        parts += ["Evidence:", *(f"- {line}" for line in evidence), ""]
    parts += [
        instruction,
        "",
        "Answer with JSON only, matching this schema exactly. Output nothing else — no "
        "explanation, no commentary, no markdown outside the JSON:",
        json.dumps(shape.model_json_schema(), indent=2, sort_keys=True),
    ]
    return "\n".join(parts)


def _json_in(body: str) -> str | None:
    """The body, or the JSON inside a fenced block. Models fence constantly, and refusing a
    right answer for its wrapper is refusing a right answer."""
    fenced = _FENCE.search(body)
    candidate = (fenced.group(1) if fenced else body).strip()
    return candidate or None


def _why_refused(shape: type[BaseModel], failure: ValidationError) -> str:
    """Which shape violation, not merely that there was one.

    **A refusal that cannot say why it refused is a refusal somebody guesses at.** An overlong
    field is the one violation with an obvious cause and an obvious fix, so it gets its own
    code; reading Pydantic's own error types rather than checking a field by name means any
    capped field in any shape reports itself, not just the one this was written for.
    """
    too_long = [e for e in failure.errors() if e["type"] == "string_too_long"]
    if too_long:
        fields = ", ".join(".".join(str(part) for part in e["loc"]) for e in too_long)
        return coded("MA0006", f"{fields} was longer than the field allows")
    return coded("MA0004", f"the answer did not match {shape.__name__}")


class LiteLLMTransport:
    """The real one.

    **Imported lazily** so the package stays importable with no provider configured, which is
    what lets the no-model lane remain the default rather than a degraded one.
    """

    def send(self, access: ModelAccess, prompt: str) -> str:
        return self.deliver(access, prompt)[0]

    def deliver(self, access: ModelAccess, prompt: str) -> tuple[str, Usage]:
        import time

        import litellm

        started = time.monotonic()
        try:
            response = litellm.completion(
                model=access.model,
                messages=[{"role": "user", "content": prompt}],
                api_key=access.api_key,
                base_url=access.base_url,
                timeout=access.timeout_seconds,
                temperature=access.temperature,
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
            # **Everything else, rather than the two shapes that were anticipated.** A model
            # id with no provider prefix raises `BadRequestError`, which escaped as a raw
            # traceback with LiteLLM's own stderr banner on top of it — found by running the
            # documented loop by hand, not by any test. A transport boundary that lets a
            # third-party exception through is a transport boundary that reports somebody
            # else's error message to our user.
            raise ModelUnavailableError(
                coded("MA0007", f"{access.model}: {failure}")
            ) from failure
        return response.choices[0].message.content or "", _usage(access, response, started)


def _usage(access: ModelAccess, response: object, started: float) -> Usage:
    """What the provider said, defensively.

    **Every field is read through `getattr` and every one may be absent.** LiteLLM normalises
    across a dozen providers and a local endpoint is free to omit the whole `usage` block; an
    attribute error here would turn a successful answer into a transport failure, which is the
    worst possible trade for a diagnostic field. `model` falls back to what was asked for.
    """
    import time

    elapsed = int((time.monotonic() - started) * 1000)
    usage = getattr(response, "usage", None)
    choices = getattr(response, "choices", None) or []
    return Usage(
        model=getattr(response, "model", None) or access.model,
        duration_ms=elapsed,
        input_tokens=getattr(usage, "prompt_tokens", None),
        output_tokens=getattr(usage, "completion_tokens", None),
        finish_reason=getattr(choices[0], "finish_reason", None) if choices else None,
    )
