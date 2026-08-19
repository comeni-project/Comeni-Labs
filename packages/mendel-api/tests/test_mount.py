"""The served surface is exactly this app's OpenAPI document.

**FastAPI does not merge a mounted sub-app's schema into its parent**, so anything mounted is a
surface that exists and is not in the contract — invisible to `frontend/src/api/`, which is
generated from that document, and invisible to an agent driving Mendel, which reads it. That is
the rule; the forge's transport was the instance that broke it.

**It was mounted until phase 6.** `mendel_forge.http` shipped an app that "binds nothing and has
no auth", and its docstring named `mendel-api` as the thing that would mount it and own who is
calling. Auth is deferred (interface spec §9); the mount was not. What it produced was an
unauthenticated app on the served origin whose request models take `registry_root`, `source_root`
and `workspace_root`, and whose `/drafts/land` ran `git commit` in whatever path it was handed.

The module was **deleted** rather than left unmounted — zero production consumers, an optional
`fastapi` extra nothing installed, and a guide section telling operators to mount it. The
argument, and what was lost with it, is `notes/specs/2026-08-19-sources-and-drafting.md` §3.2.
"""

from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from mendel_api.main import create_app


def test_the_served_surface_is_the_openapi_document():
    """No mounts — because a mount is by construction outside the document."""
    from starlette.routing import Mount

    mounts = [(r.path, type(r).__name__) for r in create_app().routes if isinstance(r, Mount)]
    assert mounts == [], (
        f"{mounts} is served and not in the OpenAPI document. If a sub-app is wanted, it has to "
        "be reachable through the schema — and the forge's own transport additionally took "
        "filesystem paths from an unauthenticated body. Spec §3.2."
    )


def test_no_request_body_accepts_a_filesystem_path():
    """The general form of the same claim, over every body this app accepts.

    A field named for a root is how a path gets back in — not by somebody re-mounting a sub-app,
    but by one convenience parameter on one route.

    **Asserted over the OpenAPI document rather than over `app.routes`.** Two reasons, and the
    first was found by running it: `include_router` nests the real routes, so iterating
    `app.routes` finds **zero** `APIRoute`s carrying a body and the test passes vacuously. The
    second is that the document is the honest surface — it is what the client is generated from.
    """
    schema = create_app().openapi()
    defined = schema["components"]["schemas"]

    bodies = {}
    for path, methods in schema["paths"].items():
        for verb, operation in methods.items():
            body = operation.get("requestBody")
            if body is None:
                continue
            ref = body["content"]["application/json"]["schema"].get("$ref", "")
            bodies[f"{verb.upper()} {path}"] = ref.rsplit("/", 1)[-1]

    assert len(bodies) >= 6, f"the scan found {len(bodies)} request bodies — it is not scanning"
    offenders = [
        f"{where} {model}.{field}"
        for where, model in bodies.items()
        for field in defined.get(model, {}).get("properties", {})
        if field.endswith("_root") or field.endswith("_path")
    ]
    assert offenders == [], f"a request body takes a filesystem path: {offenders}"


def test_every_route_is_under_api():
    """One namespace, because the frontend owns `/forge/*` in the browser. Served on one origin
    the dev proxy resolved the overlap in the API's favour and every deep link 404'd — found by
    loading a URL rather than by a test."""
    outside = [
        r.path
        for r in create_app().routes
        if isinstance(r, APIRoute) and not r.path.startswith("/api")
    ]
    assert outside == [], f"served outside /api: {outside}"


def test_health_answers_before_anything_else_is_built():
    client = TestClient(create_app())
    assert client.get("/api/health").json()["ok"] is True
