"""Caching what a source last said, against a real database.

The claims worth a database are the ones about *reconciliation*: what happens to a tool that
vanished upstream, what happens to `first_seen_at` on the second sync, and whether a failed
sync leaves the previous catalogue where it was. None of those can be checked by constructing
an object — they are about two syncs and the rows between them.
"""

import hashlib
from datetime import UTC, datetime, timedelta

import pytest
from mendel_api.db import session_scope
from mendel_api.models import ForgeCatalogueItem
from mendel_api.services import forge_catalogue, forge_state
from mendel_forge.catalogue import (
    CatalogueItem,
    Freshness,
    LandedSource,
    SourceSnapshot,
    SyncWarning,
)
from sqlalchemy import text


def _database_is_reachable() -> bool:
    try:
        with session_scope() as session:
            session.execute(text("SELECT 1"))
    except Exception:
        return False
    return True


pytestmark = pytest.mark.skipif(
    not _database_is_reachable(), reason="no database — run `docker compose up -d postgres`"
)


def _item(
    ref: str, *, digest: str = "a" * 64, adaptable: bool = True, summary: str = ""
) -> CatalogueItem:
    """`id` is `sha256(source + ref)`, which is what the adapters compute.

    **Written as a hash rather than a padded string, and that cost one failing test.** The first
    version padded the ref to 64 characters with zeros, which made `tool1` and `tool10`
    the same id — so a twelve-tool sync stored eleven rows and
    `test_search_reports_the_total_and_not_the_size_of_the_page` failed on the fixture rather
    than on the thing it was checking.
    """
    return CatalogueItem(
        id=hashlib.sha256(f"nf-core{ref}".encode()).hexdigest(),
        source="nf-core",
        ref=ref,
        display_name=ref,
        summary=summary,
        content_digest=digest,
        adaptable=adaptable,
        unsupported_reason="" if adaptable else "no container",
    )


def _snapshot(*items: CatalogueItem, revision: str = "abc123", **kwargs) -> SourceSnapshot:
    return SourceSnapshot(
        source="nf-core",
        source_revision=revision,
        synced_at=datetime.now(UTC),
        items=items,
        **kwargs,
    )


def test_a_sync_stores_every_item_it_read(clean_forge):
    forge_catalogue.record(_snapshot(_item("samtools/sort"), _item("fastqc")))
    found, total = forge_catalogue.search()
    assert total == 2
    assert {item.ref for item in found} == {"samtools/sort", "fastqc"}


def test_a_tool_that_vanished_upstream_keeps_its_row_and_stops_being_present(clean_forge):
    """**Absent, not deleted.** A tool removed from nf-core still has adaptations, revisions
    and events pointing at it, and a curated contract's provenance names it. Deleting the item
    would take all of that with it — which is why every foreign key is `RESTRICT` and why this
    is a flag rather than a `DELETE`.
    """
    forge_catalogue.record(_snapshot(_item("samtools/sort"), _item("fastqc")))
    forge_catalogue.record(_snapshot(_item("samtools/sort")))

    found, total = forge_catalogue.search()
    assert total == 1 and found[0].ref == "samtools/sort"
    with session_scope() as session:
        gone = session.query(ForgeCatalogueItem).filter_by(ref="fastqc").one()
        assert gone.present is False


def test_a_tool_that_came_back_is_present_again(clean_forge):
    """The reconciliation runs both ways. A tool that reappears — a module restored upstream,
    or a sync that read a truncated tree — must not stay hidden, and `present` is set on every
    upsert rather than only on insert."""
    forge_catalogue.record(_snapshot(_item("fastqc")))
    forge_catalogue.record(_snapshot(_item("samtools/sort")))
    forge_catalogue.record(_snapshot(_item("fastqc"), _item("samtools/sort")))
    assert forge_catalogue.search()[1] == 2


def test_a_second_sync_does_not_reset_when_a_tool_was_first_seen(clean_forge):
    """`first_seen_at` is the one column an upsert must not touch.

    Overwriting it makes every tool look newly discovered on every sync, which is precisely the
    number a *what is new upstream* page is reading. The defect is invisible in a single sync
    and invisible in any test that only ever runs one.
    """
    forge_catalogue.record(_snapshot(_item("fastqc")))
    with session_scope() as session:
        first = session.query(ForgeCatalogueItem).filter_by(ref="fastqc").one().first_seen_at

    forge_catalogue.record(_snapshot(_item("fastqc", digest="b" * 64)))
    with session_scope() as session:
        row = session.query(ForgeCatalogueItem).filter_by(ref="fastqc").one()
        assert row.first_seen_at == first
        assert row.last_seen_at > first
        assert row.content_digest == "b" * 64


