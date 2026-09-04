"""The PEGiS adapter: a container namespace joined to its Dockerfile repository.

This is the source the `Source` protocol was designed against and never had — issue #65 — and
the tests that matter are the ones about **honesty rather than coverage**: an image with no
source stays visible and says why, `latest` never becomes a version, and a version that is
unknown is `None` rather than a guess.
"""

import base64
import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from mendel_forge.catalogue import ContainerRef, Freshness
from mendel_forge.sources.base import UpstreamError
from mendel_forge.sources.pegi3s import (
    ALIASES,
    SEMVER,
    Pegi3sAdapter,
    _proved_version,
    _sortable,
    _why_not,
)

FIXTURES = Path(__file__).parent / "fixtures" / "sources"
WHEN = datetime(2026, 9, 4, tzinfo=UTC)
COMMIT = "cccccccccccccccccccccccccccccccccccccccc"

SOURCE_BLOBS = {
    "s100fastqcdockerfile": "FROM ubuntu:22.04\nRUN apt-get install -y fastqc\n",
    "s101fastqcreadme": "# fastqc\n\nQuality control for sequencing reads.\n",
    "s200clustaldockerfile": "FROM debian:12\nRUN apt-get install -y clustalw\n",
    "s300prodigaldockerfile": "FROM ubuntu:22.04\nRUN apt-get install -y prodigal\n",
    "s301prodigalreadme": "# prodigal\n\nProkaryotic gene prediction.\n",
}


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


def _repositories() -> list[dict]:
    """The namespace listing as the fixture pages it — a second opinion on the total."""
    return _fixture("pegi3s_repositories_page1.json")["results"] + _fixture(
        "pegi3s_repositories_page2.json"
    )["results"]


def _documented_tools() -> set[str]:
    """Which tools the `pegi3s/dockerfiles` fixture actually carries a directory for."""
    tree = _fixture("pegi3s_source_tree.json")["tree"]
    return {
        entry["path"].split("/", 1)[0]
        for entry in tree
        if entry["type"] == "blob" and "/" in entry["path"]
    }


