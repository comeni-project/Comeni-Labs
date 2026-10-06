"""How the walk paces itself: at every step together, or only where the person is needed.

The values are the Pacing setting's option ids (`comeni_core.settings.catalogue.PACING`). Its
third option, `ask`, is not a pacing: the shell asks the question and passes the answer here.
"""

from enum import StrEnum

from mendel_authoring.plan import BuildPlan


class Pacing(StrEnum):
    TOGETHER = "together"
    STOP_WHERE_NEEDED = "stop_where_needed"


def waits(plan: BuildPlan, pacing: Pacing) -> list[str]:
    """The steps the walk stops at; the shell places the rest at once."""
    if pacing is Pacing.TOGETHER:
        return [step.node for step in plan.steps]
    return [step.node for step in plan.needing()]
