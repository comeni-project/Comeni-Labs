"""Recorded HTTP exchanges and source fixtures for pegi3s."""

import base64
import json
from datetime import UTC, datetime

import httpx
from mendel_forge.sources.pegi3s import (
    Pegi3sAdapter,
)
from mendel_forge_tests.paths import FIXTURES as FORGE_FIXTURES

FIXTURES = FORGE_FIXTURES / "sources"


WHEN = datetime(2026, 9, 4, tzinfo=UTC)


COMMIT = "cccccccccccccccccccccccccccccccccccccccc"


SOURCE_BLOBS = {
    "s100fastqcdockerfile": "FROM ubuntu:22.04\nRUN apt-get install -y fastqc\n",
    "s101fastqcreadme": "# fastqc\n\nQuality control for sequencing reads.\n",
    "s200clustaldockerfile": "FROM debian:12\nRUN apt-get install -y clustalw\n",
    "s300prodigaldockerfile": "FROM ubuntu:22.04\nRUN apt-get install -y prodigal\n",
    "s301prodigalreadme": "# prodigal\n\nProkaryotic gene prediction.\n",
    "s400sedadockerfile": "FROM debian:12\nRUN apt-get install -y seda\n",
    "s401sedareadme": "# seda\n\nA desktop application for processing FASTA files.\n",
}


CENTRAL_BLOBS = {
    "m001metadatajson": "pegi3s_metadata.json",
    "m002dioobo": "pegi3s_dio.obo",
    "m003diodiaf": "pegi3s_dio.diaf",
}


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


def _repositories() -> list[dict]:
    """The namespace listing as the fixture pages it — a second opinion on the total."""
    return (
        _fixture("pegi3s_repositories_page1.json")["results"]
        + _fixture("pegi3s_repositories_page2.json")["results"]
    )


def _documented_tools() -> set[str]:
    """Which tools the `pegi3s/dockerfiles` fixture actually carries a directory for."""
    tree = _fixture("pegi3s_source_tree.json")["tree"]
    return {
        entry["path"].split("/", 1)[0]
        for entry in tree
        if entry["type"] == "blob" and "/" in entry["path"]
    }


def _handler(
    *, source_tree: str = "pegi3s_source_tree.json", blobs=None, fetched: list[str] | None = None
):
    """`fetched` collects every blob sha requested, so a test can assert *once per sync*."""
    extra = {**SOURCE_BLOBS, **(blobs or {})}
    fetched = fetched if fetched is not None else []

    async def handle(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "api.github.com" in url and "/commits/" in url:
            return httpx.Response(200, json={"sha": COMMIT})
        if "api.github.com" in url and "/git/trees/" in url:
            return httpx.Response(200, json=_fixture(source_tree))
        if "api.github.com" in url and "/git/blobs/" in url:
            sha = url.rsplit("/", 1)[-1]
            fetched.append(sha)
            # **`extra` first.** A test overriding a central file must actually override it.
            # Checking the on-disk map first is the precedence bug this suite has now hit
            # three times — the override is silently ignored and the test asserts against
            # unmodified fixture data, which passes for the wrong reason.
            if sha in extra:
                text = extra[sha]
            elif sha in CENTRAL_BLOBS:
                text = (FIXTURES / CENTRAL_BLOBS[sha]).read_text()
            else:
                text = ""
            return httpx.Response(
                200,
                json={
                    "encoding": "base64",
                    "content": base64.b64encode(text.encode()).decode(),
                },
            )
        if "/repositories?" in url and "page=2" not in url:
            return httpx.Response(200, json=_fixture("pegi3s_repositories_page1.json"))
        if "page=2" in url:
            return httpx.Response(200, json=_fixture("pegi3s_repositories_page2.json"))
        if "/tags" in url:
            name = url.split("/repositories/")[1].split("/tags")[0]
            return httpx.Response(200, json=_fixture(f"pegi3s_tags_{name}.json"))
        return httpx.Response(404, json={"url": url})

    return handle


def _adapter(handler=None) -> Pegi3sAdapter:
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler or _handler()))
    return Pegi3sAdapter(client, now=WHEN)


async def _digests(*, metadata: str | None = None, obo: str | None = None):
    """A sync with one central file swapped, returning `{ref: digest}`."""
    blobs = {}
    if metadata is not None:
        blobs["m001metadatajson"] = metadata
    if obo is not None:
        blobs["m002dioobo"] = obo
    got = await Pegi3sAdapter(
        httpx.AsyncClient(transport=httpx.MockTransport(_handler(blobs=blobs))), now=WHEN
    ).sync()
    return {i.ref: i.content_digest for i in got.items}
