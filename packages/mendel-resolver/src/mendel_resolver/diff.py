"""What moved between two resolutions of the same goal.

`mendel upgrade` re-resolves a locked pipeline against the current registry. The re-resolve
is the easy half; this is the half a person reads. Every line has to say *what* changed,
*from what to what*, and *at which tier* — because a tier-1 change and a tier-4 change
demand completely different amounts of attention, and a diff that flattens them is noise.
"""

from comeni_core.pipeline import Pipeline
from comeni_core.tiers import Tier
from pydantic import BaseModel, ConfigDict


class Change(BaseModel):
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
    """The same question as `diff_ir`, asked of the artifact rather than of the IR.

    `upgrade` reads a `pipeline.yml` since Plan 1.10 Task 10, so there is no previous IR to
    compare against — only the file, which is the thing a person edited and the thing they
    will read the answer beside.

    **`ext_args` is deliberately not compared, and that is not an oversight.** It is a contract
    field rather than a decision: nobody resolved it, it carries no `why`, and a change to it
    is the registry moving, which `DRIFT` already reports. What catches its effect is the
    digest verdict — `emitted.from_digest` and `emitted.files` say the generated pipeline
    moved, and when nothing in this diff explains that, `upgrade` says so out loud instead of
    letting a reader assume the diff is complete. That pairing is audit A28's actual fix, and
    a diff that compared every field would not remove the need for it: the compiler itself can
    change, and no comparison of two documents can see that.
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
