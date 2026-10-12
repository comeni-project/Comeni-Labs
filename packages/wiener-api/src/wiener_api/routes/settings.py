"""Wiener's settings (spec §7, Part H). **Wiener serves its own** because only Wiener reads
Wiener's `.env` and stores Wiener's limits; Mendel's menu merges these sections by order.
Running is reported and read-only; Data retention: runs is stored here and changeable."""

from comeni_core.settings import IllegalValue, Menu, SettingLocked, Shown
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, JsonValue

from wiener_api.services.installation import installation

router = APIRouter(prefix="/api/wiener", tags=["settings"])


@router.get("/settings", operation_id="readWienerSettings", summary="Wiener's settings")
def read_settings() -> Menu:
    return installation().menu("wiener")


class Change(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: JsonValue = None


@router.put("/settings/{key}", operation_id="writeWienerSetting",
            summary="Change one of Wiener's settings")
def write_setting(key: str, change: Change) -> Shown:
    if "value" not in change.model_fields_set:
        raise HTTPException(status_code=422, detail=f"{key} was saved with no value")
    try:
        return installation().put(key, change.value, by="operator")
    except SettingLocked as locked:
        raise HTTPException(status_code=409, detail=str(locked)) from None
    except IllegalValue as refused:
        raise HTTPException(status_code=422, detail=f"{key}: {refused}") from None
    except KeyError:
        raise HTTPException(status_code=404, detail=f"no setting called {key}") from None
