"""May this cross? The protection level, asked at every crossing (spec §8, consultant spec §6).

**Only level 0's row is implemented.** Level 0 lets a sample be uploaded and a model read it;
every other level refuses each crossing with MI0213, so tightening is filling in a row, never a
crossing that forgot to ask.
"""

import logging
import os
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
_DESIGNED = frozenset({"open", "guarded", "sealed"})
"""Levels a person can name and none of whose rows is built yet (issue 71)."""
log = logging.getLogger(__name__)


def level() -> str:
    return str(installation().get(PROTECTION))


def allows(crossing: Crossing) -> bool:
    return crossing in _ALLOWED.get(level(), frozenset())


def refuse(crossing: Crossing) -> str:
    at = level()
    said = f"the protection level is {at}, which does not allow {crossing.value}"
    if at in _DESIGNED:
        said += f"; {at} is designed, not built, so nothing crosses at it yet (level 0 is built)"
    return coded("MI0213", said)


def warn_if_unbuilt() -> None:
    """At startup: a designed level pinned by `.env` fails every crossing, so say so once,
    where an operator reads, rather than only on the first refused upload (issue 226). Reads the
    environment, not the store, so starting the app never waits on the database."""
    pinned = os.environ.get(PROTECTION.env or "", "")
    if pinned in _DESIGNED:
        log.warning(
            "%s=%s is designed, not built: every upload and characterisation will be refused "
            "(MI0213). Level 0 is the only level built.",
            PROTECTION.env,
            pinned,
        )
