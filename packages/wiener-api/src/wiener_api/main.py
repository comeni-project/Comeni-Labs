"""The two apps. They are separate because §13.1 says so, not as an implementation detail.

`create_app()` is what a person's browser reaches. `create_ingest_app()` is what the head
process posts to, bound on loopback, carrying a per-run secret in its URL. Mounting the second
on the first would make an ingest route reachable by anything that can reach the API.
"""

import logging
import pathlib
import secrets

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from wiener_api.routes.ingest import create_ingest_app
from wiener_api.routes.runs import router as runs_router
from wiener_api.settings import settings

log = logging.getLogger(__name__)

DOCKER_SOCKET = pathlib.Path("/var/run/docker.sock")


def socket_is_mounted() -> bool:
    """Whether this deployment can start containers on the host. A function rather than an
    inline check so a test can say what it is testing."""
    return DOCKER_SOCKET.exists()


OPEN_PATHS = frozenset({"/api/health", "/openapi.json", "/docs", "/redoc",
                        "/docs/oauth2-redirect"})
"""What a request may reach without a token. **Health, because a probe has no credential** —
and it answers whether Wiener is up, which is not a fact worth protecting."""

__all__ = ["create_app", "create_ingest_app"]


def create_app() -> FastAPI:
    app = FastAPI(title="wiener-api", version="0.1.0")

    if not settings.api_token:
        # **Said out loud at startup**, because the alternative is a deployment that is open
        # and nobody notices until it matters. §12.1 makes this a W1 requirement and an
        # unconfigured install is the one most likely to exist.
        #
        # **The second sentence is the one that matters**, and only when both halves are true:
        # a worker with the Docker socket can start containers on the host, so an open API and
        # a mounted socket together mean anyone who can reach this can reach the machine.
        # Either alone is a choice; the pair is the incident.
        log.warning(
            "WIENER_API_TOKEN is unset: this API accepts every request. Fine on a laptop, "
            "and §12.1 says the first deployment anybody else can reach needs the check first.",
        )
        if socket_is_mounted():
            log.warning(
                "AND the Docker socket is mounted: a run can start containers on the host, "
                "which is root-equivalent. With no token, ANYONE WHO CAN REACH THIS API CAN "
                "REACH THE HOST. Set WIENER_API_TOKEN before exposing this beyond localhost.",
            )

    @app.middleware("http")
    async def require_token(request: Request, call_next):
        """One token, compared in constant time.

        `secrets.compare_digest` rather than `==`: a token checked with an early-exit compare
        leaks its own prefix to anybody willing to time the answers, and this is one line
        either way.
        """
        if settings.api_token and request.url.path not in OPEN_PATHS:
            offered = (request.headers.get("authorization") or "").removeprefix("Bearer ").strip()
            if not (offered and secrets.compare_digest(offered, settings.api_token)):
                # **Returned, not raised.** FastAPI's exception handlers do not run for an
                # exception raised inside middleware, so `raise HTTPException` propagates and
                # the caller sees a 500 or a dropped connection rather than a 401. Found by a
                # test that expected 401 and got the exception itself.
                return JSONResponse(status_code=401,
                                    content={"detail": "a bearer token is required"})
        return await call_next(request)
    app.include_router(runs_router)

    @app.get("/api/health", operation_id="health", summary="Is Wiener up")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
