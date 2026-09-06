"""The nf-core adapter, against a recorded tree.

**Every count here is derived from the fixture, never written as a literal.** A test asserting
`len(items) == 3` passes when the fixture changes and the adapter breaks; one asserting it
equals the number of directories in the fixture holding both required files is checking the
adapter. That rule is the plan's, and `_expected_refs` is where it lives.
"""

import io
import json
import tarfile
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from mendel_forge.catalogue import CatalogueItem, LandedSource
from mendel_forge.sources.base import UpstreamError
from mendel_forge.sources.nfcore_catalogue import (
    OWNER,
    REPO,
    NfCoreAdapter,
    _Blob,
    _modules_in,
)

FIXTURES = Path(__file__).parent / "fixtures" / "sources"
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


# ── what counts as a module ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_the_discovered_set_is_exactly_what_the_fixture_declares():
    tree = _tree()
    got = await _adapter(_handler()).sync()
    assert {item.ref for item in got.items} == _expected_refs(tree)


@pytest.mark.asyncio
async def test_a_directory_with_only_main_nf_is_not_a_module():
    """A helper, not something anybody can route to."""
    got = await _adapter(_handler()).sync()
    assert "helperonly" not in {item.ref for item in got.items}


@pytest.mark.asyncio
async def test_a_directory_with_only_meta_yml_is_not_a_module():
    got = await _adapter(_handler()).sync()
    assert "metaonly" not in {item.ref for item in got.items}


@pytest.mark.asyncio
async def test_subworkflows_are_not_modules():
    """§1.3 names them explicitly. They live outside `modules/nf-core/` and carry both files,
    so only the path prefix keeps them out."""
    got = await _adapter(_handler()).sync()
    assert not any("bam_sort" in item.ref for item in got.items)


@pytest.mark.asyncio
async def test_a_nested_tool_is_one_module_per_leaf():
    """`samtools/sort` and `samtools/index` are two refs; `samtools` is not a module."""
    refs = {item.ref for item in (await _adapter(_handler()).sync()).items}
    assert "samtools/sort" in refs
    assert "samtools/index" in refs
    assert "samtools" not in refs


def test_a_tests_directory_belongs_to_its_module_rather_than_becoming_one():
    """`fastqc/tests/` holds `main.nf.test`, not `main.nf`, so it is not a module of its own —
    and its blobs belong to `fastqc` rather than falling out of the catalogue entirely.

    The second half is the defect this caught: grouping by immediate parent made `fastqc/tests`
    a separate group with neither required file, so it vanished, and the module shipped without
    the tests its declared capabilities promise.
    """
    modules = _modules_in(
        [
            _Blob(path=path, sha=sha)
            for path, sha in [
                ("modules/nf-core/fastqc/main.nf", "1"),
                ("modules/nf-core/fastqc/meta.yml", "2"),
                ("modules/nf-core/fastqc/tests/main.nf.test", "3"),
            ]
        ]
    )
    assert set(modules) == {"fastqc"}
    assert {b.path.rsplit("/", 1)[-1] for b in modules["fastqc"]} == {
        "main.nf",
        "meta.yml",
        "main.nf.test",
    }


@pytest.mark.asyncio
async def test_editing_a_modules_test_moves_its_digest():
    """The consequence of the fix above, stated rather than implied.

    nf-core ships tests as part of the module and this adapter claims them as a capability, so
    a changed test is changed module content and the tool reads as outdated.
    """
    before = await _adapter(_handler()).sync()

    # **The bytes change, and the sha follows them.** This used to edit the tree's declared
    # sha, which was the whole story while the sha came from the tree API. Content is now the
    # only input — `_blob_sha` derives the id git itself would give these bytes — so a test
    # that edited an id without editing the file would be asserting on nothing.
    changed = _handler(blobs={"b103fastqctest": "nextflow_process { CHANGED }\n"})

    after = await _adapter(changed).sync()
    was = {i.ref: i.content_digest for i in before.items}
    now = {i.ref: i.content_digest for i in after.items}
    assert was["fastqc"] != now["fastqc"], "a module's own test changed and its digest did not"
    assert was["samtools/sort"] == now["samtools/sort"]


# ── refusing a partial total ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_an_archive_with_no_modules_is_refused_rather_than_published():
    """**The truncation case is gone and this is what replaced it.**

    A recursive tree response is capped and had to be detected, walked around, and refused when
    even that failed — three mechanisms whose whole purpose was to avoid publishing a total
    shorter than the repository. An archive is the repository, so none of that can happen.

    What *can* still happen is an archive that holds nothing under `modules/nf-core/` — an
    upstream reorganisation, a wrong ref, a truncated download. That is indistinguishable from
    "the catalogue is empty" unless it refuses, and an empty catalogue is precisely the wrong
    answer this whole path is arranged to prevent: it would mark every adapted tool absent.
    """

    async def handle(request: httpx.Request) -> httpx.Response:
        if "/commits/" in str(request.url):
            return httpx.Response(200, json={"sha": COMMIT})
        return httpx.Response(200, content=_tarball({"README.md": "no modules here\n"}))

    with pytest.raises(UpstreamError, match="MF0200"):
        await _adapter(handle).sync()


