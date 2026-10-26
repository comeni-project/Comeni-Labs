"""Closed-choice helpers built on validated model generation.

The helpers put offered values in the request and reject replies outside that set. Single-value
and list-valued choices remain separate contracts. Callers may repeat membership checks while
admitting the result into their own domain model.
"""

from comeni_core.diagnostics import coded
from pydantic import BaseModel, ConfigDict, Field, model_validator

from comeni_ai.client import Client

_NO_EXTRAS = ConfigDict(extra="forbid")

WHY_LIMIT = 500
"""Maximum rationale length for choice replies.

The limit keeps this generic free-text field unsuitable for large payloads. It is a bounded
interface, not a guarantee about the meaning or safety of model output.
"""


class Option(BaseModel):
    model_config = _NO_EXTRAS

    value: str
    note: str = ""
    """Where this option is declared, so the answer can cite something a reviewer can check."""


class Choice(BaseModel):
    model_config = _NO_EXTRAS

    value: str
    why: str = Field(max_length=WHY_LIMIT)


class Choices(BaseModel):
    model_config = _NO_EXTRAS

    values: list[str]
    """May be empty. 'None of these' is a real answer to a closed choice."""
    why: str = Field(max_length=WHY_LIMIT)


def _question(question: str, options: list[Option]) -> str:
    lines = [question, "", "Choose only from these:"]
    lines += [f"- {o.value}" + (f"  ({o.note})" if o.note else "") for o in options]
    return "\n".join(lines)


def choose_one(
    client: Client,
    question: str,
    options: list[Option],
    evidence: list[str],
    *,
    system: str | None = None,
) -> Choice | None:
    """Return one offered value, or ``None`` when no valid choice is available.

    An empty option list returns without contacting the model.
    """
    if not options:
        return None
    # Enforce the options in the server format when supported, then check membership locally.
    allowed = {"value": [o.value for o in options]}
    if system is not None:
        # Options vary per call, so they follow the cacheable system prefix.
        answer = client.chat(system, _question(question, options), Choice, choices=allowed)
    else:
        answer = client.generate(_question(question, options), Choice, evidence, choices=allowed)
    if answer is None:
        return None
    if answer.value not in {o.value for o in options}:
        client.last_refusal = coded("MA0005", f"{answer.value!r} was not offered")
        return None
    return answer


def choose_many(
    client: Client, question: str, options: list[Option], evidence: list[str]
) -> Choices | None:
    """Any subset of `options`, possibly empty, or `None`."""
    if not options:
        return None
    allowed = {"values": [o.value for o in options]}
    answer = client.generate(_question(question, options), Choices, evidence, choices=allowed)
    if answer is None:
        return None
    offered = {o.value for o in options}
    outside = [value for value in answer.values if value not in offered]
    if outside:
        client.last_refusal = coded("MA0005", f"{outside!r} were not offered")
        return None
    return answer


class Chosen(BaseModel):
    """One of the options was right."""

    model_config = _NO_EXTRAS

    value: str
    why: str = Field(max_length=WHY_LIMIT)


class Proposed(BaseModel):
    """A bounded proposal returned when none of the offered values fits."""

    model_config = _NO_EXTRAS

    id: str
    description: str = Field(max_length=WHY_LIMIT)
    why: str = Field(max_length=WHY_LIMIT)


class _Answer(BaseModel):
    """Wire shape containing exactly one of a selected value or a proposal."""

    model_config = _NO_EXTRAS

    value: str | None = None
    """One of the offered options, or null when nothing fitted."""
    proposed_id: str | None = None
    """A new entry to declare, when and only when `value` is null."""
    proposed_description: str | None = None
    why: str = Field(max_length=WHY_LIMIT)

    @model_validator(mode="after")
    def _exactly_one(self) -> "_Answer":
        chose = self.value is not None
        proposed = self.proposed_id is not None
        if chose and proposed:
            raise ValueError("answer both chose an option and proposed a new one")
        if not chose and not proposed:
            raise ValueError("answer neither chose an option nor proposed a new one")
        if proposed and not self.proposed_description:
            raise ValueError("a proposal must say what the thing it proposes is")
        return self


def choose_or_propose(
    client: Client,
    question: str,
    options: list[Option],
    evidence: list[str],
    *,
    proposing: str,
) -> Chosen | Proposed | None:
    """Return an offered value, a bounded proposal, or ``None``.

    ``proposing`` names the kind of value the model may propose. Use this helper only where the
    caller's contract permits invention; :func:`choose_one` remains strictly closed.
    """
    if not options:
        return None
    asked = "\n\n".join(
        [
            _question(question, options),
            f"If none of them fits, leave `value` null and propose {proposing} instead: "
            f"give `proposed_id` and `proposed_description`. Prefer an option when one fits — "
            f"propose only when none does.",
        ]
    )
    answer = client.generate(asked, _Answer, evidence)
    if answer is None:
        return None
    if answer.value is not None:
        if answer.value not in {o.value for o in options}:
            client.last_refusal = coded("MA0005", f"{answer.value!r} was not offered")
            return None
        return Chosen(value=answer.value, why=answer.why)
    return Proposed(
        id=answer.proposed_id or "",
        description=answer.proposed_description or "",
        why=answer.why,
    )


def suggest(
    client: Client, question: str, options: list[Option], evidence: list[str]
) -> Choice | None:
    """Return a suggestion guided, but not restricted, by the supplied examples."""
    shown = "\n".join(
        f"- {o.value}" + (f"  ({o.note})" if o.note else "") for o in options
    )
    asked = (
        f"{question}\n\nNames used for this elsewhere in the registry, as a guide — you may "
        f"answer with one of them or with something else if it fits better:\n{shown}"
        if options
        else question
    )
    return client.generate(asked, Choice, evidence)