def test_a_failed_sync_leaves_the_catalogue_alone_and_says_why(clean_forge):
    """§4.3 — a page shows *stale, and here is why* rather than zero tools.

    This is why `SourceSnapshot` in `mendel-forge` is only ever a success: a failure has a
    different shape, it produces no items, and a degraded snapshot would be indistinguishable
    from a source that genuinely shrank to nothing.
    """
    forge_catalogue.record(_snapshot(_item("fastqc"), _item("samtools/sort")))
    forge_catalogue.record_failure(
        "nf-core", error="MF0201 upstream answered 503", started_at=datetime.now(UTC)
    )

    assert forge_catalogue.search()[1] == 2
    latest = forge_catalogue.latest("nf-core")
    assert latest.ok is False
    assert "MF0201" in latest.error
    assert latest.last_successful_sync_id is not None


def test_the_first_failure_of_a_source_has_no_successful_sync_to_point_at(clean_forge):
    """The empty state the plan asks for by name: *no successful source sync*, not *0 tools*."""
    forge_catalogue.record_failure(
        "nf-core", error="MF0201 upstream answered 503", started_at=datetime.now(UTC)
    )
    assert forge_catalogue.latest("nf-core").last_successful_sync_id is None


def test_a_sync_keeps_the_warnings_it_could_not_use(clean_forge):
    """A sync that read 190 tools and could not classify two is a success with warnings, not a
    failure — `MF0205` and `MF0207` are exactly that shape, and dropping them here would make
    the adapter's care invisible to the page."""
    forge_catalogue.record(
        _snapshot(
            _item("fastqc"),
            warnings=(SyncWarning(code="MF0207", detail="unknown tool", subject="nosuchtool"),),
        )
    )
    stored = forge_catalogue.latest("nf-core")
    assert stored.ok is True
    assert stored.warnings[0]["code"] == "MF0207"


def test_search_reports_the_total_and_not_the_size_of_the_page(clean_forge):
    """A page that reports its own length as the total says "2 tools" about a source with
    twelve. That is `MF0202`'s failure mode — a number smaller than the truth, quietly —
    arriving through the front end instead of through the adapter."""
    forge_catalogue.record(_snapshot(*[_item(f"tool{n}") for n in range(12)]))
    found, total = forge_catalogue.search(limit=2)
    assert len(found) == 2
    assert total == 12


def test_search_matches_the_summary_as_well_as_the_name(clean_forge):
    """`summary` is denormalised out of the JSON document for exactly this: a curator looking
    for *quality* will not know the tool is called `fastqc`."""
    forge_catalogue.record(
        _snapshot(_item("fastqc", summary="Quality control for high throughput sequence data"))
    )
    assert forge_catalogue.search(query="quality")[1] == 1
    assert forge_catalogue.search(query="QUALITY")[1] == 1
    assert forge_catalogue.search(query="alignment")[1] == 0


def test_search_can_hide_what_cannot_be_adapted(clean_forge):
    forge_catalogue.record(_snapshot(_item("fastqc"), _item("broken", adaptable=False)))
    assert forge_catalogue.search()[1] == 2
    assert forge_catalogue.search(adaptable_only=True)[1] == 1


def test_the_card_counts_unadapted_tools_against_a_stated_denominator(clean_forge):
    """`SourceCounts` validates its own arithmetic, so a wrong card raises here rather than
    drawing a bar past its own end. What this checks is that the numbers handed to it come from
    three places — the catalogue, the workflow and the registry — and still add up."""
    forge_catalogue.record(_snapshot(_item("fastqc"), _item("broken", adaptable=False)))
    card = forge_catalogue.counts("nf-core", landed={})
    assert (card.discovered, card.adaptable, card.unsupported) == (2, 1, 1)
    assert card.unadapted == 1
    assert card.adapted == 0


def test_a_landed_tool_is_current_until_its_digest_moves(clean_forge):
    """**Digest equality, never a date.** A tool whose upstream description was reworded and
    whose module did not change must not read as outdated, and a tool whose module changed must
    not read as current because the registry file is newer."""
    forge_catalogue.record(_snapshot(_item("fastqc", digest="a" * 64)))
    landed = {"fastqc": LandedSource(source="nf-core", ref="fastqc", content_digest="a" * 64)}
    assert forge_catalogue.counts("nf-core", landed=landed).current == 1

    forge_catalogue.record(_snapshot(_item("fastqc", digest="b" * 64)))
    card = forge_catalogue.counts("nf-core", landed=landed)
    assert (card.current, card.outdated) == (0, 1)


