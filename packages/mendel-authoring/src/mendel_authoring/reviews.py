"""A review applies to meaning, and changing a producer invalidates its dependents."""

import hashlib
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from mendel_authoring.blueprint import Blueprint
from mendel_authoring.canonical import canonical_json
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
    UPDATED = "updated"
    """Only the step's settings, or the facts behind them, changed: the review stands, on the
    step as it is now (issue 496)."""
    SUPERSEDED = "superseded"
    REMOVED = "removed"


class Reason(StrEnum):
    SAME_MEANING = "same_meaning"
    MEANING_CHANGED = "meaning_changed"
    DEPENDENCY_CHANGED = "dependency_changed"
    STEP_REMOVED = "step_removed"
    SETTINGS_CHANGED = "settings_changed"


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
        canonical_json(payload).encode()
    ).hexdigest()


def shape(blueprint: Blueprint, node: str) -> str:
    """What a step is, apart from how it is set: its tool, the module's digest, how the tool was
    chosen, its wiring and the channels it reads by name and type (issue 496). A change here is
    one a person reviews again; a change to settings alone is not."""
    step = blueprint.step(node)
    names = {i.channel for i in step.inputs if i.channel is not None}
    payload = {
        "module": step.module.model_dump(mode="json"),
        # How the tool was chosen: a rule miss turns tier 3 into a tier-4 question, which stays
        # flagged for review (CLAUDE.md), so that is never a settings change.
        "chosen": [int(step.why.tier), step.why.source.value],
        "inputs": [i.model_dump(mode="json") for i in step.inputs],
        "call": [c.model_dump(mode="json") for c in step.call],
        "channels": sorted((c.name, c.type_id) for c in blueprint.pipeline.channels
                           if c.name in names),
    }
    return hashlib.sha256(
        canonical_json(payload).encode()
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
    """Which reviews stand. **Only a new tool or new wiring re-opens a step and the steps after
    it** (the operator's decision on issue 496): a late answer that changes only settings, such
    as strandedness, updates the steps it touches in place rather than sending the walk back."""
    old = {s.id: fingerprint(before, s.id) for s in before.pipeline.steps}
    fresh = {s.id: fingerprint(after, s.id) for s in after.pipeline.steps}
    old_shape = {s.id: shape(before, s.id) for s in before.pipeline.steps}
    new_shape = {s.id: shape(after, s.id) for s in after.pipeline.steps}
    roots = {n for n in old.keys() | fresh.keys() if old_shape.get(n) != new_shape.get(n)}
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
        elif entry.node in roots:
            status, reason = Applicability.SUPERSEDED, Reason.MEANING_CHANGED
        elif entry.node in affected:
            status, reason = Applicability.SUPERSEDED, Reason.DEPENDENCY_CHANGED
        elif entry.fingerprint != fresh[entry.node]:
            status, reason = Applicability.UPDATED, Reason.SETTINGS_CHANGED
        else:
            status, reason = Applicability.RETAINED, Reason.SAME_MEANING
        outcomes.append(ReviewApplicability(node=entry.node, status=status, reason=reason))
    return outcomes
