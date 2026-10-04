"""④ Your consultant builds it with you (14.7.8.1). Part 3 replaces this stage's handlers."""

from mendel_api.services import authoring
from mendel_api.services.session import Ctx, handles

_TIER = {1: "settled", 2: "settled", 3: "a_rule", 4: "no_rule"}


@handles("resolve")
def resolve(ctx: Ctx) -> str | None:
    """**A command arriving rests here; resuming resolves** (ruling 9 of 14.7.8.1b). Build
    resumes in the same request (`start_building`), Spawn in its build job."""
    if ctx.command is not None:
        return None
    try:
        return authoring.build_blueprint(ctx.session_id, client=ctx.payload.get("client"))
    except authoring.ResolverFailed as failed:  # the resolver itself: `failed`, then raised
        ctx.raised = failed.__cause__
        return "cant_build"
    # Anything else raised here (MI0200, MI0201) is a refusal of the request: nothing moves.


@handles("offer")
def offer(ctx: Ctx) -> str:
    """Which card the pending step is — or the end. The step was offered by whatever came
    before (`build_blueprint`, `settle_step`)."""
    tier = authoring.pending_step_tier(ctx.session_id)
    return "nothing_left" if tier is None else _TIER[tier]
