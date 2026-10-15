"""Recorded HTTP exchanges and source fixtures for nfcore."""

import io
import json
import tarfile
from datetime import UTC, datetime

import httpx
from mendel_forge.catalogue import CatalogueItem
from mendel_forge.sources.nfcore_catalogue import (
    OWNER,
    REPO,
    NfCoreAdapter,
)
from mendel_forge_tests.paths import FIXTURES as FORGE_FIXTURES

FIXTURES = FORGE_FIXTURES / "sources"


WHEN = datetime(2026, 9, 4, tzinfo=UTC)


COMMIT = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"


META = {
    "b101fastqcmeta": "nfcore_meta_fastqc.yml",
    "b201sortmeta": "nfcore_meta_sort.yml",
}


def _tree(name: str = "nfcore_tree.json") -> dict:
    return json.loads((FIXTURES / name).read_text())


def _expected_refs(tree: dict) -> set[str]:
    """What the fixture *says* is a module, computed from its own contents.

    A leaf directory under `modules/nf-core/` holding both `main.nf` and `meta.yml`. Written out
    here rather than imported from the adapter, so this is a second opinion rather than the
    adapter agreeing with itself.
    """
    files: dict[str, set[str]] = {}
    for entry in tree["tree"]:
        path = entry["path"]
        if entry["type"] != "blob" or not path.startswith("modules/nf-core/"):
            continue
        relative = path.removeprefix("modules/nf-core/")
        if "/" not in relative:
            continue
        ref, _, filename = relative.rpartition("/")
        files.setdefault(ref, set()).add(filename)
    return {ref for ref, names in files.items() if {"main.nf", "meta.yml"} <= names}


def _contents(tree: dict, extra: dict[str, str]) -> dict[str, str]:
    """The fixture tree as `{path: text}`, which is what the archive serves.

    **The tree fixture stays the declaration of what exists**, so `_expected_refs` still reads
    the same file and remains a second opinion rather than the adapter agreeing with itself.
    What changed is only how the adapter gets the bytes.

    Overrides are still keyed by the fixture's blob sha, because that is how the tests that use
    them name a file. The adapter recomputes its own sha from the content it receives — as git
    does — so those two shas are unrelated and nothing here should assert on either.
    """
    files: dict[str, str] = {}
    for entry in tree["tree"]:
        if entry["type"] != "blob":
            continue
        sha = entry["sha"]
        # `extra` first: a test overriding a file must actually override it. The first version
        # checked `META` first, so an override of `meta.yml` was silently ignored and the test
        # passed against the unmodified fixture.
        if sha in extra:
            files[entry["path"]] = extra[sha]
        elif sha in META:
            files[entry["path"]] = (FIXTURES / META[sha]).read_text()
        else:
            files[entry["path"]] = f"contents of {sha}\n"
    return files


def _tarball(files: dict[str, str]) -> bytes:
    """A gzipped tar shaped like GitHub's, root directory and all."""
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        for path, text in sorted(files.items()):
            payload = text.encode()
            info = tarfile.TarInfo(name=f"{OWNER}-{REPO}-{COMMIT[:7]}/{path}")
            info.size = len(payload)
            archive.addfile(info, io.BytesIO(payload))
    return buffer.getvalue()


def _handler(
    tree_name: str = "nfcore_tree.json",
    *,
    blobs: dict[str, str] | None = None,
    commit: str = COMMIT,
):
    """The repository at one commit: a sha, and an archive of every file.

    `commit` is a parameter because an upstream change moves the branch — a test that edits a
    file and leaves the sha where it was is describing something that cannot happen, and the
    adapter's own short-circuit (*the commit did not move, reuse the snapshot*) reads that as
    nothing having changed at all.
    """
    archive = _tarball(_contents(_tree(tree_name), blobs or {}))

    async def handle(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "/commits/" in url:
            return httpx.Response(200, json={"sha": commit})
        if "/tarball/" in url:
            return httpx.Response(200, content=archive)
        return httpx.Response(404)

    return handle


def _adapter(handler, **kw) -> NfCoreAdapter:
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return NfCoreAdapter(client, now=WHEN, **kw)


def _item(ref: str, snapshot) -> CatalogueItem:
    return next(i for i in snapshot.items if i.ref == ref)
