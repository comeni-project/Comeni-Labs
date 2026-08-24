"""Where the head process posts. **Not on the public app** — `docs/design/wiener.md` §13.1.

This app is bound separately and every request carries a per-run secret Wiener generated at
launch and put in the weblog URL. A route the head process can reach is not a route the
internet may reach just because it exists — which is the defect Plan 3A phase 6 deleted a whole
transport over, arriving one release later in a different package.
"""

from fastapi import APIRouter, FastAPI, HTTPException, Request

from wiener_api.db import session_scope
from wiener_api.services.projection import record
from wiener_api.settings import settings

router = APIRouter()


@router.post("/events/{run_id}/{secret}", status_code=204)
async def ingest(run_id: str, secret: str, request: Request) -> None:
    payload = await request.json()
    with session_scope() as session:
        from wiener_api import repository

        row = repository.run(session, settings.lab_id, run_id)
        # 404 rather than 403: a wrong secret must not confirm that the run exists.
        if row is None or row.ingest_secret != secret:
            raise HTTPException(status_code=404)
        record(session, settings.lab_id, run_id, payload)


def create_ingest_app() -> FastAPI:
    """Its own app, with no OpenAPI document: nothing about this surface is public."""
    app = FastAPI(title="wiener-ingest", openapi_url=None)
    app.include_router(router)
    return app
