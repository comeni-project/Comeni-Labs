"""Drafting, the refusal, and that no path crosses the boundary.

**The catalogue tests left with the catalogue route** — `GET /sources` was deleted in the same
commit as `Sources.tsx`, and its assertions live in `test_tools_route.py`. The POST stays,
because drafting is still started from a row.
"""

from fastapi.testclient import TestClient
from mendel_api.main import create_app


def test_drafting_twice_refuses_with_its_code(tmp_path, monkeypatch):
    from mendel_api.settings import settings

    monkeypatch.setattr(settings, "workspace_root", tmp_path / "workspace")
    client = TestClient(create_app())
    body = {"ref": "nf-core:samtools/faidx", "name": "faidx", "version": "1.24"}

    assert client.post("/api/sources/draft", json=body).status_code == 200
    again = client.post("/api/sources/draft", json=body)
    assert again.status_code == 422
    assert "MF0010" in again.json()["detail"]


def test_the_draft_body_cannot_carry_a_path(tmp_path, monkeypatch):
    """**The constraint this phase exists to honour.** `extra="forbid"` is what makes a request
    naming `workspace_root` a 422 rather than a second answer to where drafts live."""
    from mendel_api.settings import settings

    monkeypatch.setattr(settings, "workspace_root", tmp_path / "workspace")
    client = TestClient(create_app())
    sent = client.post(
        "/api/sources/draft",
        json={
            "ref": "nf-core:samtools/faidx",
            "name": "x",
            "version": "1",
            "workspace_root": "/tmp/anywhere",
        },
    )
    assert sent.status_code == 422
    # And nothing was written where the caller asked, nor where it did not.
    assert not (tmp_path / "workspace" / "x").exists()
