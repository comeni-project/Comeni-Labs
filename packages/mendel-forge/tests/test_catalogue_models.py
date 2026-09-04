"""The catalogue's records, and the arithmetic a source card rests on.

Every assertion here is about a number or a claim a person will read on a page and act on. The
plan's §1.3 exists because three of these totals were routinely conflated, so they are checked
rather than described.
"""

from datetime import UTC, datetime

import pytest
from mendel_forge.catalogue import (
    BundleFile,
    CatalogueItem,
    ContainerRef,
    Freshness,
    LandedSource,
    SourceCapabilities,
    SourceCounts,
    SourceSnapshot,
)
from pydantic import ValidationError

WHEN = datetime(2026, 9, 4, tzinfo=UTC)


def item(ref: str, digest: str = "d1", adaptable: bool = True, why: str | None = None):
    return CatalogueItem(
        id=f"id-{ref}",
        source="nf-core",
        ref=ref,
        display_name=ref,
        content_digest=digest,
        adaptable=adaptable,
        unsupported_reason=why,
    )


def snapshot(*items):
    return SourceSnapshot(
        source="nf-core", source_revision="abc123", synced_at=WHEN, items=items
    )


# ── an unsupported entry must say why, and a supported one must not pretend ────────────


def test_an_unsupported_entry_states_its_reason():
    got = item("weird", adaptable=False, why="no pullable linux image")
    assert got.freshness(None) is Freshness.UNSUPPORTED


def test_an_unsupported_entry_with_no_reason_is_refused():
    """§4.2 — show unsupported entries *and their reason*. A silent exclusion is how a
    catalogue starts lying about its own size."""
    with pytest.raises(ValidationError, match="say what is missing"):
        item("weird", adaptable=False)


def test_an_adaptable_entry_carrying_a_stale_reason_is_refused():
    """The other direction, and the quieter one: an obstacle that has been removed leaves a
    usable tool wearing an excuse nobody re-read."""
    with pytest.raises(ValidationError, match="carrying an unsupported reason"):
        item("fine", adaptable=True, why="no pullable linux image")


# ── freshness is digest equality, never a date ─────────────────────────────────────────


def test_an_unadapted_tool_is_unadapted():
    assert item("fastqc").freshness(None) is Freshness.UNADAPTED


def test_work_underway_is_in_progress_and_not_adapted():
    """Counting queued work as adapted makes the registry look more complete than it is,
    which is the one direction a progress figure must never err in."""
    assert item("fastqc").freshness(None, in_progress=True) is Freshness.IN_PROGRESS


def test_a_matching_digest_is_current():
    landed = LandedSource(source="nf-core", ref="fastqc", content_digest="d1")
    assert item("fastqc", digest="d1").freshness(landed) is Freshness.CURRENT


def test_a_moved_digest_is_outdated():
    landed = LandedSource(source="nf-core", ref="fastqc", content_digest="old")
    assert item("fastqc", digest="new").freshness(landed) is Freshness.OUTDATED


def test_an_unrelated_tree_change_does_not_age_a_module():
    """§1.3's rule, and the reason `content_digest` is per tool.

    Two tools land. An upstream commit changes only the second. The first must stay current —
    if freshness compared a repository revision, every adapted tool in the registry would go
    outdated at once and the outdated count would become noise nobody reads.
    """
    landed = {
        "fastqc": LandedSource(source="nf-core", ref="fastqc", content_digest="fastqc-v1"),
        "star/align": LandedSource(
            source="nf-core", ref="star/align", content_digest="star-v1"
        ),
    }
    # A new sync at a new repository revision; only star/align's content moved.
    after = snapshot(
        item("fastqc", digest="fastqc-v1"),
        item("star/align", digest="star-v2"),
    ).model_copy(update={"source_revision": "def456"})

    counts = after.counts(landed)
    assert counts.current == 1, "an unrelated commit aged a module whose content did not move"
    assert counts.outdated == 1


# ── the card's arithmetic ──────────────────────────────────────────────────────────────


