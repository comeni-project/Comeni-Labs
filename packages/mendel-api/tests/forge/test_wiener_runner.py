"""Mendel's one call to Wiener, against a fake transport: no live Wiener in tests."""

import json

import httpx
import pytest
from mendel_api.services import wiener_runner
from mendel_api.services.wiener_runner import WienerRunner
from mendel_api.settings import settings
from mendel_forge.runner import RunnerUnavailable
from pydantic import SecretStr

TOKEN = "wiener-guard-token-0123"


def _runner(handler) -> WienerRunner:
    return WienerRunner("http://wiener:8001", TOKEN,
                        httpx.Client(transport=httpx.MockTransport(handler)))


def test_submit_uploads_then_runs_with_the_bearer_token():
    seen = []

    def handler(request):
        seen.append(request)
        if request.url.path == "/api/artifacts":
            return httpx.Response(201, json={"artifact_id": "a1"})
        return httpx.Response(202, json={"run_id": "r1"})

    assert _runner(handler).submit(b"zip", "forge test", {"reads": "https://x"}) == "r1"
    assert [r.url.path for r in seen] == ["/api/artifacts", "/api/runs"]
    assert all(r.headers["authorization"] == f"Bearer {TOKEN}" for r in seen)
    assert json.loads(seen[1].content) == {"artifact_id": "a1", "params": {"reads": "https://x"}}


def test_a_refusal_raises_with_its_reason():
    handler = lambda request: httpx.Response(422, json={"detail": "missing reads"})  # noqa: E731
    with pytest.raises(RunnerUnavailable, match="missing reads"):
        _runner(handler).state("r1")


def test_an_unreachable_wiener_never_says_the_token():
    def handler(request):
        raise httpx.ConnectError(f"no route, {request.headers['authorization']}")

    with pytest.raises(RunnerUnavailable) as caught:
        _runner(handler).state("r1")
    assert TOKEN not in str(caught.value)


def test_results_reads_every_page():
    def handler(request):
        after = int(request.url.params["after"])
        files = [{"process": "fastqc", "name": f"{n}.zip"} for n in range(after, min(after + 200, 250))]
        return httpx.Response(200, json={"files": files, "total": 250, "published": True})

    found = _runner(handler).results("r1")
    assert len(found) == 250 and found[0] == "fastqc/0.zip" and found[-1] == "fastqc/249.zip"


def test_state_reads_the_runs_phase():
    handler = lambda request: httpx.Response(200, json={"phase": "running"})  # noqa: E731
    assert _runner(handler).state("r1") == "running"


def test_no_url_means_no_runner(monkeypatch):
    monkeypatch.setattr(settings, "wiener_url", "")
    assert wiener_runner.runner() is None


def test_a_url_means_a_runner(monkeypatch):
    monkeypatch.setattr(settings, "wiener_url", "http://wiener:8001")
    monkeypatch.setattr(settings, "wiener_token", SecretStr(TOKEN))
    assert isinstance(wiener_runner.runner(), WienerRunner)
