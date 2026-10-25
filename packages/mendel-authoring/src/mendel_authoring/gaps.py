"""Identify missing registry declarations that limit a step's review card.

Each gap is derived from pipeline evidence or declared data and names the registry file that owns
the missing description, verification, or parameter domain.
"""

from enum import StrEnum

from comeni_core.artifact.pipeline import Pipeline, Step
from comeni_core.plan.decision import ParamDecision
from pydantic import BaseModel, ConfigDict

from mendel_authoring.brief import tool_of
from mendel_authoring.ports import Declared


class GapKind(StrEnum):
    NO_DOMAIN = "no_domain"
    NO_DESCRIPTION = "no_description"
    UNVERIFIED = "unverified"


class Gap(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: GapKind
    subject: str
    """The setting, tool or contract the gap is about."""
    fix: str
    """The repository path to edit."""


def no_domain(record) -> bool:
    """A tier-4 setting the resolver could offer no values for: its candidates are `[None]`."""
    return isinstance(record, ParamDecision) and list(record.candidates) == [None]


def _contract_file(contract_id: str) -> str:
    return f"registry/tools/{contract_id.split('@', 1)[0]}/contract.yml"


def gaps_of(step: Step, pipeline: Pipeline, declared: Declared) -> list[Gap]:
    contract = step.module.contract_id
    found: list[Gap] = []
    for record in pipeline.decisions:
        if no_domain(record) and record.key.split(".", 1)[0] == step.id:
            found.append(Gap(kind=GapKind.NO_DOMAIN, subject=record.subject,
                             fix=_contract_file(contract)))
    tool = tool_of(contract)
    if declared.tool(tool) is None:
        found.append(Gap(kind=GapKind.NO_DESCRIPTION, subject=tool,
                         fix=f"registry/tools/{tool}/tool.yml"))
    if contract in pipeline.registry.unverified:
        found.append(Gap(kind=GapKind.UNVERIFIED, subject=contract,
                         fix=_contract_file(contract)))
    return found