# ── the digest is the module's own subtree ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_an_unrelated_module_changing_leaves_this_one_current():
    """The property §1.3 is built around, end to end through the adapter.

    A commit changes `samtools/sort`'s `main.nf` blob and nothing else. `fastqc` must keep its
    digest — comparing the repository HEAD instead would age every adapted tool in the registry
    on every upstream merge.
    """
    before = await _adapter(_handler()).sync()
    changed = _handler(
        blobs={"b200sortmain": "process SAMTOOLS_SORT { CHANGED }\n"},
        commit="bbbbbbbb" + COMMIT[8:],
    )

    after = await _adapter(changed).sync()
    digests_before = {item.ref: item.content_digest for item in before.items}
    digests_after = {item.ref: item.content_digest for item in after.items}

    assert digests_before["fastqc"] == digests_after["fastqc"], (
        "an unrelated module's change aged fastqc"
    )
    assert digests_before["samtools/sort"] != digests_after["samtools/sort"]
    assert before.source_revision != after.source_revision, "the fixture did not move the commit"


@pytest.mark.asyncio
async def test_freshness_follows_the_per_tool_digest():
    got = await _adapter(_handler()).sync()
    fastqc = next(i for i in got.items if i.ref == "fastqc")
    landed = LandedSource(
        source="nf-core", ref="fastqc", content_digest=fastqc.content_digest
    )
    assert fastqc.freshness(landed).value == "current"
    assert fastqc.freshness(landed.model_copy(update={"content_digest": "old"})).value == (
        "outdated"
    )


# ── metadata ───────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_metadata_comes_off_meta_yml():
    got = await _adapter(_handler()).sync()
    fastqc = next(i for i in got.items if i.ref == "fastqc")
    assert fastqc.display_name == "fastqc"
    assert fastqc.summary == "Run FastQC on sequenced reads"
    assert "quality control" in fastqc.keywords
    assert fastqc.licence == ("GPL-2.0-only",)
    assert fastqc.homepage_url.startswith("https://www.bioinformatics.babraham.ac.uk")


@pytest.mark.asyncio
async def test_a_multi_paragraph_tool_description_is_cut_to_one_line():
    """A catalogue row has one line, and a `tools:` description runs to several paragraphs."""
    got = await _adapter(_handler()).sync()
    sort = next(i for i in got.items if i.ref == "samtools/sort")
    assert "\n" not in sort.summary


@pytest.mark.asyncio
async def test_port_hints_are_read_and_the_groovy_map_is_not_one():
    """`meta` is on every port and is never the answer."""
    got = await _adapter(_handler()).sync()
    fastqc = next(i for i in got.items if i.ref == "fastqc")
    assert "reads" in fastqc.input_hints
    assert set(fastqc.output_hints) == {"html", "zip"}
    assert "meta" not in fastqc.input_hints
    assert "meta" not in fastqc.output_hints


@pytest.mark.asyncio
async def test_no_version_is_claimed():
    """nf-core's `meta.yml` states a homepage and a licence, not a version. The container tag
    lives in a Groovy ternary and is a tag rather than a proved release."""
    got = await _adapter(_handler()).sync()
    assert all(item.latest_version is None for item in got.items)


@pytest.mark.asyncio
async def test_a_module_with_unparseable_metadata_is_kept_not_dropped():
    """Dropping it would make the catalogue quietly smaller than the repository."""
    handler = _handler(blobs={"b101fastqcmeta": "name: fastqc\nname: fastqc\n"})
    got = await _adapter(handler).sync()
    assert "fastqc" in {item.ref for item in got.items}
    fastqc = next(i for i in got.items if i.ref == "fastqc")
    assert fastqc.summary == "", "a duplicate key parsed rather than being refused"


@pytest.mark.asyncio
async def test_every_module_claims_the_sources_capabilities():
    got = await _adapter(_handler()).sync()
    assert got.items, "the fixture produced nothing"
    for item in got.items:
        assert item.capabilities.supplies_nextflow
        assert item.capabilities.supplies_structured_ports
        assert not item.capabilities.supplies_container_digest, (
            "nf-core writes a container by tag; claiming a digest would pin what it cannot prove"
        )


@pytest.mark.asyncio
async def test_everything_is_adaptable():
    """A module with both required files always has a dossier — that is what the two files
    being required *means*."""
    got = await _adapter(_handler()).sync()
    assert all(item.adaptable for item in got.items)