def test_an_open_adaptation_makes_its_tool_in_progress(clean_forge):
    """The one count that comes from the workflow table rather than from the catalogue or the
    registry. Without it a tool somebody is actively working on reads as untouched, and two
    curators start it twice — which the partial index then refuses, at the worst moment."""
    forge_catalogue.record(_snapshot(_item("fastqc")))
    item_id = forge_catalogue.search()[0][0].id
    forge_state.begin(item_id, who="rafael")

    card = forge_catalogue.counts("nf-core", landed={})
    assert card.in_progress == 1
    assert card.unadapted == 0


def test_a_finished_adaptation_stops_being_in_progress(clean_forge):
    """`TERMINAL` is what "active" is defined against, in one place. A count that used its own
    idea of finished would disagree with the refusal in `forge_state.begin`, and the page would
    show a tool as busy that the server would happily let you start."""
    forge_catalogue.record(_snapshot(_item("fastqc")))
    item_id = forge_catalogue.search()[0][0].id
    adaptation = forge_state.begin(item_id, who="rafael")
    with session_scope() as session:
        from mendel_api.models import ForgeAdaptation

        session.get(ForgeAdaptation, adaptation).state = "archived"

    assert forge_catalogue.counts("nf-core", landed={}).in_progress == 0


def test_the_latest_sync_is_the_most_recent_attempt_not_the_most_recent_success(clean_forge):
    """*We tried twenty minutes ago and it failed* is the sentence that separates stale data
    from abandoned data, and a `latest` that only ever returned successes cannot say it."""
    old = datetime.now(UTC) - timedelta(hours=2)
    forge_catalogue.record(_snapshot(_item("fastqc")), started_at=old)
    forge_catalogue.record_failure("nf-core", error="MF0201", started_at=datetime.now(UTC))
    assert forge_catalogue.latest("nf-core").ok is False


# ── what has landed, and how a page filters on it ─────────────────────────────────────


def _publish(item_id: str, *, digest: str) -> None:
    """Put a tool in `published` carrying the source digest it was built from.

    Written against the columns rather than driven through the workflow because what is under
    test is the *reader*: `landed_of` and `_status_filter` both answer from `state` and
    `source_digest`, and walking six transitions to arrive at those two values would be testing
    the transitions again.
    """
    from mendel_api.models import ForgeAdaptation

    adaptation = forge_state.begin(item_id, who="rafael")
    with session_scope() as session:
        row = session.get(ForgeAdaptation, adaptation)
        row.state = "published"
        row.source_digest = digest


def test_what_landed_is_read_from_what_was_published(clean_forge):
    """**The registry cannot answer this and the forge can.** A contract's `Provenance` carries
    no source content digest, so *was it the current version that landed* is unanswerable from
    registry files — `ForgeAdaptation.source_digest` is the digest the adaptation was built
    from, and it is what makes current and outdated distinguishable at all."""
    forge_catalogue.record(_snapshot(_item("fastqc", digest="a" * 64)))
    _publish(forge_catalogue.search()[0][0].id, digest="a" * 64)

    assert forge_catalogue.landed_of("nf-core")["fastqc"].content_digest == "a" * 64


def test_counts_read_what_landed_rather_than_reporting_nothing_ever_did(clean_forge):
    """**The default was `{}` and it was structurally wrong.** Every source card's `current` and
    `outdated` were zero on every deployment, because the overview passed no mapping and the
    parameter defaulted to an empty one — so the two figures the completeness bar is built out
    of said *nothing has ever been adapted*, always."""
    forge_catalogue.record(_snapshot(_item("fastqc", digest="a" * 64)))
    _publish(forge_catalogue.search()[0][0].id, digest="a" * 64)

    assert forge_catalogue.counts("nf-core").current == 1
    # And it still yields to a caller who has a better answer.
    assert forge_catalogue.counts("nf-core", landed={}).current == 0


def test_a_published_tool_goes_outdated_when_upstream_moves(clean_forge):
    forge_catalogue.record(_snapshot(_item("fastqc", digest="a" * 64)))
    _publish(forge_catalogue.search()[0][0].id, digest="a" * 64)
    forge_catalogue.record(_snapshot(_item("fastqc", digest="b" * 64)))

    card = forge_catalogue.counts("nf-core")
    assert (card.current, card.outdated) == (0, 1)


