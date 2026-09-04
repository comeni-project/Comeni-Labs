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
from mendel_forge.sources.dio import parse_obo
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
    "s400sedadockerfile": "FROM debian:12\nRUN apt-get install -y seda\n",
    "s401sedareadme": "# seda\n\nA desktop application for processing FASTA files.\n",
}

CENTRAL_BLOBS = {
    "m001metadatajson": "pegi3s_metadata.json",
    "m002dioobo": "pegi3s_dio.obo",
    "m003diodiaf": "pegi3s_dio.diaf",
}
"""PEGiS's three central files, by the blob sha the source tree fixture gives them.

Read from disk rather than inlined so the OBO and DIAF fixtures stay in the format upstream
actually publishes — a tab-separated assignment file written as a Python string literal is one
`\\t` away from silently being a space-separated one."""


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


# ── the central metadata join ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_the_three_central_files_are_fetched_once_from_one_commit():
    """§2. Fetching `dio.obo` from one commit and `dio.diaf` from another lets an assignment
    reference a term the ontology read does not carry — which looks exactly like upstream
    corruption and is entirely self-inflicted.

    Also: once per sync, not once per tool. Five tools, three central blobs.
    """
    fetched: list[str] = []
    trees: list[str] = []
    inner = _handler(fetched=fetched)

    async def handle(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "api.github.com" in url and "/git/trees/" in url:
            trees.append(url)
        return await inner(request)

    await Pegi3sAdapter(
        httpx.AsyncClient(transport=httpx.MockTransport(handle)), now=WHEN
    ).sync()

    for sha in CENTRAL_BLOBS:
        assert fetched.count(sha) == 1, f"{sha} was fetched {fetched.count(sha)} times"
    assert len(trees) == 1, "the source tree was read more than once per sync"
    assert all(COMMIT in url for url in trees), "a tree was read from a moving branch"


@pytest.mark.asyncio
async def test_metadata_enriches_the_description_and_the_version():
    """`metadata.json` is what PEGiS maintains; the Hub blurb is often stale or empty."""
    got = await _adapter().sync()
    fastqc = next(i for i in got.items if i.ref == "fastqc")
    assert fastqc.summary == "A quality control tool for high throughput sequence data."
    assert fastqc.latest_version == "0.11.9"
    assert fastqc.documentation_url.startswith(
        "https://www.bioinformatics.babraham.ac.uk"
    ), "manual_url did not become the documentation link"


@pytest.mark.asyncio
async def test_source_facts_are_preserved_verbatim():
    got = await _adapter().sync()
    fastqc = next(i for i in got.items if i.ref == "fastqc")
    facts = {f.name: f.value for f in fastqc.source_facts}
    assert facts["invocation_general"].startswith("docker run")
    assert facts["usual_invocation_specific"].startswith("fastqc /data")
    assert facts["singularity"] == "OK"
    assert facts["test_result"] == "reads_fastqc.html"


@pytest.mark.asyncio
async def test_input_data_type_becomes_a_hint_and_not_a_port():
    """PEGiS stating what a tool eats, in its own words. §8: not a port, not a type id."""
    got = await _adapter().sync()
    fastqc = next(i for i in got.items if i.ref == "fastqc")
    assert fastqc.input_hints == ("FASTQ", "BAM")
    assert fastqc.output_hints == (), "an output port was invented from a category"


@pytest.mark.asyncio
async def test_a_tool_with_no_metadata_entry_stays_visible_and_is_reported():
    """§7's first rule. An image PEGiS publishes and has not documented centrally is a real,
    pullable tool with less evidence behind it."""
    got = await _adapter().sync()
    prodigal = next(i for i in got.items if i.ref == "prodigal")
    assert prodigal.adaptable
    assert prodigal.source_facts == ()
    assert prodigal.classifications == ()
    assert any(
        w.code == "MF0208" and w.subject == "prodigal" for w in got.warnings
    ), "no metadata-missing diagnostic"


# ── classification and hierarchical filtering ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_a_tool_carries_its_direct_classification():
    got = await _adapter().sync()
    fastqc = next(i for i in got.items if i.ref == "fastqc")
    direct = [c for c in fastqc.classifications if c.direct]
    assert [c.id for c in direct] == ["DIO:0000036"]
    assert direct[0].name == "Quality"
    assert direct[0].path == ("Data_type", "Sequences", "Short_reads", "Quality")


@pytest.mark.asyncio
async def test_a_tool_with_several_classifications_keeps_all_of_them():
    got = await _adapter().sync()
    seda = next(i for i in got.items if i.ref == "seda")
    assert sorted(c.id for c in seda.classifications if c.direct) == [
        "DIO:0000052",
        "DIO:0000060",
    ]


@pytest.mark.asyncio
async def test_an_assigned_child_is_discoverable_under_its_ancestors():
    """§6, and the whole point of splitting the ontology from the assignments.

    `fastqc` is assigned to `Quality` and must appear when somebody clicks `Short_reads`,
    `Sequences` or `Data_type` — three levels up.
    """
    got = await _adapter().sync()
    for ancestor in ("DIO:0000010", "DIO:0000004", "DIO:0000001"):
        assert "fastqc" in {i.ref for i in got.classified(ancestor)}, ancestor
    assert "fastqc" in {i.ref for i in got.classified("DIO:0000036")}


@pytest.mark.asyncio
async def test_an_unrelated_branch_does_not_collect_the_tool():
    """The other half: inheritance must go up, never sideways."""
    got = await _adapter().sync()
    assert "fastqc" not in {i.ref for i in got.classified("DIO:0000050")}


@pytest.mark.asyncio
async def test_direct_and_inherited_stay_distinguishable():
    """A reviewer needs to know which claim the source actually made. Flattening the two is
    the loss §6 forbids."""
    got = await _adapter().sync()
    fastqc = next(i for i in got.items if i.ref == "fastqc")
    assert {c.id for c in fastqc.classifications if not c.direct} == {
        "DIO:0000010",
        "DIO:0000004",
        "DIO:0000001",
    }
    assert all(c.ancestors for c in fastqc.classifications if c.direct)


@pytest.mark.asyncio
async def test_two_alignment_categories_do_not_merge():
    """`clustalw` is an *analysis* Alignment; `seda` carries the *data* one. Same display
    name, different branches — keying on the name would put each under the other's filter."""
    got = await _adapter().sync()
    clustalw = next(i for i in got.items if i.ref == "clustalw")
    seda = next(i for i in got.items if i.ref == "seda")

    assert [c.id for c in clustalw.classifications if c.direct] == ["DIO:0000051"]
    assert "DIO:0000052" in {c.id for c in seda.classifications if c.direct}
    assert "clustalw" not in {i.ref for i in got.classified("DIO:0000052")}
    assert "seda" not in {i.ref for i in got.classified("DIO:0000051")}

    names = {c.name for c in (*clustalw.classifications, *seda.classifications)}
    assert "Alignment" in names, "the fixture no longer exercises the duplicate name"


@pytest.mark.asyncio
async def test_a_tool_with_no_assignment_stays_in_the_catalogue():
    got = await _adapter().sync()
    prodigal = next(i for i in got.items if i.ref == "prodigal")
    assert prodigal.classifications == ()


# ── the filter tree ────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_the_filter_tree_is_the_whole_vocabulary_not_just_what_is_used():
    """A tree assembled from the classifications in use is missing every branch nobody has
    been assigned to yet, which makes the filter narrower than the vocabulary — silently."""
    got = await _adapter().sync()
    ontology, _ = parse_obo((FIXTURES / "pegi3s_dio.obo").read_text())
    assert {node.id for node in got.filters} == set(ontology.terms)

    unused = next(n for n in got.filters if n.id == "DIO:0000010")
    assert unused.direct_count == 0, "the fixture no longer has an unassigned branch"


@pytest.mark.asyncio
async def test_filter_nodes_carry_the_shape_a_ui_needs():
    got = await _adapter().sync()
    sequences = next(n for n in got.filters if n.id == "DIO:0000004")
    assert sequences.name == "Sequences"
    assert sequences.definition
    assert sequences.parents == ("DIO:0000001",)
    assert set(sequences.children) == {"DIO:0000010", "DIO:0000052"}
    assert sequences.path == ("Data_type", "Sequences")


@pytest.mark.asyncio
async def test_direct_counts_are_direct_only():
    """`Sequences` has no tool assigned to it directly; two are beneath it. A node's total
    depends on which other filters are applied, which a snapshot cannot know."""
    got = await _adapter().sync()
    sequences = next(n for n in got.filters if n.id == "DIO:0000004")
    quality = next(n for n in got.filters if n.id == "DIO:0000036")
    assert sequences.direct_count == 0
    assert quality.direct_count == 1
    assert len(got.classified("DIO:0000004")) == 2


# ── diagnostics, not crashes ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_an_unknown_ontology_id_warns_and_the_sync_completes():
    got = await _adapter().sync()
    assert any(w.code == "MF0205" and "DIO:0009999" in w.detail for w in got.warnings)
    assert len(got.items) == len(_repositories()), "a bad assignment cost a tool"


@pytest.mark.asyncio
async def test_an_assignment_for_an_undiscovered_tool_fabricates_nothing():
    got = await _adapter().sync()
    assert "nosuchtool" not in {i.ref for i in got.items}
    assert any(w.code == "MF0207" and w.subject == "nosuchtool" for w in got.warnings)


@pytest.mark.asyncio
async def test_a_missing_central_file_degrades_rather_than_refusing():
    """Every tool loses its classifications for that sync; none loses its row."""
    stripped = _fixture("pegi3s_source_tree.json")
    stripped["tree"] = [e for e in stripped["tree"] if e["path"] != "metadata/dio.diaf"]
    inner = _handler()

    async def handle(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "api.github.com" in url and "/git/trees/" in url:
            return httpx.Response(200, json=stripped)
        return await inner(request)

    got = await Pegi3sAdapter(
        httpx.AsyncClient(transport=httpx.MockTransport(handle)), now=WHEN
    ).sync()

    assert len(got.items) == len(_repositories())
    assert all(i.classifications == () for i in got.items)
    assert any("dio.diaf" in w.detail for w in got.warnings)


# ── evidence: labelled, and direct only ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_a_classification_reaches_the_dossier_labelled_as_one():
    """§8. A dossier line reading "Sequences" beside a list of ports invites exactly the
    inference that rule forbids, so the sentence carries its own frame."""
    got = await _adapter().sync()
    fastqc = next(i for i in got.items if i.ref == "fastqc")
    said = [e.text for e in fastqc.evidence if "DIO:0000036" in e.text]
    assert said, "the classification never reached the evidence"
    assert "PEGiS classifies this tool as" in said[0]
    assert "not a port or parameter declaration" in said[0]


@pytest.mark.asyncio
async def test_only_direct_classifications_become_evidence():
    """An inherited term is true and is not something the source said about this tool.
    Sending it would put a claim nobody made in front of a model."""
    got = await _adapter().sync()
    fastqc = next(i for i in got.items if i.ref == "fastqc")
    quoted = " ".join(e.text for e in fastqc.evidence)
    assert "DIO:0000036" in quoted
    for inherited in ("DIO:0000010", "DIO:0000004", "DIO:0000001"):
        assert inherited not in quoted, f"{inherited} is inherited and was sent as evidence"


@pytest.mark.asyncio
async def test_no_locator_is_absolute_after_enrichment():
    got = await _adapter().sync()
    for item in got.items:
        for excerpt in item.evidence:
            assert not excerpt.locator.startswith("/"), excerpt.locator


# ── freshness ──────────────────────────────────────────────────────────────────────────


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


@pytest.mark.asyncio
async def test_a_change_to_a_tools_metadata_moves_its_digest():
    before = await _digests()
    edited = (FIXTURES / "pegi3s_metadata.json").read_text()
    edited = edited.replace(
        "A quality control tool for high throughput sequence data.",
        "A quality control tool. Now with more detail.",
    )
    after = await _digests(metadata=edited)
    assert before["fastqc"] != after["fastqc"]


@pytest.mark.asyncio
async def test_another_tools_metadata_change_leaves_this_one_alone():
    """§9's requirement, and the one that keeps the outdated count meaningful."""
    before = await _digests()
    edited = (FIXTURES / "pegi3s_metadata.json").read_text()
    edited = edited.replace(
        "General purpose multiple sequence alignment.",
        "General purpose multiple sequence alignment, rewritten.",
    )
    after = await _digests(metadata=edited)
    assert before["clustalw"] != after["clustalw"], "the fixture edit did nothing"
    assert before["fastqc"] == after["fastqc"], "an unrelated tool's metadata aged fastqc"
    assert before["seda"] == after["seda"]


@pytest.mark.asyncio
async def test_renaming_a_referenced_term_moves_the_digest_of_tools_that_show_it():
    """The breadcrumb those tools display has genuinely changed."""
    before = await _digests()
    edited = (FIXTURES / "pegi3s_dio.obo").read_text()
    edited = edited.replace("name: Quality", "name: Read quality")
    after = await _digests(obo=edited)
    assert before["fastqc"] != after["fastqc"]


@pytest.mark.asyncio
async def test_renaming_a_term_on_another_branch_ages_nothing_here():
    before = await _digests()
    edited = (FIXTURES / "pegi3s_dio.obo").read_text()
    edited = edited.replace("name: Editing", "name: Curation")
    after = await _digests(obo=edited)
    assert before["seda"] != after["seda"], "the fixture edit did nothing"
    assert before["fastqc"] == after["fastqc"], "an unrelated term aged fastqc"
    assert before["clustalw"] == after["clustalw"]


@pytest.mark.asyncio
async def test_the_digest_is_stable_across_two_identical_syncs():
    """Nothing here reads the repository HEAD, a timestamp or an HTTP header."""
    assert await _digests() == await _digests()


@pytest.mark.asyncio
async def test_an_unclassified_tool_still_has_a_digest_that_tracks_its_image():
    got = await _adapter().sync()
    prodigal = next(i for i in got.items if i.ref == "prodigal")
    assert prodigal.content_digest
