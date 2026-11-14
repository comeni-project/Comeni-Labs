"""Rules proposed from people's answers (#462): the evidence, the engine's judge, the replay.

When people keep giving the same tier-4 answer on the same facts, that answer is a rule nobody
wrote down. A model drafts the row (`mendel_api.services.rules_ai`); these functions hold it to
the evidence. They are pure, and their input is a list of :class:`Case` records, so they do not
know whether the cases came from this installation's kept pipelines or, later, from a server
gathering them from many.

A case holds what was decided, the study's facts, the answer and who gave it, and a reference to
the pipeline and decision. Never a sample name, key, reference or file name.
"""

import hashlib
import json
from collections import defaultdict

from comeni_core.artifact.pipeline import Pipeline
from comeni_core.declared.registry import Registry
from comeni_core.plan.decision import DecisionKind
from comeni_core.spell.marks import ParamValue
from pydantic import BaseModel, ConfigDict

from mendel_resolver.rules.format import DecisionTarget, Effect

MIN_CASES = 3
"""How many people's answers to one question it takes before the model is asked for a rule.

The first knob for how much the AI does: lower, and it proposes from thinner evidence."""


class Case(BaseModel):
    """One past decision: what it decided, on which facts, the answer and who gave it."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    target: DecisionTarget
    facts: dict[str, ParamValue]
    """The study-wide facts the pipeline was built on. A per-sample list is left out."""
    answer: ParamValue
    reason: str = ""
    """What the person typed with their answer, where they typed anything."""
    pipeline: str
    decision: str
    """The decision's key in that pipeline's `decisions`."""
    by_person: bool
    tier: int

    @property
    def target_key(self) -> str:
        return self.target.key()

    @property
    def evidence(self) -> bool:
        """A person's answer to a question the rules could not settle. A model's answer, or a
        rule's, is a case the replay compares against, never evidence."""
        return self.by_person and self.tier == 4


def _single_role(contracts: list[str], registry: Registry) -> str | None:
    """The one role every contract fills, or None when they share none or several."""
    try:
        shared = set.intersection(*(set(registry.get(c).roles) for c in contracts))
    except (KeyError, ValueError):
        return None
    return next(iter(shared)) if len(shared) == 1 else None


def _target(record, pipeline: Pipeline, registry: Registry) -> DecisionTarget | None:
    if record.kind == DecisionKind.PRODUCER:
        role = _single_role(list(record.candidates), registry)
        return DecisionTarget(effect=Effect.IMPLEMENTATION, of=role) if role else None
    node, _, param = record.key.partition(".")
    step = next((s for s in pipeline.steps if s.id == node), None)
    if step is None or not param:
        return None
    contract = step.module.contract_id
    role = _single_role([contract], registry)
    if role is None:
        return None
    return DecisionTarget(effect=Effect.PARAM, of=role, name=param,
                          when_implementation=[contract])


def _answer(record) -> ParamValue:
    if getattr(record, "human_override", None) is not None:
        return record.human_override
    if getattr(record, "model_override", None) is not None:
        return record.model_override
    return record.chosen


def cases_of(pipeline: Pipeline, registry: Registry, pipeline_id: str) -> list[Case]:
    """Every tool choice and setting this pipeline decided among two or more candidates, as
    cases, sorted by target, pipeline and decision. Model answers and rule answers are kept:
    the replay compares against them."""
    facts = {m.measurement: m.value for m in pipeline.facts.measurements
             if not isinstance(m.value, list)}
    found = []
    for record in pipeline.decisions:
        if record.kind not in (DecisionKind.PRODUCER, DecisionKind.PARAM):
            continue
        if len(record.candidates) < 2:
            continue
        target = _target(record, pipeline, registry)
        if target is None:
            continue
        found.append(Case(
            target=target, facts=facts, answer=_answer(record),
            reason=getattr(record, "override_reason", "") or "", pipeline=pipeline_id,
            decision=record.key, by_person=getattr(record, "human_override", None) is not None,
            tier=int(record.tier)))
    return sorted(found, key=lambda c: (c.target_key, c.pipeline, c.decision))


def evidence(cases: list[Case]) -> dict[str, list[Case]]:
    """People's answers grouped by what they decide, for each target with at least
    :data:`MIN_CASES` of them; sorted by target key."""
    grouped: dict[str, list[Case]] = defaultdict(list)
    for case in cases:
        if case.evidence:
            grouped[case.target_key].append(case)
    return {key: sorted(found, key=lambda c: (c.pipeline, c.decision))
            for key, found in sorted(grouped.items()) if len(found) >= MIN_CASES}


def evidence_digest(cases: list[Case]) -> str:
    """The digest of these cases, independent of their order: a proposal is asked for again only
    when it moves."""
    rows = sorted(json.dumps(case.model_dump(mode="json"), sort_keys=True) for case in cases)
    return "sha256:" + hashlib.sha256("\n".join(rows).encode()).hexdigest()
