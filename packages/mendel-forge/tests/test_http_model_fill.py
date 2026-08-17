"""The HTTP transport over the same models the CLI uses.

If this test needs to construct anything the CLI does not, logic has leaked into a transport.
"""

from fastapi.testclient import TestClient
from mendel_forge.http import app


def test_the_route_exists() -> None:
    assert "/drafts/fill-with-model" in {route.path for route in app.routes}


def test_a_bad_request_is_a_422_not_a_traceback() -> None:
    client = TestClient(app)
    assert client.post("/drafts/fill-with-model", json={"name": "x"}).status_code == 422


def test_it_takes_the_same_request_model_the_cli_builds() -> None:
    """The property the module's docstring claims: one request model, two transports."""
    from mendel_forge import ops

    schema = app.openapi()["components"]["schemas"]["ModelFillRequest"]
    assert set(ops.ModelFillRequest.model_fields) == set(schema["properties"])
