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

from comeni_core.settings import SettingLocked
from fastapi import FastAPI

from mendel_api.refusals import locked_handler, missing_handler, refusal_handler
from mendel_api.routes import attention as attention_routes
from mendel_api.routes import authoring as authoring_routes
from mendel_api.routes import build as build_routes
from mendel_api.routes import health as health_routes
from mendel_api.routes import registry as registry_routes
from mendel_api.routes import settings as settings_routes
from mendel_api.services import protection

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


def create_app() -> FastAPI:
    app = FastAPI(
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

    # One handler: a coded refusal is a 422 whatever raised it — the convention the forge's
    # CLI and its (now deleted) transport both followed.
    app.add_exception_handler(ValueError, refusal_handler)
    # A `KeyError` is *this id names nothing*, and it was a 500 until 2026-09-05 —
    # `refusals.missing_handler` records why that mattered.
    app.add_exception_handler(KeyError, missing_handler)
    # A setting that is locked (pinned by .env, or not built) is a 409 with its reason, `MI0300`.
    app.add_exception_handler(SettingLocked, locked_handler)
    protection.warn_if_unbuilt()

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
    return app


app = create_app()
