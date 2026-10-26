"""Describe added, removed, swapped, or meaningfully updated blueprint steps.

Alternative cards, amendment receipts, and hand-edit receipts share this deterministic diff.
"""

from comeni_core.plan.draft import DraftGraph
from pydantic import BaseModel, ConfigDict

from mendel_authoring.blueprint import Blueprint
from mendel_authoring.reviews import fingerprint


class BlueprintDiff(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    added: list[str] = []
    removed: list[str] = []
    updated: list[str] = []
    """The same tool, with changed settings, wiring, reasons, or evidence."""
    swapped: list[tuple[str, str]] = []
    """The same step id, another contract: `(step id, its new contract)`."""

    @property
    def empty(self) -> bool:
        return not (self.added or self.removed or self.swapped or self.updated)

    def sentence(self) -> str:
        parts = []
        if self.added:
            parts.append("adds " + ", ".join(self.added))
        if self.removed:
            parts.append("removes " + ", ".join(self.removed))
        if self.swapped:
            parts.append("changes " + ", ".join(f"{n} to {c}" for n, c in self.swapped))
        if self.updated:
            parts.append("updates " + ", ".join(self.updated) + " settings, wiring or evidence")
        return "; ".join(parts) or "changes nothing"


def _between(
    before: dict[str, str], before_order: list[str], after: dict[str, str], after_order: list[str]
) -> BlueprintDiff:
    return BlueprintDiff(
        added=[n for n in after_order if n not in before],
        removed=[n for n in before_order if n not in after],
        swapped=[(n, after[n]) for n in after_order if n in before and before[n] != after[n]],
    )


def diff_of(before: Blueprint, after: Blueprint) -> BlueprintDiff:
    def tools(blueprint: Blueprint) -> dict[str, str]:
        return {step.id: step.module.contract_id for step in blueprint.pipeline.steps}

    difference = _between(tools(before), before.order, tools(after), after.order)
    swapped = {n for n, _contract in difference.swapped}
    return difference.model_copy(update={"updated": [
        n for n in after.order if n in before.order and n not in swapped
        and fingerprint(before, n) != fingerprint(after, n)]})


def graph_diff(before: DraftGraph, after: DraftGraph) -> BlueprintDiff:
    def tools(graph: DraftGraph) -> dict[str, str]:
        return {node.id: node.contract_id for node in graph.nodes}

    return _between(
        tools(before), [n.id for n in before.nodes], tools(after), [n.id for n in after.nodes]
    )
