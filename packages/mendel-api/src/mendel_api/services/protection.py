"""May this cross? The protection level, asked at every crossing (spec §8, consultant spec §6).

**Only level 0's row is implemented.** Level 0 lets a sample be uploaded and a model read it;
every other level refuses each crossing with MI0213, so tightening is filling in a row, never a
crossing that forgot to ask.
"""

from enum import StrEnum

from comeni_core.diagnostics import coded
from comeni_core.settings.catalogue import PROTECTION

from mendel_api.services.installation import installation


class Crossing(StrEnum):
    UPLOAD = "upload"
    """A sample's head reaches this server (14.7.6)."""
    CHARACTERISE = "characterise"
    """A model reads a sample's head (14.7.7)."""
    DOOR_6 = "door_6"
    """The characterise payload leaves (14.7.7)."""


_ALLOWED = {"level_0": frozenset(Crossing)}


def level() -> str:
    return str(installation().get(PROTECTION))


def allows(crossing: Crossing) -> bool:
    return crossing in _ALLOWED.get(level(), frozenset())


def refuse(crossing: Crossing) -> str:
    return coded(
        "MI0213", f"the protection level is {level()}, which does not allow {crossing.value}"
    )
