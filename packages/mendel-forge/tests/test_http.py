import json

from fastapi.testclient import TestClient
from mendel_forge.cli import main
from mendel_forge.http import app

client = TestClient(app)


def test_sources_over_http_matches_the_cli_json(capsys):
    """The claim the whole two-transport split rests on. If these ever differ, one of them
    has grown logic, and the GUI in Plan 3 will be built against the wrong one."""
    main(["--json", "sources"])
    from_cli = json.loads(capsys.readouterr().out)
    from_http = client.get("/sources").json()
    assert from_cli == from_http


def test_drafting_over_http_matches_the_cli_json(capsys, tmp_path):
    body = {
        "ref": "nf-core:fastqc",
        "name": "a",
        "version": "0.12.1",
        "registry_root": "registry",
        "source_root": "vendor",
        "workspace_root": str(tmp_path / "a"),
    }
    from_http = client.post("/drafts", json=body).json()

    main(["--json", "draft", "nf-core:fastqc", "--name", "b", "--version", "0.12.1",
          "--workspace", str(tmp_path / "b")])
    from_cli = json.loads(capsys.readouterr().out)

    from_http.pop("name")
    from_cli.pop("name")
    assert from_cli == from_http


def test_a_refusal_becomes_a_422_carrying_the_code():
    response = client.post(
        "/drafts",
        json={
            "ref": "nonesuch:x",
            "name": "x",
            "registry_root": "registry",
            "source_root": "vendor",
            "workspace_root": "/tmp/x",
        },
    )
    assert response.status_code == 422
    assert "MF0001" in response.json()["detail"]


def test_the_app_is_mountable():
    """Plan 3's mendel-api mounts this rather than reimplementing it."""
    from fastapi import FastAPI

    parent = FastAPI()
    parent.mount("/forge", app)
    assert TestClient(parent).get("/forge/sources").status_code == 200


def test_no_route_contains_a_branch():
    """A branch in a transport is logic the other transport does not have.

    Read off the source rather than asserted in prose: the equivalence tests above compare
    two payloads today, and this one is what keeps them comparable tomorrow.
    """
    import inspect

    import mendel_forge.http as http_module

    source = inspect.getsource(http_module)
    body = source.split("app = FastAPI(")[1]
    routes = body.split("@app.")[2:]  # [0] is the FastAPI(...) tail, [1] the error handler
    for route in routes:
        assert " if " not in route and "\n    if" not in route, f"a route branches:\n{route}"
