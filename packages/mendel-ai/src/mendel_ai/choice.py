"""Closed choice, as a helper over `generate`.

**Not the primitive.** The first design of this package made closed choice the whole surface,
which was wrong twice: it drew the boundary at *choice versus generation* rather than at
*validated against a declared shape*, and it was designed against the tier-4 ambiguity
resolver while the next consumer — the rule drafter — does not fit a list of options. Spec
§4.3 records both.

**Two functions because some holes are list-valued.** `roles` and `produces[].state` take
several members from one closed set, which is why `Hole.legal` checks member by member and why
a single-value return cannot fill them. The future `AmbiguityResolver` uses `choose_one` only —
`Resolution.chosen` is singular.

**Membership is checked here and again by the caller.** `Hole.legal` refuses the same value on
the way into a scaffold. Not redundant: that is the check a person's fill already goes through,
and routing a model's answer through it means one rule rather than two that drift.
"""

from comeni_core.diagnostics import coded
from pydantic import BaseModel, ConfigDict, Field

from mendel_ai.client import Client

_NO_EXTRAS = ConfigDict(extra="forbid")

WHY_LIMIT = 500
"""How long a rationale may be.

A sentence or two. **This is the only free-text field a model writes in this package**, and the
cap is what makes it the wrong shape for the things worth smuggling through it — a module's
script body, or a `priority_because` essay. It does not close the side channel and is not sold
as doing so (spec §4.3.1: cost-raising, not a proof).

A first number, expected to move once there are real drafts to look at. `MA0006` is what a
reader sees when it bites, so moving it is a decision somebody makes with evidence rather than
a silence somebody discovers.
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
    client: Client, question: str, options: list[Option], evidence: list[str]
) -> Choice | None:
    """One of `options`, or `None`.

    **No options is `None` rather than a free answer.** A hole with no candidates is free text,
    and asking anyway is the one thing this design says it does not do.
    """
    if not options:
        return None
    answer = client.generate(_question(question, options), Choice, evidence)
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
    answer = client.generate(_question(question, options), Choices, evidence)
    if answer is None:
        return None
    offered = {o.value for o in options}
    outside = [value for value in answer.values if value not in offered]
    if outside:
        client.last_refusal = coded("MA0005", f"{outside!r} were not offered")
        return None
    return answer
