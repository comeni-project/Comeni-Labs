"""The forge is mounted, not reimplemented.

`mendel_forge.http`'s docstring names this plan: it ships an `app` that binds nothing and
has no auth, and Plan 3 mounts it and owns who is calling. A route added here that the
forge already has is a second spelling of one payload.
"""

from fastapi.testclient import TestClient
from mendel_api.main import create_app


def test_the_forge_is_mounted_under_forge():
    client = TestClient(create_app())
    assert client.get("/forge/sources").status_code == 200


def test_we_added_no_routes_to_the_forge():
    """`/forge` is a MOUNT, and that is the assertion.

    A mount delegates every path beneath it to the forge's own app, so there is no way to
    add a `/forge/...` route of our own without it appearing here as a second entry. An
    `APIRoute` under `/forge` would be logic in a transport, which is what the forge spent
    Phase 1 avoiding.
    """
    from fastapi.routing import APIRoute
    from starlette.routing import Mount

    # `getattr`, not `r.path`: include_router puts an _IncludedRouter in app.routes and it
    # carries no path at all. Assuming every route has one is how this test broke the first
    # time a router was added rather than a route.
    under_forge = [
        r for r in create_app().routes
        if str(getattr(r, "path", "")).startswith("/forge")
    ]
    assert [type(r) for r in under_forge] == [Mount], (
        f"expected exactly one mount, got {[(type(r).__name__, r.path) for r in under_forge]}"
    )
    assert not [r for r in under_forge if isinstance(r, APIRoute)]


def test_health_answers_before_anything_else_is_built():
    client = TestClient(create_app())
    assert client.get("/health").json()["ok"] is True
