"""The two apps. They are separate because §13.1 says so, not as an implementation detail.

`create_app()` is what a person's browser reaches. `create_ingest_app()` is what the head
process posts to, bound on loopback, carrying a per-run secret in its URL. Mounting the second
on the first would make an ingest route reachable by anything that can reach the API.
"""

from fastapi import FastAPI

from wiener_api.routes.ingest import create_ingest_app
from wiener_api.routes.runs import router as runs_router

__all__ = ["create_app", "create_ingest_app"]


def create_app() -> FastAPI:
    app = FastAPI(title="wiener-api", version="0.1.0")
    app.include_router(runs_router)

    @app.get("/api/health", operation_id="health", summary="Is Wiener up")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
