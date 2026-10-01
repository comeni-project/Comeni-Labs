"""The settings menu's API (spec §8): read every section, change one setting.

**Thin on purpose.** The resolver, the checks and the sealing are `comeni_core.settings`; this
file turns their refusals into codes and status codes and adds nothing else.
"""

from typing import Annotated

from comeni_core.diagnostics import coded
from comeni_core.settings import IllegalValue, Installation, Menu, Shown
from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, JsonValue

from mendel_api.identity import default_author
from mendel_api.refusals import LOCKED, REFUSES
from mendel_api.services.installation import installation

router = APIRouter(prefix="/settings", tags=["settings"])


class Change(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: JsonValue = None


@router.get("", operation_id="readSettings", summary="Every setting, its value and its source")
def read_settings(inst: Annotated[Installation, Depends(installation)]) -> Menu:
    return inst.menu("mendel")


@router.put(
    "/{key}",
    operation_id="writeSetting",
    summary="Change one setting for this installation",
    responses={**REFUSES, **LOCKED},
)
def write_setting(
    key: str, change: Change, inst: Annotated[Installation, Depends(installation)]
) -> Shown:
    if change.value is None:
        raise ValueError(coded("MI0301", f"{key} was saved with no value"))
    try:
        return inst.put(key, change.value, by=default_author())
    except IllegalValue as refused:
        raise ValueError(coded("MI0302", f"{key}: {refused}")) from None
