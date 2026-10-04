"""② The engine gathers what it needs (14.7.8.1)."""

from mendel_api.services import authoring
from mendel_api.services.session import Ctx, handles


@handles("list_needs")
def list_needs(ctx: Ctx) -> str:
    return "listed" if authoring.need_listed(ctx.session_id) else "unreachable"


@handles("next_gap")
def next_gap(ctx: Ctx) -> str:
    return authoring.offer_gap_or_card(ctx.session_id)


@handles("answered")
def answered(ctx: Ctx) -> str:
    """Which of the three the answer was: `answer_gap` recorded it, and says which."""
    return str(ctx.payload["answered"])
