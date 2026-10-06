"""What a step needs from the person before it is placed.

- **A fact**, when a rule would decide the step and its premise is unknown (#174): the resolver
  recorded the facts in `ProducerDecision.unknown`. The tools still travel with it, so *choose a
  tool instead* is possible.
- **A choice**, when a decision on the step — its tool or a setting — is tier 4 and waits on no
  fact. Candidates are the resolver's own, never authored.
- **Nothing**, otherwise; a question a person already answered (its value's `why.source` is
  `human`) is not asked again.
"""

from collections.abc import Sequence
from enum import StrEnum

from comeni_core.artifact.pipeline import Step
from comeni_core.plan.decision import DecisionRecord, ProducerDecision
from comeni_core.plan.tiers import Tier, ValueSource
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
        if record.tier is Tier.AMBIGUOUS and not _answered(step, record)
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


def _answered(step: Step, record: DecisionRecord) -> bool:
    """Whether a person already settled this question, so the walk does not ask it again.

    **Read off the value the record governs, not only the record.** The router writes a replayed
    person's tool as `chosen` plus the step's `why.source = human` and never sets a producer
    record's `human_override`; and a setting's `human_override` cannot tell *answered null* from
    *unanswered*. `why.source` is the signal `needs_review()` already reads.
    """
    if record.human_override is not None:
        return True
    if isinstance(record, ProducerDecision):
        return step.why.source is ValueSource.HUMAN
    name = record.key.split(".", 1)[1] if "." in record.key else ""
    setting = next((s for s in step.settings if s.name == name), None)
    return setting is not None and setting.why.source is ValueSource.HUMAN


def _candidate(record: DecisionRecord, value: ParamValue, declared: Declared) -> Candidate:
    if isinstance(record, ProducerDecision):
        return Candidate(value=value, does=declared.tool(tool_of(str(value))))
    return Candidate(value=value)
