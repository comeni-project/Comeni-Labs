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
from pydantic import BaseModel, ConfigDict, Field, model_validator

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


class Chosen(BaseModel):
    """One of the options was right."""

    model_config = _NO_EXTRAS

    value: str
    why: str = Field(max_length=WHY_LIMIT)


class Proposed(BaseModel):
    """None of the options fitted, and here is what would.

    **This is the one place a model invents rather than selects**, and it is deliberate: the
    alternative is a wrong pick, and a wrong pick is worse than a blank because a blank is
    visible to a reviewer. Spec §3.1.

    `description` is capped for the same reason `why` is — it is free text reaching declared
    data, and a cap makes it the wrong shape for anything larger than a definition.
    """

    model_config = _NO_EXTRAS

    id: str
    description: str = Field(max_length=WHY_LIMIT)
    why: str = Field(max_length=WHY_LIMIT)


class _Answer(BaseModel):
    """What the model is asked for: a choice **or** a proposal, never both.

    Modelled as one shape with two optional halves rather than a union, because a JSON Schema a
    small model can follow is worth more here than a tidy type — and the validator makes the
    exclusivity real either way.
    """

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
    """One of `options`, or a proposal for a new one, or `None`.

    **A sibling of `choose_one` rather than a replacement.** The tier-4 ambiguity resolver
    (Plan 3) wants the strict form — an ambiguity is a choice between contracts that exist, and
    nothing there should be able to invent a candidate. Widening `choose_one` would hand it a
    path it has no use for.

    `proposing` names the kind of thing a proposal would be — "a declared type" — because a
    model asked to invent needs to know what it is inventing.
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