def test_counts_are_derived_from_the_items():
    landed = {"a": LandedSource(source="nf-core", ref="a", content_digest="d1")}
    counts = snapshot(
        item("a", digest="d1"),
        item("b"),
        item("c"),
        item("d", adaptable=False, why="container only, no documentation"),
    ).counts(landed, in_progress=frozenset({"b"}))

    assert counts.discovered == 4
    assert counts.adaptable == 3
    assert counts.unsupported == 1
    assert counts.adapted == 1
    assert counts.current == 1
    assert counts.outdated == 0
    assert counts.in_progress == 1
    assert counts.unadapted == 1


def test_unsupported_sits_outside_the_denominator():
    """The bar's four segments sum to `adaptable`; unsupported is stated beneath it."""
    counts = snapshot(
        item("a"), item("b", adaptable=False, why="no image")
    ).counts()
    assert counts.adaptable == 1
    assert counts.unadapted == 1
    assert counts.discovered == 2


def test_a_card_whose_parts_exceed_its_whole_is_refused():
    """A bar drawn past its own end reaches a screenshot before it reaches a test."""
    with pytest.raises(ValidationError, match="exceeds adaptable"):
        SourceCounts(
            discovered=10,
            adaptable=10,
            unsupported=0,
            adapted=8,
            current=8,
            outdated=0,
            in_progress=5,
        )


def test_adapted_must_equal_current_plus_outdated():
    with pytest.raises(ValidationError, match="!= current"):
        SourceCounts(
            discovered=5,
            adaptable=5,
            unsupported=0,
            adapted=4,
            current=1,
            outdated=1,
            in_progress=0,
        )


def test_adaptable_plus_unsupported_must_equal_discovered():
    with pytest.raises(ValidationError, match="!= discovered"):
        SourceCounts(
            discovered=9,
            adaptable=5,
            unsupported=1,
            adapted=0,
            current=0,
            outdated=0,
            in_progress=0,
        )


# ── a snapshot is internally consistent ────────────────────────────────────────────────


def test_a_snapshot_refuses_items_from_another_source():
    other = item("x").model_copy(update={"source": "pegi3s"})
    with pytest.raises(ValidationError, match="carries items from"):
        snapshot(item("a"), other)


def test_a_snapshot_refuses_a_duplicated_ref():
    """Two rows for one tool double a total and give an adaptation two rows to point at."""
    with pytest.raises(ValidationError, match="more than once"):
        snapshot(item("a"), item("a"))


# ── a version is proved or it is null ──────────────────────────────────────────────────


def test_an_unproved_version_is_none_rather_than_latest():
    assert item("fastqc").latest_version is None


def test_a_container_needs_a_tag_or_a_digest():
    with pytest.raises(ValidationError, match="needs a tag or a digest"):
        ContainerRef(registry="docker.io", repository="pegi3s/fastqc")


def test_a_digest_wins_over_a_tag_when_pinning():
    """A tag is repointable; a digest is the only reference that makes a run reproducible."""
    ref = ContainerRef(
        registry="docker.io", repository="pegi3s/fastqc", tag="latest", digest="sha256:abc"
    )
    assert ref.pinned() == "docker.io/pegi3s/fastqc@sha256:abc"


def test_a_tag_is_used_when_there_is_no_digest():
    ref = ContainerRef(registry="docker.io", repository="pegi3s/fastqc", tag="1.2")
    assert ref.pinned() == "docker.io/pegi3s/fastqc:1.2"


# ── a bundle file cannot escape its root ───────────────────────────────────────────────


@pytest.mark.parametrize("path", ["/etc/passwd", "../outside.nf", "a/../../b.nf"])
def test_a_bundle_file_path_stays_inside(path: str):
    with pytest.raises(ValidationError, match="escapes the bundle root"):
        BundleFile(path=path, text="x")


def test_an_ordinary_nested_path_is_fine():
    assert BundleFile(path="module/main.nf", text="x").path == "module/main.nf"


# ── capabilities describe the adapter's reach ──────────────────────────────────────────


def test_capabilities_default_to_claiming_nothing():
    """The safe default. A source that has not said it supplies Nextflow must not be assumed
    to, or a scaffold will copy a process that does not exist."""
    blank = SourceCapabilities()
    assert not blank.supplies_nextflow
    assert not blank.supplies_structured_ports
    assert not blank.supplies_container_digest
    assert not blank.supplies_tests
