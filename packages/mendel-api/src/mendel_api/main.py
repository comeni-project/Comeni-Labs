"""The app factory.

**Each route re-exposes one forge operation to supply the paths, and adds nothing else.** No
branch, no reshaping, no second answer to what a draft is. The forge's request models carry
`registry_root`, `source_root` and `workspace_root`; `settings` owns those, and a browser
choosing them would be a second answer to a question that file answers once.

**The served surface is exactly this app's OpenAPI document.** FastAPI does not merge a
mounted sub-app's schema into its parent, so a mounted route is a surface `frontend/src/api/`
cannot be generated for and an agent reading the schema cannot find. `tests/test_mount.py`
holds both halves — no mounts, and no request body carrying a path.
"""

import logging

from comeni_core.settings import SettingLocked
from fastapi import FastAPI

from mendel_api.refusals import locked_handler, missing_handler, refusal_handler
from mendel_api.routes import attention as attention_routes
from mendel_api.routes import authoring as authoring_routes
from mendel_api.routes import build as build_routes
from mendel_api.routes import data as data_routes
from mendel_api.routes import forge as forge_routes
from mendel_api.routes import health as health_routes
from mendel_api.routes import proposals as proposal_routes
from mendel_api.routes import registry as registry_routes
from mendel_api.routes import settings as settings_routes

TAGS = [
    {"name": "questions", "description": "What is open, and how it gets closed."},
    {"name": "health", "description": "Whether the service is up, and what the registry holds."},
    {"name": "registry", "description": "The declared data, read only."},
    {"name": "contracts", "description": "What has landed. Read only."},
    {"name": "sources", "description": "What can be read, and starting a draft."},
    {"name": "attention", "description": "What needs a person, across both halves."},
    {
        "name": "settings",
        "description": "What this installation may change, and where each value came from.",
    },
    {
        "name": "forge",
        "description": (
            "Adapting a tool: the catalogue, an adaptation and its revisions, and the "
            "review conversation. Queued mutations answer 202."
        ),
    },
]


def _warm() -> None:
    """Load and check the registry before the first request, so the first build a person asks
    for is not the one that pays for it (#545). Never fatal: a registry that cannot load is
    met, and said, by the first build."""
    from mendel_api.services import registry

    try:
        registry.warm()
    except Exception:  # noqa: BLE001 — starting is not the place to refuse a registry
        logging.getLogger(__name__).exception("the registry could not be loaded at startup")


def create_app() -> FastAPI:
    import asyncio
    from contextlib import asynccontextmanager

    from mendel_api.agent import mcp as served

    # **The engine's tools over MCP** (#463), behind `MENDEL_MCP_TOKEN`. Its session manager
    # runs for the app's lifetime: a mounted app's own lifespan never runs.
    mcp_app = served.app()

    @asynccontextmanager
    async def lifespan(_app):
        await asyncio.to_thread(_warm)
        async with served.server.session_manager.run():
            yield

    app = FastAPI(
        lifespan=lifespan,
        title="mendel-api",
        version="0.1.0",
        summary="The forge and Mendel, over one schema.",
        description=(
            "**The schema is the contract.** `frontend/src/api/` is generated from this "
            "document and never hand-edited, and an agent driving Mendel reads the same "
            "document — so an operation without an `operationId`, a tag, or a declared "
            "refusal is a gap in both consumers at once."
        ),
        openapi_tags=TAGS,
    )

    @app.middleware("http")
    async def one_reading_of_the_decisions(request, call_next):
        """A request decides each draft's decisions once per revision (#561): a sync route
        runs in a thread with a copy of this context, which holds the same memo."""
        from mendel_api.services import decisions

        with decisions.remembered():
            return await call_next(request)

    # One handler: a coded refusal is a 422 whatever raised it — the convention the forge's
    # CLI and its (now deleted) transport both followed.
    app.add_exception_handler(ValueError, refusal_handler)
    # A `KeyError` is *this id names nothing*, and it was a 500 until 2026-09-05 —
    # `refusals.missing_handler` records why that mattered.
    app.add_exception_handler(KeyError, missing_handler)
    # A setting that is locked (pinned by .env, or not built) is a 409 with its reason, `MI0300`.
    app.add_exception_handler(SettingLocked, locked_handler)

    @app.get(
        "/api/health", operation_id="liveness", summary="Is the service up", tags=["health"]
    )
    def health() -> dict[str, bool]:
        """Liveness only. What the *registry* looks like is `/health/registry`, which walks
        a directory — conflating the two makes a liveness probe do real work."""
        return {"ok": True}

    # **Everything under `/api`**, so the browser owns every other path as a client-side route
    # and a hard refresh on a deep link reaches the SPA rather than the API.
    app.include_router(health_routes.router, prefix="/api")
    app.include_router(registry_routes.router, prefix="/api")
    app.include_router(build_routes.router, prefix="/api")
    app.include_router(attention_routes.router, prefix="/api")
    # The living pipeline. `/pipeline/authoring` sits under the build router's own prefix and
    # declares no path parameter at its root, so it cannot be swallowed by anything above it.
    app.include_router(authoring_routes.router, prefix="/api")
    # Settings for the whole installation (spec 2026-10-01).
    app.include_router(settings_routes.router, prefix="/api")
    app.include_router(data_routes.router, prefix="/api")
    # The forge's catalogue (forge part 1, #362).
    app.include_router(forge_routes.router, prefix="/api")
    app.include_router(proposal_routes.router, prefix="/api")
    app.mount("/api/mcp", mcp_app)
    return app


app = create_app()