def test_standing_names_the_adaptation_a_row_would_open(clean_forge):
    """A catalogue row offers *Adapt* or *Open*, and the second needs an id. Without it the
    page would ask the adaptations endpoint once per row — fifty requests for one screen."""
    forge_catalogue.record(_snapshot(_item("fastqc")))
    item = forge_catalogue.search()[0][0]
    adaptation = forge_state.begin(item.id, who="rafael")

    where = forge_catalogue.standing([item])[item.id]
    assert where.freshness is Freshness.IN_PROGRESS
    assert where.adaptation_id == adaptation


def test_standing_is_two_queries_whatever_the_page_size(clean_forge):
    """A page of fifty must not be fifty round trips. Asserted as *the whole page comes back*
    rather than by counting queries, because the count is an implementation detail and the
    thing that breaks is a row silently missing a standing."""
    forge_catalogue.record(_snapshot(*[_item(f"tool{n}") for n in range(12)]))
    items = forge_catalogue.search(limit=12)[0]
    assert set(forge_catalogue.standing(items)) == {item.id for item in items}


def test_standing_of_nothing_is_nothing(clean_forge):
    """The empty page. An `IN ()` over no ids is a query some backends refuse and all of them
    waste, and the caller has nothing to key on either way."""
    assert forge_catalogue.standing([]) == {}


def test_a_status_filter_is_a_query_and_not_a_walk_of_the_page(clean_forge):
    """**Filtering after paging reports eleven of sixteen hundred.** The total describes the
    whole catalogue and the rows describe what survived the page — and the next page skips
    whatever the first one dropped. Both numbers here come from the same WHERE clause."""
    forge_catalogue.record(
        _snapshot(
            _item("fastqc", digest="a" * 64),
            _item("samtools/sort", digest="b" * 64),
            _item("broken", adaptable=False),
        )
    )
    by_ref = {item.ref: item for item in forge_catalogue.search()[0]}
    _publish(by_ref["fastqc"].id, digest="a" * 64)
    forge_state.begin(by_ref["samtools/sort"].id, who="rafael")

    def refs(status: str) -> set[str]:
        found, total = forge_catalogue.search(status=status)
        assert total == len(found), f"{status}: the total and the page disagree"
        return {item.ref for item in found}

    assert refs("current") == {"fastqc"}
    assert refs("adapted") == {"fastqc"}
    assert refs("in_progress") == {"samtools/sort"}
    assert refs("unadapted") == set()
    assert refs("unsupported") == {"broken"}
    assert refs("outdated") == set()


def test_an_outdated_tool_is_adapted_and_not_current(clean_forge):
    """The one status that is a *pair* of facts: something landed, and it is not what upstream
    has now. A filter that read only the first would put it under `current`."""
    forge_catalogue.record(_snapshot(_item("fastqc", digest="a" * 64)))
    _publish(forge_catalogue.search()[0][0].id, digest="a" * 64)
    forge_catalogue.record(_snapshot(_item("fastqc", digest="b" * 64)))

    assert {item.ref for item in forge_catalogue.search(status="outdated")[0]} == {"fastqc"}
    assert forge_catalogue.search(status="current")[1] == 0
    assert forge_catalogue.search(status="adapted")[1] == 1


def test_every_freshness_is_a_filter_somebody_can_ask_for(clean_forge):
    """**The overview links one per segment**, so a `Freshness` member with no clause would be
    a number on the front door that goes nowhere. This is what makes a sixth member fail here
    rather than on the screen."""
    for freshness in Freshness:
        forge_catalogue.search(status=freshness.value)
    with pytest.raises(ValueError):
        forge_catalogue.search(status="invented")


def test_one_tool_is_found_past_the_first_page(clean_forge):
    """**The route used to scan the first two hundred rows and walk them**, so every tool past
    the two-hundredth answered 404 — invisible against a fixture catalogue of six and certain
    against a real one of sixteen hundred."""
    forge_catalogue.record(_snapshot(*[_item(f"tool{n}") for n in range(250)]))
    last = forge_catalogue.search(limit=1, offset=249)[0][0]

    assert forge_catalogue.one(last.id).ref == last.ref
    with pytest.raises(KeyError):
        forge_catalogue.one("no-such-tool")


def test_a_tool_that_vanished_upstream_is_not_found_by_id(clean_forge):
    """`present` is what a sync writes when a tool stops being published, and the row stays so
    an approved contract keeps its provenance. Serving it as though it were still on offer
    would put an *Adapt* button on a tool nobody can fetch."""
    forge_catalogue.record(_snapshot(_item("fastqc"), _item("gone")))
    gone = {item.ref: item for item in forge_catalogue.search()[0]}["gone"]
    forge_catalogue.record(_snapshot(_item("fastqc")))

    with pytest.raises(KeyError):
        forge_catalogue.one(gone.id)
