"""A review applies to meaning, and changing a producer invalidates its dependents."""

import hashlib
import json
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from mendel_authoring.blueprint import Blueprint
from mendel_authoring.decisions import ActorKind


class Reviewed(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    node: str
    by: str
    actor_kind: ActorKind = ActorKind.PERSON
    contract: str
    fingerprint: str = Field(min_length=64, max_length=64)


class Applicability(StrEnum):
    RETAINED = "retained"
    SUPERSEDED = "superseded"
    REMOVED = "removed"


class Reason(StrEnum):
    SAME_MEANING = "same_meaning"
    MEANING_CHANGED = "meaning_changed"
    DEPENDENCY_CHANGED = "dependency_changed"
    STEP_REMOVED = "step_removed"


class ReviewApplicability(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    node: str
    status: Applicability
    reason: Reason


def fingerprint(blueprint: Blueprint, node: str) -> str:
    step = blueprint.step(node)
    channels = {i.channel for i in step.inputs if i.channel is not None}
    # Producer decisions use a stable site key; other decisions belong to one node.
    decisions = [
        d.model_dump(mode="json")
        for d in blueprint.pipeline.decisions
        if d.key.startswith(f"{node}.")
        or (d.kind == "producer" and d.chosen == step.module.contract_id)
    ]
    payload = {
        "step": step.model_dump(mode="json"),
        "decisions": decisions,
        "channels": [
            c.model_dump(mode="json") for c in blueprint.pipeline.channels if c.name in channels
        ],
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def review(blueprint: Blueprint, node: str, by: str, *, actor_kind=ActorKind.PERSON) -> Reviewed:
    return Reviewed(
        node=node,
        by=by,
        actor_kind=actor_kind,
        contract=blueprint.step(node).module.contract_id,
        fingerprint=fingerprint(blueprint, node),
    )


def cascade(before: Blueprint, after: Blueprint, reviewed: list[Reviewed]):
    old = {s.id: fingerprint(before, s.id) for s in before.pipeline.steps}
    fresh = {s.id: fingerprint(after, s.id) for s in after.pipeline.steps}
    roots = {n for n in old.keys() | fresh.keys() if old.get(n) != fresh.get(n)}
    children = {}
    for blueprint in (before, after):
        for step in blueprint.pipeline.steps:
            for wired in step.inputs:
                if wired.source:
                    parent = wired.source.split(".", 1)[0]
                    children.setdefault(parent, set()).add(step.id)
    affected, pending = set(roots), list(roots)
    while pending:
        parent = pending.pop()
        for node in children.get(parent, ()):
            if node not in affected:
                affected.add(node)
                pending.append(node)
    outcomes = []
    for entry in reviewed:
        if entry.node not in fresh:
            status, reason = Applicability.REMOVED, Reason.STEP_REMOVED
        elif entry.node in roots or entry.fingerprint != fresh[entry.node]:
            status, reason = Applicability.SUPERSEDED, Reason.MEANING_CHANGED
        elif entry.node in affected:
            status, reason = Applicability.SUPERSEDED, Reason.DEPENDENCY_CHANGED
        else:
            status, reason = Applicability.RETAINED, Reason.SAME_MEANING
        outcomes.append(ReviewApplicability(node=entry.node, status=status, reason=reason))
    return outcomes
