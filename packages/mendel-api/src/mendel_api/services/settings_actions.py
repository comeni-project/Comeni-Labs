"""What a record can be asked to do (spec §6). One map, one generic route.

**Adding an action is one entry here** and its name in the setting's `actions`; the menu draws a
button for each name it is served.
"""

from collections.abc import Awaitable, Callable

from pydantic import BaseModel, ConfigDict

from mendel_api.services import probe


class ActionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: bool | None
    """`None`: not asked, on purpose — a hosted provider is never probed."""
    says: str
    values: list[str] = []


async def _test(record: dict) -> ActionResult:
    endpoint = record.get("endpoint")
    if not endpoint:
        return ActionResult(
            ok=None, says="A hosted provider is not probed: asking costs a call."
        )
    if await probe.answers(endpoint):
        return ActionResult(ok=True, says=f"Something answers at {endpoint}.")
    return ActionResult(ok=False, says=f"Nothing answered at {endpoint} within a few seconds.")


async def _models(record: dict) -> ActionResult:
    endpoint = record.get("endpoint")
    if not endpoint:
        return ActionResult(ok=None, says="Type the model id, as provider/model.")
    try:
        key = record.get("key")  # a SecretStr, opened only for this request
        values = await probe.listed(
            endpoint, record.get("server"), key.get_secret_value() if key else None
        )
    except probe.ProbeFailed as failed:
        return ActionResult(ok=False, says=f"Could not list models at {endpoint} ({failed}).")
    return ActionResult(ok=True, says=f"{len(values)} models at {endpoint}.", values=values)


ACTIONS: dict[tuple[str, str], Callable[[dict], Awaitable[ActionResult]]] = {
    ("models.connections", "test"): _test,
    ("models.connections", "models"): _models,
}
