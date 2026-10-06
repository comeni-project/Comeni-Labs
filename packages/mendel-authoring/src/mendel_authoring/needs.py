"""What a step needs from the person before it is placed.

- **A fact**, when a rule would decide the step and its premise is unknown (#174): the resolver
  recorded the facts in `ProducerDecision.unknown`. The tools still travel with it, so *choose a
  tool instead* is possible.
- **A choice**, when a decision on the step — its tool or a setting — is tier 4 and waits on no
  fact. Candidates are the resolver's own, never authored.
- **Nothing**, otherwise; a question a person already answered is not asked again.
"""

from collections.abc import Sequence
from enum import StrEnum

from comeni_core.artifact.pipeline import Step
from comeni_core.plan.decision import DecisionRecord, ProducerDecision
from comeni_core.plan.tiers import Tier
from comeni_core.spell.marks import ParamValue
from pydantic import BaseModel, ConfigDict

from mendel_authoring.brief import tool_of
from mendel_authoring.ports import Declared


class NeedKind(StrEnum):
    NOTHING = "nothing"
    FACT = "fact"
    CHOICE = "choice"


class Candidate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    value: ParamValue
    does: str | None = None
    """For a tool, its declared description; nothing for a setting's value."""


class Choice(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    key: str
    candidates: list[Candidate]


class Need(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: NeedKind
    facts: list[str] = []
    choices: list[Choice] = []


def decisions_of(step: Step, decisions: Sequence[DecisionRecord]) -> list[DecisionRecord]:
    """The decisions about this step: its producer question (matched on the contract chosen, as
    `committed` matches it — a contract appears at most once in a pipeline, A97), and every
    per-step record keyed `<node>.<subject>`."""
    found: list[DecisionRecord] = []
    for record in decisions:
        if isinstance(record, ProducerDecision):
            if record.chosen == step.module.contract_id:
                found.append(record)
        elif record.key.split(".", 1)[0] == step.id:
            found.append(record)
    return found


def need_of(step: Step, decisions: Sequence[DecisionRecord], declared: Declared) -> Need:
    open_ = [
        record
        for record in decisions_of(step, decisions)
        if record.tier is Tier.AMBIGUOUS and record.human_override is None
    ]
    if not open_:
        return Need(kind=NeedKind.NOTHING)
    facts = sorted(
        {fact for r in open_ if isinstance(r, ProducerDecision) for fact in r.unknown}
    )
    return Need(
        kind=NeedKind.FACT if facts else NeedKind.CHOICE,
        facts=facts,
        choices=[
            Choice(key=r.key, candidates=[_candidate(r, value, declared) for value in r.candidates])
            for r in open_
        ],
    )


def _candidate(record: DecisionRecord, value: ParamValue, declared: Declared) -> Candidate:
    if isinstance(record, ProducerDecision):
        return Candidate(value=value, does=declared.tool(tool_of(str(value))))
    return Candidate(value=value)
