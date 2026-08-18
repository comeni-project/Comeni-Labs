"""The app factory, and the forge mount.

**The forge's app is mounted, never re-exposed route by route.** `mendel_forge.http` is a
complete transport with eleven routes and a test that compares its payloads to the CLI's;
adding our own `/forge/...` route would be a third spelling of the same operation, and its
own docstring names this plan as the thing that mounts it.
"""

from fastapi import FastAPI
from mendel_forge.http import app as forge_app

from mendel_api.refusals import refusal_handler
from mendel_api.routes import health as health_routes
from mendel_api.routes import questions as questions_routes

TAGS = [
    {"name": "questions", "description": "What is open, and how it gets closed."},
    {"name": "health", "description": "Whether the service is up, and what the registry holds."},
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

    # One handler, as `mendel_forge.http` does: a coded refusal is a 422 whatever raised it.
    app.add_exception_handler(ValueError, refusal_handler)

    @app.get(
        "/api/health", operation_id="liveness", summary="Is the service up", tags=["health"]
    )
    def health() -> dict[str, bool]:
        """Liveness only. What the *registry* looks like is `/health/registry`, which walks
        a directory — conflating the two makes a liveness probe do real work."""
        return {"ok": True}

    # **Everything under `/api`, and that is not decoration.** The frontend owns `/forge/*`
    # as browser routes and this app mounts the forge transport at `/forge` too; served on one
    # origin, the dev proxy sent `/forge/queue` to the API and every deep link 404'd. Found by
    # loading a URL rather than by a test — client-side navigation never leaves the SPA, so
    # only a hard refresh shows it.
    app.include_router(questions_routes.router, prefix="/api")
    app.include_router(health_routes.router, prefix="/api")
    app.mount("/api/forge", forge_app)
    return app


app = create_app()
