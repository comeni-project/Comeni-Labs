"""Running, as Wiener has it (spec §7). **Wiener reports its own** because only Wiener reads
Wiener's `.env`; Mendel's menu merges this by section order."""

from comeni_core.settings import CATALOGUE, Installation, Menu
from fastapi import APIRouter

from wiener_api.settings import settings

router = APIRouter(prefix="/api/wiener", tags=["settings"])


class _Nothing:
    """Running is read-only: nothing is stored, so the store is empty and refuses writes."""

    def values(self):
        return {}

    def put(self, key, value, by):
        raise PermissionError("Wiener's settings are read-only")


def _reporters() -> dict:
    return {
        "running.runtime": lambda: settings.container_profile,
        "running.lost_after": lambda: f"{settings.lost_after_ms // 60000} minutes",
        "running.token": lambda: (
            "a token is required" if settings.api_token
            else "open: anyone who can reach this API can submit runs"
        ),
        "running.telemetry": lambda: "on" if settings.otlp_endpoint else "off",
    }


@router.get("/settings", operation_id="readWienerSettings", summary="Running, as Wiener has it")
def read_settings() -> Menu:
    return Installation(CATALOGUE, _Nothing(), {}, reporters=_reporters()).menu("wiener")
