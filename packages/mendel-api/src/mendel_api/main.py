"""The app factory.

**Each route re-exposes one forge operation to supply the paths, and adds nothing else.** No
branch, no reshaping, no second answer to what a draft is. The forge's request models carry
`registry_root`, `source_root` and `workspace_root`; `settings` owns those, and a browser
choosing them would be a second answer to a question that file answers once.

**The served surface is exactly this app's OpenAPI document.** FastAPI does not merge a
mounted sub-app's schema into its parent, so a mounted route is a surface `frontend/src/api/`
cannot be generated for and an agent reading the schema cannot find. `tests/test_mount.py`
holds both halves — no mounts, and no request body carrying a path.

**This used to say the forge's app was "mounted, never re-exposed route by route".** That
stopped being true in phase 2 and stayed untrue for four phases, for the reason above. The
mount and `mendel_forge.http` were both removed in phase 6 —
`notes/specs/2026-08-19-sources-and-drafting.md` §3.2 is the argument and what was lost.
"""

from fastapi import FastAPI

from mendel_api.refusals import refusal_handler
from mendel_api.routes import attention as attention_routes
from mendel_api.routes import contracts as contracts_routes
from mendel_api.routes import health as health_routes
from mendel_api.routes import questions as questions_routes
from mendel_api.routes import registry as registry_routes
from mendel_api.routes import sources as sources_routes

TAGS = [
    {"name": "questions", "description": "What is open, and how it gets closed."},
    {"name": "health", "description": "Whether the service is up, and what the registry holds."},
    {"name": "registry", "description": "The declared data, read only."},
    {"name": "contracts", "description": "What has landed. Read only."},
    {"name": "sources", "description": "What can be read, and starting a draft."},
    {"name": "attention", "description": "What needs a person, across both halves."},
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

    @app.get(
        "/api/health", operation_id="liveness", summary="Is the service up", tags=["health"]
    )
    def health() -> dict[str, bool]:
        """Liveness only. What the *registry* looks like is `/health/registry`, which walks
        a directory — conflating the two makes a liveness probe do real work."""
        return {"ok": True}

    # **Everything under `/api`, and that is not decoration.** The frontend owns `/forge/*` as
    # browser routes, and this app once served `/forge` too; on one origin the dev proxy sent
    # `/forge/queue` to the API and every deep link 404'd. Found by loading a URL rather than
    # by a test — client-side navigation never leaves the SPA, so only a hard refresh shows it.
    app.include_router(questions_routes.router, prefix="/api")
    app.include_router(health_routes.router, prefix="/api")
    app.include_router(registry_routes.router, prefix="/api")
    app.include_router(contracts_routes.router, prefix="/api")
    app.include_router(sources_routes.router, prefix="/api")
    app.include_router(attention_routes.router, prefix="/api")
    return app


app = create_app()
