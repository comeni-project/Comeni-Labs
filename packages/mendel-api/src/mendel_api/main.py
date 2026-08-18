"""The app factory, and the forge mount.

**The forge's app is mounted, never re-exposed route by route.** `mendel_forge.http` is a
complete transport with eleven routes and a test that compares its payloads to the CLI's;
adding our own `/forge/...` route would be a third spelling of the same operation, and its
own docstring names this plan as the thing that mounts it.
"""

from fastapi import FastAPI
from mendel_forge.http import app as forge_app

from mendel_api.routes import health as health_routes
from mendel_api.routes import questions as questions_routes


def create_app() -> FastAPI:
    app = FastAPI(title="mendel-api", version="0.1.0")

    @app.get("/health")
    def health() -> dict[str, bool]:
        """Liveness only. What the *registry* looks like is `/health/registry`, which walks
        a directory — conflating the two makes a liveness probe do real work."""
        return {"ok": True}

    app.include_router(questions_routes.router)
    app.include_router(health_routes.router)
    app.mount("/forge", forge_app)
    return app


app = create_app()