def _handler(*, source_tree: str = "pegi3s_source_tree.json", blobs=None):
    extra = {**SOURCE_BLOBS, **(blobs or {})}

    async def handle(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "api.github.com" in url and "/commits/" in url:
            return httpx.Response(200, json={"sha": COMMIT})
        if "api.github.com" in url and "/git/trees/" in url:
            return httpx.Response(200, json=_fixture(source_tree))
        if "api.github.com" in url and "/git/blobs/" in url:
            sha = url.rsplit("/", 1)[-1]
            return httpx.Response(
                200,
                json={
                    "encoding": "base64",
                    "content": base64.b64encode(extra.get(sha, "").encode()).decode(),
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


# ── discovered is what the namespace lists ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_every_public_repository_is_discovered():
    got = await _adapter().sync()
    assert {i.ref for i in got.items} == {r["name"] for r in _repositories()}


@pytest.mark.asyncio
async def test_pagination_reaches_the_second_page():
    """A namespace listing that stopped at page one would report a total that is simply
    smaller than the namespace."""
    got = await _adapter().sync()
    assert "prodigal" in {i.ref for i in got.items}, "the second page was never read"


# ── unsupported entries stay visible and say why ───────────────────────────────────────


@pytest.mark.asyncio
async def test_an_image_with_no_source_directory_is_kept_and_explained():
    """§4.2's rule. Making it disappear is how a catalogue starts lying about its own size."""
    got = await _adapter().sync()
    orphan = next(i for i in got.items if i.ref == "orphanimage")
    assert not orphan.adaptable
    assert orphan.unsupported_reason
    assert orphan.freshness(None) is Freshness.UNSUPPORTED


@pytest.mark.asyncio
async def test_an_image_with_no_manifest_says_so_rather_than_saying_no_source():
    """The catalogue's orphan has both problems, and the image one is reported first: a tool
    you cannot run is not worth documenting."""
    got = await _adapter().sync()
    orphan = next(i for i in got.items if i.ref == "orphanimage")
    assert "no pullable" in orphan.unsupported_reason


def test_each_way_of_being_unsupported_says_something_different():
    """Three branches, and the catalogue fixture only reaches one of them.

    An image with no source has nothing to write a contract *from*; source with no pullable
    image has nothing to *run*; a directory with neither a Dockerfile nor a README describes
    nothing. One shared "unsupported" would leave a reader guessing which, so each is asserted
    to be distinct rather than merely non-empty.
    """
    pullable = (
        ContainerRef(
            registry="docker.io", repository="pegi3s/x", tag="1.0", digest="sha256:a"
        ),
    )
    no_image = _why_not((), {"Dockerfile": "s1"})
    no_source = _why_not(pullable, {})
    nothing_useful = _why_not(pullable, {"LICENSE": "s2"})
    fine = _why_not(pullable, {"Dockerfile": "s1", "README.md": "s2"})

    assert fine is None
    assert no_image and no_source and nothing_useful
    assert len({no_image, no_source, nothing_useful}) == 3, "two reasons read the same"
    assert "no pullable" in no_image
    assert "no matching directory" in no_source
    assert "neither a Dockerfile nor a README" in nothing_useful


def test_a_readme_alone_is_enough_to_be_adaptable():
    """A Dockerfile is not required. Some PEGiS tools document what the image does without
    shipping the recipe, and prose is exactly what a dossier is built from here."""
    pullable = (
        ContainerRef(
            registry="docker.io", repository="pegi3s/x", tag="1.0", digest="sha256:a"
        ),
    )
    assert _why_not(pullable, {"README.md": "s1"}) is None


@pytest.mark.asyncio
async def test_adaptable_and_discovered_differ_and_both_are_derivable():
    got = await _adapter().sync()
    counts = got.counts()
    assert counts.discovered == len(_repositories())
    assert counts.adaptable == len(
        [r for r in _repositories() if r["name"] in _documented_tools()]
    )
    assert counts.discovered != counts.adaptable, "the fixture no longer exercises the gap"
    assert counts.adaptable + counts.unsupported == counts.discovered


# ── latest is an alias, never a version ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_a_semantic_tag_becomes_the_version():
    got = await _adapter().sync()
    fastqc = next(i for i in got.items if i.ref == "fastqc")
    assert fastqc.latest_version == "0.11.9"


@pytest.mark.asyncio
async def test_an_image_tagged_only_latest_has_no_proved_version():
    """A publisher can repoint `latest` tomorrow. Writing it here would turn an alias into a
    claim nobody made."""
    got = await _adapter().sync()
    prodigal = next(i for i in got.items if i.ref == "prodigal")
    assert prodigal.latest_version is None


@pytest.mark.asyncio
async def test_an_unknown_version_does_not_make_a_tool_unadaptable():
    """An unknown version and a knowable digest are different facts. The image can still be
    pinned, and the version becomes something a reviewer resolves."""
    got = await _adapter().sync()
    prodigal = next(i for i in got.items if i.ref == "prodigal")
    assert prodigal.adaptable
    assert prodigal.container_refs[0].digest


def test_version_ordering_is_numeric_not_lexicographic():
    """`1.10` after `1.9`, which a string sort gets wrong."""
    assert _proved_version(
        [{"name": "1.9", "images": [{"digest": "d"}]}, {"name": "1.10", "images": [{"d": 1}]}]
    ) == "1.10"
    assert _sortable("1.10") > _sortable("1.9")


def test_an_alias_is_never_a_version():
    for alias in ("latest", "stable", "dev", "main", "master", "edge"):
        assert _proved_version([{"name": alias}]) is None, alias


def test_the_alias_list_is_redundant_only_while_semver_is_strict():
    """`ALIASES` cannot currently fire, and this is what says so out loud.

    Anchored `SEMVER` rejects every name in the set, so deleting the alias check changes no
    answer — found by reverting it and watching the tests stay green, which is the failure mode
    A14 exists for. Rather than delete a line that becomes load-bearing the moment somebody
    loosens the regex, this asserts the *relationship*: every alias must already be rejected by
    `SEMVER` alone. Loosen `SEMVER` and this fails, naming the alias that has just become the
    only thing standing between a moving tag and a version claim.
    """
    slipped = sorted(alias for alias in ALIASES if SEMVER.match(alias))
    assert slipped == [], (
        "SEMVER now accepts these alias names, so the ALIASES check has stopped being "
        f"redundant and started being the only guard: {slipped}"
    )


def test_a_floating_numeric_tag_is_the_limit_and_is_not_pretended_away():
    """`pegi3s/tool:1` meaning "latest 1.x" is an alias wearing a version's clothes.

    Nothing here can tell it from a release by name, so it *is* reported as a version. The test
    exists so the limit is recorded rather than discovered — the digest recorded beside the
    version is what makes it survivable.
    """
    assert _proved_version([{"name": "1", "images": [{"digest": "d"}]}]) == "1"


def test_a_prerelease_sorts_below_its_release():
    assert _sortable("2.1") > _sortable("2.1-rc")


@pytest.mark.asyncio
async def test_the_fixture_version_is_the_higher_of_two():
    got = await _adapter().sync()
    clustalw = next(i for i in got.items if i.ref == "clustalw")
    assert clustalw.latest_version == "1.10"


# ── containers: one platform pinned, all of them kept ──────────────────────────────────


@pytest.mark.asyncio
async def test_linux_amd64_is_first_and_the_others_survive():
    """Dropping the other platforms makes a future arm64 decision unrecoverable without a
    full re-sync."""
    got = await _adapter().sync()
    fastqc = next(i for i in got.items if i.ref == "fastqc")
    assert fastqc.container_refs[0].platform == "linux/amd64"
    assert "linux/arm64" in {ref.platform for ref in fastqc.container_refs}


@pytest.mark.asyncio
async def test_a_container_is_pinned_by_digest():
    """A tag is repointable; a digest is the only reference that makes a run reproducible."""
    got = await _adapter().sync()
    fastqc = next(i for i in got.items if i.ref == "fastqc")
    assert "@sha256:" in fastqc.container_refs[0].pinned()


@pytest.mark.asyncio
async def test_a_tag_with_no_manifest_is_not_recorded_as_a_pin():
    """Docker Hub knows the name and holds no manifest; recording it would be a pin that
    fails at run time."""
    got = await _adapter().sync()
    orphan = next(i for i in got.items if i.ref == "orphanimage")
    assert orphan.container_refs == ()


# ── capabilities are the mirror image of nf-core's ─────────────────────────────────────


@pytest.mark.asyncio
async def test_the_source_claims_no_nextflow_and_no_structured_ports():
    """A scaffold reads these and behaves differently: with no Nextflow upstream a module has
    to be authored, and with no structured ports every port is a hole."""
    got = await _adapter().sync()
    assert got.items
    for item in got.items:
        assert not item.capabilities.supplies_nextflow
        assert not item.capabilities.supplies_structured_ports
        assert item.capabilities.supplies_container_digest
        assert not item.capabilities.supplies_tests


# ── the digest covers image and documentation together ─────────────────────────────────


@pytest.mark.asyncio
async def test_a_rewritten_readme_moves_the_digest():
    """A rewritten README is new evidence for ports that were inferred from prose, so it is a
    reason to re-adapt."""
    before = await _adapter().sync()

    moved = _fixture("pegi3s_source_tree.json")
    for entry in moved["tree"]:
        if entry["path"] == "fastqc/README.md":
            entry["sha"] = "s101fastqcreadme-CHANGED"

    async def handle(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "api.github.com" in url and "/git/trees/" in url:
            return httpx.Response(200, json=moved)
        return await _handler()(request)

    after = await Pegi3sAdapter(
        httpx.AsyncClient(transport=httpx.MockTransport(handle)), now=WHEN
    ).sync()

    was = {i.ref: i.content_digest for i in before.items}
    now = {i.ref: i.content_digest for i in after.items}
    assert was["fastqc"] != now["fastqc"]
    assert was["clustalw"] == now["clustalw"], "an unrelated tool's digest moved"


# ── refusing rather than under-reporting ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_a_truncated_source_tree_refuses():
    """Every image would read as undocumented, which is a false total rather than a small one."""
    truncated = {**_fixture("pegi3s_source_tree.json"), "truncated": True}

    async def handle(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "api.github.com" in url and "/git/trees/" in url:
            return httpx.Response(200, json=truncated)
        return await _handler()(request)

    with pytest.raises(UpstreamError, match="MF0200"):
        await Pegi3sAdapter(
            httpx.AsyncClient(transport=httpx.MockTransport(handle)), now=WHEN
        ).sync()


# ── the bundle ─────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_a_bundle_carries_the_source_directory():
    snapshot = await _adapter().sync()
    fastqc = next(i for i in snapshot.items if i.ref == "fastqc")
    bundle = await _adapter().bundle(fastqc)
    assert {f.path for f in bundle.files} == {"Dockerfile", "README.md"}


@pytest.mark.asyncio
async def test_a_bundle_reads_the_readme_before_the_dockerfile():
    """A model reading the Dockerfile first has to infer what the tool does from `apt-get`
    lines."""
    snapshot = await _adapter().sync()
    fastqc = next(i for i in snapshot.items if i.ref == "fastqc")
    bundle = await _adapter().bundle(fastqc)
    texts = [e.excerpt.text for e in bundle.evidence]
    assert any("Quality control" in t for t in texts)
    readme_at = next(i for i, t in enumerate(texts) if "Quality control" in t)
    dockerfile_at = next(i for i, t in enumerate(texts) if "FROM ubuntu" in t)
    assert readme_at < dockerfile_at


@pytest.mark.asyncio
async def test_the_container_is_the_first_evidence():
    """What the thing *is* comes before what it says about itself."""
    snapshot = await _adapter().sync()
    fastqc = next(i for i in snapshot.items if i.ref == "fastqc")
    bundle = await _adapter().bundle(fastqc)
    assert bundle.evidence[0].kind == "container"
    assert bundle.evidence[0].id == "E001"


@pytest.mark.asyncio
async def test_no_nextflow_is_written_by_the_adapter():
    """The adapter proves what the container is. A generated process would be a proposal
    wearing a source's authority."""
    snapshot = await _adapter().sync()
    fastqc = next(i for i in snapshot.items if i.ref == "fastqc")
    bundle = await _adapter().bundle(fastqc)
    assert not any(f.path.endswith(".nf") for f in bundle.files)
    assert all("process " not in f.text for f in bundle.files)


@pytest.mark.asyncio
async def test_bundling_an_unsupported_entry_refuses_with_its_reason():
    snapshot = await _adapter().sync()
    orphan = next(i for i in snapshot.items if i.ref == "orphanimage")
    with pytest.raises(UpstreamError) as raised:
        await _adapter().bundle(orphan)
    assert orphan.unsupported_reason in str(raised.value)


@pytest.mark.asyncio
async def test_every_bundled_file_is_verbatim():
    snapshot = await _adapter().sync()
    fastqc = next(i for i in snapshot.items if i.ref == "fastqc")
    bundle = await _adapter().bundle(fastqc)
    assert bundle.files
    assert all(f.verbatim for f in bundle.files)


@pytest.mark.asyncio
async def test_no_locator_is_an_absolute_host_path():
    snapshot = await _adapter().sync()
    fastqc = next(i for i in snapshot.items if i.ref == "fastqc")
    bundle = await _adapter().bundle(fastqc)
    for numbered in bundle.evidence:
        assert not numbered.excerpt.locator.startswith("/"), numbered.excerpt.locator


@pytest.mark.asyncio
async def test_the_observation_carries_the_prose_a_model_will_read():
    adapter = _adapter()
    snapshot = await adapter.sync()
    fastqc = next(i for i in snapshot.items if i.ref == "fastqc")
    observation = adapter.observe(await _adapter().bundle(fastqc))
    assert observation.source == "pegi3s"
    assert observation.ref_id == "pegi3s:fastqc"
    assert any("Quality control" in e.text for e in observation.prose)
