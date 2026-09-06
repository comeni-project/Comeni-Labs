"""The upstream credential reaches the requests that spend it.

**This is a guard over a defect that shipped, not a precaution.** Both adapters declared
`token: str | None = None`, both built a correct `Authorization` header from it, and every
construction site in the API spelled `adapter_for(client)` — so the parameter was never once
filled. The authenticated path was dead code that read as working, and the symptom was not an
error: it was sixty requests an hour against a catalogue that costs two thousand, which looks
exactly like a slow upstream.

So the assertions here are deliberately at two levels. `open_adapter` is the *only* constructor
that fills the credential, and the header tests drive a real `sync()` per adapter and read what
went out — because a constructor storing a token it never sends would pass a signature check.
"""

import httpx
import pytest
from mendel_forge import sources
from mendel_forge.sources.base import BaseSourceAdapter

from tests.test_source_nfcore_catalogue import _handler as _nfcore_handler
from tests.test_source_pegi3s import _handler as _pegi3s_handler

TOKEN = "probe-token-not-a-real-credential"


def _recording(handler):
    """The adapter's own fixture handler, with every request's headers kept."""
    seen: list[httpx.Request] = []

    async def record(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return await handler(request)

    return record, seen


@pytest.mark.parametrize(
    ("source", "handler"),
    [("nf-core", _nfcore_handler), ("pegi3s", _pegi3s_handler)],
)
@pytest.mark.asyncio
async def test_a_configured_token_reaches_github(source, handler):
    """Every GitHub request carries the bearer, and it came from the environment.

    Reverting `open_adapter` to `kinds[name](client)` — the spelling both call sites used —
    fails here with the header absent on every request.
    """
    record, seen = _recording(handler())
    client = httpx.AsyncClient(transport=httpx.MockTransport(record))
    async with client:
        await sources.open_adapter(source, client, env={sources.GITHUB_TOKEN: TOKEN}).sync()

    github = [r for r in seen if "api.github.com" in str(r.url)]
    assert github, f"{source} made no GitHub request; this test would assert nothing"
    for request in github:
        assert request.headers.get("Authorization") == f"Bearer {TOKEN}", str(request.url)


@pytest.mark.parametrize(
    ("source", "handler"),
    [("nf-core", _nfcore_handler), ("pegi3s", _pegi3s_handler)],
)
@pytest.mark.asyncio
async def test_no_token_sends_no_header(source, handler):
    """Public development must work unauthenticated, and `Bearer ` is worse than nothing."""
    record, seen = _recording(handler())
    client = httpx.AsyncClient(transport=httpx.MockTransport(record))
    async with client:
        await sources.open_adapter(source, client, env={}).sync()

    assert seen, "no request was made; this test would assert nothing"
    assert not any("Authorization" in r.headers for r in seen)


def test_an_empty_setting_is_not_a_token():
    """`COMENI_FORGE_GITHUB_TOKEN=` is what a copied `.env.example` actually holds."""
    assert sources.upstream_token({sources.GITHUB_TOKEN: ""}) is None
    assert sources.upstream_token({sources.GITHUB_TOKEN: "   "}) is None
    assert sources.upstream_token({}) is None
    assert sources.upstream_token({sources.GITHUB_TOKEN: f"  {TOKEN} "}) == TOKEN


def test_the_credential_lives_on_the_base_so_a_new_adapter_inherits_it():
    """It was a subclass concern twice over, and both copies were unreachable.

    A third adapter written by somebody who has not read this file gets the credential and
    `_auth()` from the base or the class does not construct — which is the difference between
    a convention and a mechanism.
    """
    assert "token" in BaseSourceAdapter.__init__.__code__.co_varnames
    for kind in sources.adapters().values():
        assert issubclass(kind, BaseSourceAdapter)
        assert kind(None, token=TOKEN)._auth() == {"Authorization": f"Bearer {TOKEN}"}
        assert kind(None)._auth() == {}
