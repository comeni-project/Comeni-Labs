"""① You describe it: the model's reading becomes the want (14.7.8.1)."""

from mendel_api.services import authoring
from mendel_api.services.session import Ctx, handles


@handles("read_goal")
def read_goal(ctx: Ctx) -> str:
    """Store the want the model read; the engine takes over to gather what it needs."""
    authoring.store_goal(ctx.session_id, ctx.payload["goal"])
    return "want_returned"
