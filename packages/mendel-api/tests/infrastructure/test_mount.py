"""The served surface is exactly this app's OpenAPI document.

**FastAPI does not merge a mounted sub-app's schema into its parent**, so anything mounted is a
surface that exists and is not in the contract — invisible to `frontend/src/api/`, which is
generated from that document, and invisible to an agent driving Mendel, which reads it. That is
the rule; the forge's transport was the instance that broke it.

**It was mounted until phase 6.** The old forge's HTTP module shipped an app that "binds nothing
and has no auth", and its docstring named `mendel-api` as the thing that would mount it and own who
is calling. Auth is deferred (interface spec §9); the mount was not. What it produced was an
unauthenticated app on the served origin whose request models take `registry_root`, `source_root`
and `workspace_root`, and whose `/drafts/land` ran `git commit` in whatever path it was handed.

The module was **deleted** rather than left unmounted — zero production consumers, an optional
`fastapi` extra nothing installed, and a guide section telling operators to mount it. The
argument, and what was lost with it, is `docs/notes/specs/2026-08-19-sources-and-drafting.md` §3.2.

**One mount is allowed, by name: `/api/mcp`** (#463). It serves the builder agent's tools over
MCP, whose contract is the protocol's own tool listing rather than an OpenAPI document; it is
behind a bearer token (`MENDEL_MCP_TOKEN`, off without one); and its tools are the same declared
inputs the in-process agent uses, which `test_no_mcp_tool_takes_a_filesystem_path` scans.
"""

from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from mendel_api.main import create_app

MOUNTS = {"/api/mcp"}
"""The one sub-app served outside the document, and why, is the module docstring's."""


def test_the_served_surface_is_the_openapi_document():
    """No mounts but MCP's — because a mount is by construction outside the document."""
    from starlette.routing import Mount

    mounts = [(r.path, type(r).__name__) for r in create_app().routes
              if isinstance(r, Mount) and r.path not in MOUNTS]
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

    # **Every content type, and inline schemas too** (#134): an uploaded sample is a
    # multipart body declared inline, and a check that read only `application/json` `$ref`s
    # would skip exactly the body that carries a person's file.
    bodies = {}
    for path, methods in schema["paths"].items():
        for verb, operation in methods.items():
            body = operation.get("requestBody")
            if body is None:
                continue
            for kind, content in body["content"].items():
                shape = content["schema"]
                ref = shape.get("$ref", "")
                fields = (
                    defined.get(ref.rsplit("/", 1)[-1], {}).get("properties", {})
                    if ref
                    else shape.get("properties", {})
                )
                bodies[f"{verb.upper()} {path} ({kind})"] = list(fields)

    assert len(bodies) >= 7, f"the scan found {len(bodies)} request bodies — it is not scanning"
    # **No body carries a file since #511**: samples are read where they are, from the folders a
    # person ticks (`tickDataFolders`), never uploaded. That body names folders under the data
    # roots, each resolved and checked (`MI0221`); the recorded level-0 exception to invariant 15.
    assert not any("multipart" in where for where in bodies), "a body carries a file again"
    # **The two bodies that name a person's files, by the operator's decision (#511).** Each is
    # resolved and checked against the data roots before anything is read (`MI0221`); the level-0
    # exception to invariant 15 is recorded there. Any other body naming a path fails here.
    allowed = {
        ("PUT /api/data/{draft_id}/folders (application/json)", "folders"),
        ("POST /api/data/{draft_id}/references (application/json)", "path"),
        # Not a path at all: a file's bare name, matched within a ticked folder (`rule.validate`).
        ("POST /api/data/{draft_id}/fixes (application/json)", "file"),
        # A module's path inside a catalogue source (nf-core/modules), not on this machine.
        ("POST /api/forge/adaptations (application/json)", "path"),
        # Not a path on this machine: a registry test run's published results, `process/name`
        # as the run service lists them, matched against expected patterns and never opened.
        ("POST /api/tool-tests/check-outputs (application/json)", "files"),
    }
    offenders = [
        f"{where} {field}"
        for where, fields in bodies.items()
        for field in fields
        if (field in {"path", "paths", "folder", "folders", "file", "files"}
            or field.endswith("_root") or field.endswith("_path"))
        and (where, field) not in allowed
    ]
    assert offenders == [], f"a request body takes a filesystem path: {offenders}"
    for where, field in allowed:
        assert field in bodies.get(where, []), f"the allowed body {where} {field} moved: update it"


def test_no_mcp_tool_takes_a_filesystem_path():
    """The MCP mount's general form of the same claim: no tool input names a root or a path."""
    from mendel_api.agent.tools import TOOLS

    assert TOOLS, "no tool is declared: the scan reads nothing"
    offenders = [f"{name}.{field}" for name, tool in TOOLS.items()
                 for field in tool.input.model_fields
                 if field.endswith("_root") or field.endswith("_path")]
    assert offenders == [], f"an MCP tool takes a filesystem path: {offenders}"


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
