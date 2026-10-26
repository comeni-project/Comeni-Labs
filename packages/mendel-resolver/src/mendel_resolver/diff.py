"""Describe material changes between two pipeline artifacts.

Upgrade reporting includes added, removed, or replaced modules; setting values, evidence tiers,
and reasons; and changed input wiring. Every change retains the tier and reason a reviewer needs
to judge its significance.
"""

from comeni_core.artifact.pipeline import Pipeline
from comeni_core.plan.tiers import Tier
from pydantic import BaseModel, ConfigDict


class Change(BaseModel):
    """One stable, human-readable pipeline difference."""
    model_config = ConfigDict(extra="forbid")

    what: str
    """`node_id` for a module, `node_id.param` for a parameter."""
    before: str
    after: str
    tier: Tier
    reason: str

    def __str__(self) -> str:
        return f"  {self.what}: {self.before} -> {self.after}  (tier {self.tier}) {self.reason}"


# `diff_ir` and `_edge_changes` lived here and are deleted. `upgrade` reads a `pipeline.yml`
# since Plan 1.10 Task 10, so there is no previous `PipelineIR` to compare against and they
# had no callers left.
#
# Deleted rather than kept for a future caller. Two comparisons answering "what moved" is
# root D's finding waiting to happen — the whole reason `verify` is `upgrade --dry-run`
# rather than a second verb — and an unused one is the easier of the two to drift.


def diff_pipeline(before: Pipeline, after: Pipeline) -> list[Change]:
    """Return deterministic, sorted differences between saved pipeline decisions.

    Contract-owned ``ext_args`` are deliberately excluded: registry drift reports contract
    movement, while emitted-file digests detect its generated effect. This function reports the
    person- or resolver-facing decisions represented in the artifact.
    """
    changes: list[Change] = []
    was = {step.id: step for step in before.steps}
    now = {step.id: step for step in after.steps}

    for step_id in sorted(set(was) | set(now)):
        old, new = was.get(step_id), now.get(step_id)
        if old is None:
            changes.append(
                Change(
                    what=step_id,
                    before="(absent)",
                    after=new.module.contract_id,
                    tier=new.why.tier,
                    reason=new.why.reason,
                )
            )
            continue
        if new is None:
            changes.append(
                Change(
                    what=step_id,
                    before=old.module.contract_id,
                    after="(removed)",
                    tier=old.why.tier,
                    reason="no longer routed",
                )
            )
            continue
        if old.module.contract_id != new.module.contract_id:
            changes.append(
                Change(
                    what=step_id,
                    before=old.module.contract_id,
                    after=new.module.contract_id,
                    tier=new.why.tier,
                    reason=new.why.reason,
                )
            )
        changes += _setting_changes(step_id, old, new)
        changes += _wiring_changes(step_id, old, new)

    return sorted(changes, key=lambda change: (change.what, change.before, change.after))


def _setting_changes(step_id: str, old, new) -> list[Change]:
    """Values, and the tier each exited at.

    Same value at a different tier is still a change, and a large one: a parameter that moves
    from a documented default to "nobody knows" is the same number and a completely different
    claim. A28.
    """
    was = {setting.name: setting for setting in old.settings}
    changes = []
    for setting in new.settings:
        previous = was.get(setting.name)
        what = f"{step_id}.{setting.name}"
        if previous is None or previous.value != setting.value:
            changes.append(
                Change(
                    what=what,
                    before="(unset)" if previous is None else str(previous.value),
                    after=str(setting.value),
                    tier=setting.why.tier,
                    reason=setting.why.reason,
                )
            )
        elif previous.why.tier is not setting.why.tier:
            changes.append(
                Change(
                    what=what,
                    before=f"{previous.value} (tier {previous.why.tier})",
                    after=f"{setting.value} (tier {setting.why.tier})",
                    tier=setting.why.tier,
                    reason=setting.why.reason,
                )
            )
        elif previous.why.reason != setting.why.reason:
            # Same value, same tier, different justification — and until A77 that was the
            # shape of a person's sentence being replaced by the resolver's. Reported rather
            # than performed in silence: the answer that was dropped is exactly the thing a
            # reader needs told, which is the argument `_still_applies` already makes about
            # discarded overrides one level up.
            changes.append(
                Change(
                    what=f"{what} (reason)",
                    before=previous.why.reason,
                    after=setting.why.reason,
                    tier=setting.why.tier,
                    reason="the value is unchanged; what it is justified by is not",
                )
            )
    for name in sorted(set(was) - {s.name for s in new.settings}):
        changes.append(
            Change(
                what=f"{step_id}.{name}",
                before=str(was[name].value),
                after="(no longer a setting)",
                tier=was[name].why.tier,
                reason="the contract no longer declares it",
            )
        )
    return changes


def _wiring_changes(step_id: str, old, new) -> list[Change]:
    """Which output now feeds each consumed port.

    Keyed on the destination, because that is the question: what arrives here? `resolve.py`
    records in its own comment that wiring `.bai` into featureCounts was "valid Nextflow, no
    flag, and `-stub-run` cannot catch it" — nor could `mendel upgrade`, which compared
    contracts and parameters and never looked at the wiring between them. A28.
    """

    def origin(item) -> str:
        if item is None:
            return "(nothing)"
        return item.source if item.source is not None else f"channel:{item.channel}"

    was = {item.port: item for item in old.inputs}
    now = {item.port: item for item in new.inputs}
    changes = []
    for port in sorted(set(was) | set(now)):
        before, after = origin(was.get(port)), origin(now.get(port))
        if before == after:
            continue
        changes.append(
            Change(
                what=f"{step_id} <- {port}",
                before=before,
                after=after,
                # Structural: an edge is not resolved at a tier, it is what routing built.
                # The tier that matters for a rewire is on the step whose selection moved,
                # and that change is already its own line.
                tier=Tier.STRUCTURAL,
                reason="the wiring changed",
            )
        )
    return changes
