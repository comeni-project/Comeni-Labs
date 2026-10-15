"""How the walk paces itself: at every step together, or only where the person is needed.

The values are the Pacing setting's option ids (`comeni_core.settings.catalogue.PACING`). Its
third option, `ask`, is not a pacing: the shell asks the question and passes the answer here.
"""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from mendel_authoring.needs import NeedKind
from mendel_authoring.plan import PlannedStep


class Pacing(StrEnum):
    TOGETHER = "together"
    STOP_WHERE_NEEDED = "stop_where_needed"


class Stop(StrEnum):
    """Why the walk stops at a step (§14.4 of the consultant build)."""

    TIER_FOUR = "tier_four"
    GAP = "gap"
    TOGETHER = "together"


class Policy(BaseModel):
    """How the walk goes, stored as one value: the pacing, and whether registry gaps stop it."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    pacing: Pacing
    show_gaps: bool = False


def stops(step: PlannedStep, policy: Policy) -> Stop | None:
    """Why the walk stops at `step`, or `None` to place it quietly. **The need first** (3b's
    Review Focus 1): a tier-4 step stops whatever Dev mode says; then a gap, if gaps are shown;
    then every step under *together*."""
    if step.need.kind is not NeedKind.NOTHING:
        return Stop.TIER_FOUR
    if step.gaps and policy.show_gaps:
        return Stop.GAP
    if policy.pacing is Pacing.TOGETHER:
        return Stop.TOGETHER
    return None
