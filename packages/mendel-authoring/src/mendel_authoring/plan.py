"""The build plan: the content of the walk, from a resolved blueprint, with no model.

One entry per step **in the blueprint's order** — the layout's, so every step comes after its
inputs for any pipeline — each with its card and what it needs; then the wrap-up. Recomputed
whole after a fact is answered and the blueprint re-resolved: the plan holds no history, and
which steps the person already accepted is the draft's. Same blueprint, same plan.
"""

from pydantic import BaseModel, ConfigDict

from mendel_authoring.blueprint import Blueprint
from mendel_authoring.brief import Brief, brief_of
from mendel_authoring.gaps import Gap, gaps_of
from mendel_authoring.needs import Need, NeedKind, need_of
from mendel_authoring.ports import Declared
from mendel_authoring.wrapup import WrapUp, wrap_up


class PlannedStep(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    node: str
    contract: str
    brief: Brief
    need: Need
    gaps: list[Gap] = []
    """What its declared data lacks (spec §13.3); shown when Dev mode is on."""


class BuildPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    steps: list[PlannedStep]
    wrap_up: WrapUp

    def needing(self) -> list[PlannedStep]:
        """The steps that need a fact or a choice; the overview counts these."""
        return [step for step in self.steps if step.need.kind is not NeedKind.NOTHING]


def plan_of(blueprint: Blueprint, declared: Declared) -> BuildPlan:
    decisions = blueprint.pipeline.decisions
    steps = []
    for node in blueprint.order:
        step = blueprint.step(node)
        steps.append(
            PlannedStep(
                node=node,
                contract=step.module.contract_id,
                brief=brief_of(step, declared),
                need=need_of(step, decisions, declared),
                gaps=gaps_of(step, blueprint.pipeline, declared),
            )
        )
    return BuildPlan(steps=steps, wrap_up=wrap_up(blueprint, declared))
