"""Forge tests, run by Wiener over HTTP: Mendel's one call to it (forge MVP 4, spec §2).

**Only `forge_tests` holds one**, and a guard says so. The builder's Run button is unchanged: the
browser carries a laboratory's pipeline, so nothing here can take a person's samplesheet.
"""

import httpx
from mendel_forge.runner import RunnerUnavailable, TestRunner

from mendel_api.settings import settings

TIMEOUT = 60.0
PAGE = 200


class WienerRunner:
    def __init__(self, url: str, token: str, client: httpx.Client | None = None) -> None:
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        self._client = client or httpx.Client(timeout=TIMEOUT)
        self._client.base_url = url
        self._client.headers.update(headers)

    def _call(self, method: str, path: str, **kw) -> dict:
        try:
            answer = self._client.request(method, path, **kw)
        except httpx.HTTPError as error:
            raise RunnerUnavailable(f"Wiener could not be reached: {type(error).__name__}") \
                from None
        if answer.status_code >= 400:
            raise RunnerUnavailable(f"Wiener refused {method} {path}: {answer.status_code} "
                                    f"{answer.text[:300]}")
        return answer.json()

    def submit(self, bundle: bytes, name: str, params: dict) -> str:
        stored = self._call("POST", "/api/artifacts", data={"name": name},
                            files={"bundle": ("pipeline.zip", bundle, "application/zip")})
        accepted = self._call("POST", "/api/runs", json={"artifact_id": stored["artifact_id"],
                                                         "params": params})
        return accepted["run_id"]

    def state(self, run_id: str) -> str:
        return self._call("GET", f"/api/runs/{run_id}")["phase"]

    def results(self, run_id: str) -> list[str]:
        found: list[str] = []
        while True:
            page = self._call("GET", f"/api/runs/{run_id}/results",
                              params={"after": len(found), "limit": PAGE})
            found += [f"{f['process']}/{f['name']}" for f in page["files"]]
            if not page["files"] or len(found) >= page["total"]:
                return found


def runner() -> TestRunner | None:
    """The installation's runner, or `None` when no Wiener is configured: tests say so."""
    if not settings.wiener_url:
        return None
    return WienerRunner(settings.wiener_url, settings.wiener_token.get_secret_value())
