"""What moved between two resolutions of the same goal.

`mendel upgrade` re-resolves a locked pipeline against the current registry. The re-resolve
is the easy half; this is the half a person reads. Every line has to say *what* changed,
*from what to what*, and *at which tier* — because a tier-1 change and a tier-4 change
demand completely different amounts of attention, and a diff that flattens them is noise.
"""

from comeni_core.ir import PipelineIR
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


def diff_ir(before: PipelineIR, after: PipelineIR) -> list[Change]:
    """Every module and parameter that resolved differently, in a stable order."""
    changes: list[Change] = []

    was = {node.id: node for node in before.nodes}
    now = {node.id: node for node in after.nodes}

    for node_id in sorted(set(was) | set(now)):
        old, new = was.get(node_id), now.get(node_id)
        if old is None:
            changes.append(
                Change(
                    what=node_id,
                    before="(absent)",
                    after=new.contract_id,
                    tier=new.selection.tier,
                    reason=new.selection.reason,
                )
            )
            continue
        if new is None:
            changes.append(
                Change(
                    what=node_id,
                    before=old.contract_id,
                    after="(removed)",
                    tier=old.selection.tier,
                    reason="no longer routed",
                )
            )
            continue
        if old.contract_id != new.contract_id:
            changes.append(
                Change(
                    what=node_id,
                    before=old.contract_id,
                    after=new.contract_id,
                    tier=new.selection.tier,
                    reason=new.selection.reason,
                )
            )

        old_params = {b.name: b.value for b in old.params}
        for binding in new.params:
            previous = old_params.get(binding.name)
            if previous is None or previous.value != binding.value.value:
                changes.append(
                    Change(
                        what=f"{node_id}.{binding.name}",
                        before="(unset)" if previous is None else str(previous.value),
                        after=str(binding.value.value),
                        tier=binding.value.tier,
                        reason=binding.value.reason,
                    )
                )
    return changes
