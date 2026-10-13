"""Authoring presentation reads selected rows; model extraction remains a suggestion."""

from mendel_authoring.decisions import FactOrigin, InputDecision

from mendel_api.authoring.types import Fact, FactKind, FactSource
from mendel_api.services import decisions


def facts(draft_id):
    current = decisions.read(draft_id)
    return [
        *[
            Fact(
                kind=FactKind.INPUT, subject=i.type_id, states=i.states, source=FactSource(i.origin)
            )
            for i in current.inputs
            if i.present
        ],
        *[
            Fact(
                kind=FactKind.MEASUREMENT,
                subject=f.subject,
                value=f.value,
                source=FactSource(f.origin),
                pieces=f.pieces,
                evidence=(
                    f.evidence.model_dump(mode="json", exclude_none=True) if f.evidence else None
                ),
            )
            for f in current.facts
        ],
    ]


def record(draft_id, fact: Fact, *, who, proposal_id=None):
    if fact.kind is FactKind.INPUT:
        return decisions.set_input(
            draft_id,
            InputDecision(
                key=fact.subject,
                type_id=fact.subject,
                states=fact.states,
                origin=FactOrigin(fact.source),
            ),
            who=who,
            proposal_id=proposal_id,
        )
    if fact.source in (FactSource.OPEN, FactSource.PERSON_SAID):
        return decisions.set_fact(
            draft_id, fact.subject, fact.value, who=who, proposal_id=proposal_id
        )
    observed = decisions.observe(
        draft_id,
        fact.subject,
        fact.value,
        origin=fact.source,
        pieces=fact.pieces,
        evidence=fact.evidence,
    )
    return decisions.select_observation(
        draft_id, fact.subject, observed, who=who, proposal_id=proposal_id
    )


def confirmed(draft_id):
    return decisions.confirmed(draft_id)


def goal(row):
    return decisions.goal(row.draft_id)
