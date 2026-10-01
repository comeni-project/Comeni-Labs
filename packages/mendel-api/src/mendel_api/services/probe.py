"""Asking an endpoint whether it is there, and what it holds (spec §6). **No prompt is ever sent**.

Moved here from `routes/health.py` so the health page and Settings → Models ask the same way.
"""

import asyncio
import contextlib

import httpx

PROBE_SECONDS = 2.0
"""How long the model probe waits before saying *did not answer*.

**Short on purpose.** This is a health endpoint, not a request: a model that takes twelve
seconds to accept a connection is a model an operator needs told about, and a probe that waited
for it would make the page that reports the problem hang on the problem.
"""


async def answers(base_url: str) -> bool:
    """Open a socket to the configured endpoint. **No request, and no model name.**

    A `GET /` would be an Ollama-shaped assumption and a completion would cost a generation;
    what is being asked is *is anything listening there*, and a TCP connect answers exactly
    that without knowing whose server it is.
    """
    from urllib.parse import urlsplit

    parts = urlsplit(base_url if "//" in base_url else f"//{base_url}")
    if not parts.hostname:
        return False
    port = parts.port or (443 if parts.scheme == "https" else 80)
    try:
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(parts.hostname, port), timeout=PROBE_SECONDS
        )
    except (TimeoutError, OSError):
        return False
    writer.close()
    with contextlib.suppress(Exception):
        await writer.wait_closed()
    return True


TRANSPORT: httpx.AsyncBaseTransport | None = None
"""A seam for tests: `httpx.MockTransport`. `None` is the real network."""

PREFIX = {"ollama": "ollama_chat/", "openai_compatible": "openai/"}
"""LiteLLM's prefix per server. `ollama_chat/`, not `ollama/`: issue 179."""


class ProbeFailed(Exception):
    pass


async def listed(endpoint: str, server: str | None, key: str | None = None) -> list[str]:
    """`GET <endpoint>/v1/models`. **No prompt is sent**: this asks what a server holds."""
    try:
        async with httpx.AsyncClient(timeout=PROBE_SECONDS, transport=TRANSPORT) as http:
            # An OpenAI-compatible endpoint is usually written with `/v1` already (review M2),
            # and one started with an API key wants it here too.
            base = endpoint.rstrip("/").removesuffix("/v1")
            headers = {"Authorization": f"Bearer {key}"} if key else {}
            answer = await http.get(base + "/v1/models", headers=headers)
            answer.raise_for_status()
            ids = [item["id"] for item in answer.json()["data"]]
    except (httpx.HTTPError, KeyError, TypeError, ValueError) as failed:
        raise ProbeFailed(type(failed).__name__) from None
    prefix = PREFIX.get(server or "", "")
    return sorted(prefix + i for i in ids)