# ── conditional sync ───────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_an_unmoved_commit_reuses_the_previous_snapshot():
    """The cheapest conditional request there is, and stronger than an ETag: it says the tree
    is the same tree rather than that the bytes are the same bytes."""
    first = await _adapter(_handler()).sync()

    requests: list[str] = []

    async def handle(request: httpx.Request) -> httpx.Response:
        requests.append(str(request.url))
        if "/commits/" in request.url.path:
            return httpx.Response(200, json={"sha": COMMIT})
        raise AssertionError(f"an unmoved commit still fetched {request.url}")

    again = await _adapter(handle).sync(previous=first)
    assert {i.ref for i in again.items} == {i.ref for i in first.items}
    assert len(requests) == 1, "an unmoved commit re-read the tree"


# ── the bundle ─────────────────────────────────────────────────────────────────────────


def _item(ref: str, snapshot) -> CatalogueItem:
    return next(i for i in snapshot.items if i.ref == ref)


@pytest.mark.asyncio
async def test_a_bundle_carries_the_module_directory_with_paths_relative_to_it():
    snapshot = await _adapter(_handler()).sync()
    bundle = await _adapter(_handler()).bundle(_item("fastqc", snapshot))
    paths = {f.path for f in bundle.files}
    assert "main.nf" in paths
    assert "meta.yml" in paths
    assert not any(p.startswith("modules/") for p in paths), (
        "a bundle path carries the upstream prefix, so it would land in the wrong place"
    )


@pytest.mark.asyncio
async def test_every_bundled_file_is_verbatim():
    """The strongest property this source has: nf-core wrote the process, so nothing
    downstream may author one. A validation rung compares against these digests."""
    snapshot = await _adapter(_handler()).sync()
    bundle = await _adapter(_handler()).bundle(_item("fastqc", snapshot))
    assert bundle.files
    assert all(f.verbatim for f in bundle.files)
    assert all(f.digest for f in bundle.files)


@pytest.mark.asyncio
async def test_a_bundle_includes_the_test_directory():
    """`supplies_tests` is claimed, so the tests have to actually arrive."""
    snapshot = await _adapter(_handler()).sync()
    bundle = await _adapter(_handler()).bundle(_item("fastqc", snapshot))
    assert any(f.path.startswith("tests/") for f in bundle.files)


@pytest.mark.asyncio
async def test_bundle_evidence_reads_description_first_then_ports():
    """`number()` assigns E001 upward in the order given, and a dossier reads better with the
    description before the ports it describes."""
    snapshot = await _adapter(_handler()).sync()
    bundle = await _adapter(_handler()).bundle(_item("fastqc", snapshot))
    assert bundle.evidence
    assert bundle.evidence[0].id == "E001"
    assert "FastQC" in bundle.evidence[0].excerpt.text
    kinds = [e.kind for e in bundle.evidence]
    assert kinds[-1] == "source", "main.nf should be the last excerpt, after the metadata"


@pytest.mark.asyncio
async def test_the_include_path_is_derived_and_cites_nothing():
    """A derived value with a citation would be a false one — nothing was read from a line."""
    snapshot = await _adapter(_handler()).sync()
    bundle = await _adapter(_handler()).bundle(_item("fastqc", snapshot))
    include = next(f for f in bundle.facts if f.name == "nf_include")
    assert include.value == "modules/nf-core/fastqc/main"
    assert include.evidence_id is None


@pytest.mark.asyncio
async def test_bundling_something_the_revision_lost_refuses_clearly():
    snapshot = await _adapter(_handler()).sync()
    stale = _item("fastqc", snapshot).model_copy(update={"ref": "gone"})
    with pytest.raises(UpstreamError, match="re-sync"):
        await _adapter(_handler()).bundle(stale)


@pytest.mark.asyncio
async def test_the_bundle_digest_is_stable_across_two_fetches():
    snapshot = await _adapter(_handler()).sync()
    item = _item("fastqc", snapshot)
    one = await _adapter(_handler()).bundle(item)
    two = await _adapter(_handler()).bundle(item)
    assert one.source_digest == two.source_digest


# ── the observation adapter ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_observe_produces_the_pre_existing_shape():
    adapter = _adapter(_handler())
    snapshot = await adapter.sync()
    bundle = await _adapter(_handler()).bundle(_item("fastqc", snapshot))
    observation = adapter.observe(bundle)
    assert observation.source == "nf-core"
    assert observation.ref_id == "nf-core:fastqc"
    assert observation.fact("nf_include") == "modules/nf-core/fastqc/main"
    assert observation.prose, "no prose reached the observation"


@pytest.mark.asyncio
async def test_no_locator_is_an_absolute_host_path():
    """A locator has to name something a reviewer on another machine can open."""
    snapshot = await _adapter(_handler()).sync()
    bundle = await _adapter(_handler()).bundle(_item("fastqc", snapshot))
    for numbered in bundle.evidence:
        assert not numbered.excerpt.locator.startswith("/"), numbered.excerpt.locator
    for item in snapshot.items:
        for excerpt in item.evidence:
            assert not excerpt.locator.startswith("/"), excerpt.locator
