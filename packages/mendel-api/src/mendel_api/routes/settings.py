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
from mendel_api.services.settings_actions import ACTIONS, ActionResult

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
    # **Missing, not null, is MI0301.** `null` is a value some settings hold — a model's *same as
    # the default* — so whether it is legal is the setting's own check (MI0302 when it is not).
    if "value" not in change.model_fields_set:
        raise ValueError(coded("MI0301", f"{key} was saved with no value"))
    try:
        return inst.put(key, change.value, by=default_author())
    except IllegalValue as refused:
        raise ValueError(coded("MI0302", f"{key}: {refused}")) from None
@router.post(
    "/{key}/items/{name}/{action}",
    operation_id="runSettingAction",
    summary="Ask one record of a setting to do something: test a connection, list its models",
    responses=REFUSES,
)
async def run_setting_action(
    key: str, name: str, action: str, inst: Annotated[Installation, Depends(installation)]
) -> ActionResult:
    setting = inst.catalogue.setting(key)
    if action not in setting.actions or (key, action) not in ACTIONS:
        raise KeyError(f"{key} has no action {action}")
    record = inst.record(setting, name)
    if record is None:
        raise KeyError(f"{key} has no record {name}")
    return await ACTIONS[(key, action)](record)
