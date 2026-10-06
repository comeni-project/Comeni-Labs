"""The build's last card: what you'll get, what you need to run it, and who decided what."""

from collections import Counter

from pydantic import BaseModel, ConfigDict

from mendel_authoring.blueprint import Blueprint
from mendel_authoring.brief import Said, family_said
from mendel_authoring.ports import Declared


class Item(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    what: Said | None = None


class Count(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    tier: int
    source: str
    count: int


class WrapUp(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    gets: list[Item]
    """The goal's wanted types."""
    inputs: list[Item]
    """The pipeline's input channels, by the parameter a run sets."""
    unset: list[str]
    """`<step>.<setting>` for every setting with no value, left to the run."""
    decided: list[Count]
    """Every step's selection and every setting, by tier and source, sorted."""


def wrap_up(blueprint: Blueprint, declared: Declared) -> WrapUp:
    pipeline = blueprint.pipeline
    tally = Counter(
        (int(why.tier), why.source.value)
        for step in pipeline.steps
        for why in [step.why, *(setting.why for setting in step.settings)]
    )
    return WrapUp(
        gets=[Item(id=t, what=family_said(t, declared)) for t in pipeline.goal.want],
        inputs=[
            Item(id=f"params.{channel.param}", what=family_said(channel.type_id, declared))
            for channel in pipeline.channels
        ],
        unset=[
            f"{step.id}.{setting.name}"
            for step in pipeline.steps
            for setting in step.settings
            if setting.value is None
        ],
        decided=[
            Count(tier=tier, source=source, count=n) for (tier, source), n in sorted(tally.items())
        ],
    )
