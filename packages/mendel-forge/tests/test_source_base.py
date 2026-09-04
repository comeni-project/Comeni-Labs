"""The half of a source adapter that every source shares.

**Two fake subclasses, deliberately unalike.** `Rich` supplies Nextflow, structured ports and a
container digest; `Thin` supplies a container and prose and nothing else. A protocol with one
implementation is a protocol designed against imagination — the same argument
`sources/__init__.py` already makes — and the two shapes here are nf-core's and PEGiS's without
either adapter's detail.

Every test injects a transport. Nothing reaches the network, which is acceptance criterion 17.
"""

from datetime import UTC, datetime

import httpx
import pytest
from mendel_forge.catalogue import (
    BundleFact,
    BundleFile,
    CatalogueItem,
    ContainerRef,
    SourceCapabilities,
    SourceSnapshot,
)
from mendel_forge.sources.base import (
    BaseSourceAdapter,
    RawBundle,
    RawCatalogue,
    RawEvidence,
    RawItem,
    UpstreamError,
    digest_of,
    item_id,
    number,
)
from pydantic import ValidationError

WHEN = datetime(2026, 9, 4, tzinfo=UTC)

RICH = SourceCapabilities(
    supplies_nextflow=True,
    supplies_structured_ports=True,
    supplies_container_digest=True,
    supplies_tests=True,
)
THIN = SourceCapabilities(supplies_container_digest=True)


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


class Rich(BaseSourceAdapter):
    """A source that ships its own Nextflow and structured metadata."""

    name = "rich"
    capabilities = RICH

    def __init__(self, client, *, catalogue=None, bundle=None, now=WHEN):
        super().__init__(client, now=now)
        self._catalogue = catalogue
        self._bundle = bundle

    async def _fetch_catalogue(self, previous):
        return self._catalogue

    async def _fetch_bundle(self, item):
        return self._bundle


class Thin(BaseSourceAdapter):
    """A container-only source: an image and some prose, and every port a hole."""

    name = "thin"
    capabilities = THIN

    def __init__(self, client, *, catalogue=None, bundle=None, now=WHEN):
        super().__init__(client, now=now)
        self._catalogue = catalogue
        self._bundle = bundle

    async def _fetch_catalogue(self, previous):
        return self._catalogue

    async def _fetch_bundle(self, item):
        return self._bundle


def raw(ref: str, digest: str = "d1", **kw) -> RawItem:
    return RawItem(ref=ref, content_digest=digest, **kw)


def catalogue(*items, revision="rev1", **kw) -> RawCatalogue:
    return RawCatalogue(source_revision=revision, items=items, **kw)


async def _ok(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json={"ok": True})


# ── the two subclasses really are different ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_two_sources_with_different_capabilities_share_the_base():
    async with _client(_ok) as client:
        rich = await Rich(client, catalogue=catalogue(raw("a", capabilities=RICH))).sync()
        thin = await Thin(client, catalogue=catalogue(raw("b", capabilities=THIN))).sync()

    assert rich.items[0].capabilities.supplies_nextflow
    assert not thin.items[0].capabilities.supplies_nextflow
    assert thin.items[0].capabilities.supplies_container_digest
    assert rich.source == "rich" and thin.source == "thin"


@pytest.mark.asyncio
async def test_the_item_id_is_derived_and_differs_by_source():
    """Opaque, stable, and not a path. Two sources naming the same tool are two rows."""
    async with _client(_ok) as client:
        rich = await Rich(client, catalogue=catalogue(raw("fastqc"))).sync()
        thin = await Thin(client, catalogue=catalogue(raw("fastqc"))).sync()

    assert rich.items[0].id == item_id("rich", "fastqc")
    assert rich.items[0].id != thin.items[0].id


@pytest.mark.asyncio
async def test_an_adapter_cannot_choose_its_own_item_id():
    """`RawItem` has no `id` field at all, so the base is the only thing that can set one."""
    assert "id" not in RawItem.model_fields


# ── refusing beats under-reporting ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_an_incomplete_catalogue_is_refused():
    """A partial list produces a plausible total that is wrong, a bar with a wrong
    denominator, and an "up to date" claim about tools the sync never saw."""
    async with _client(_ok) as client:
        with pytest.raises(UpstreamError, match="MF0200"):
            await Rich(client, catalogue=catalogue(raw("a"), complete=False)).sync()


@pytest.mark.asyncio
async def test_an_incomplete_catalogue_says_how_much_it_saw():
    async with _client(_ok) as client:
        with pytest.raises(UpstreamError) as raised:
            await Rich(
                client, catalogue=catalogue(raw("a"), raw("b"), complete=False)
            ).sync()
    assert "2 item(s) read" in str(raised.value)


@pytest.mark.asyncio
async def test_an_empty_catalogue_is_not_an_error():
    """A source can legitimately list nothing. It is *incomplete* that refuses, not *empty*."""
    async with _client(_ok) as client:
        got = await Rich(client, catalogue=catalogue()).sync()
    assert got.items == ()


# ── unchanged and empty are opposite facts with identical shapes ───────────────────────


@pytest.mark.asyncio
async def test_a_304_reuses_the_previous_snapshot():
    async with _client(_ok) as client:
        first = await Rich(client, catalogue=catalogue(raw("a"), raw("b"))).sync()
        later = datetime(2026, 9, 5, tzinfo=UTC)
        again = await Rich(
            client,
            catalogue=catalogue(unchanged=True, etag='W/"same"', revision="rev1"),
            now=later,
        ).sync(previous=first)

    assert [i.ref for i in again.items] == ["a", "b"], "a 304 emptied the catalogue"
    assert again.synced_at == later, "a reused snapshot must still record when it was checked"
    assert again.etag == 'W/"same"'


@pytest.mark.asyncio
async def test_a_304_with_nothing_to_reuse_is_refused():
    """Treating it as empty would report zero tools and mark every adapted tool as gone."""
    async with _client(_ok) as client:
        with pytest.raises(UpstreamError, match="MF0203"):
            await Rich(client, catalogue=catalogue(unchanged=True)).sync(previous=None)


# ── ordering and stability ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_items_are_sorted_by_ref_whatever_order_the_source_gave():
    async with _client(_ok) as client:
        got = await Rich(client, catalogue=catalogue(raw("z"), raw("a"), raw("m"))).sync()
    assert [i.ref for i in got.items] == ["a", "m", "z"]


@pytest.mark.asyncio
async def test_the_same_catalogue_twice_gives_the_same_items():
    """A snapshot that differed between two identical syncs would make every digest and every
    freshness comparison meaningless."""
    async with _client(_ok) as client:
        first = await Rich(client, catalogue=catalogue(raw("a"), raw("b"))).sync()
        second = await Rich(client, catalogue=catalogue(raw("b"), raw("a"))).sync()
    assert first.items == second.items


# ── evidence numbering ─────────────────────────────────────────────────────────────────


def test_evidence_is_numbered_in_the_order_given():
    """An adapter assembles evidence in a reading order that means something — a description
    before its ports — and re-sorting would scatter it."""
    got = number(
        [
            RawEvidence(locator="meta.yml:description", text="reads QC"),
            RawEvidence(locator="meta.yml:input.reads", text="the FASTQs"),
        ]
    )
    assert [e.id for e in got] == ["E001", "E002"]
    assert got[0].excerpt.text == "reads QC"


def test_evidence_ids_are_stable_across_syncs():
    """The property a stored citation depends on: `E014` must point at the same text a
    reviewer read, so an adapter emitting a stable order gets stable ids."""
    entries = [
        RawEvidence(locator="a", text="one"),
        RawEvidence(locator="b", text="two"),
        RawEvidence(locator="c", text="three"),
    ]
    assert [e.id for e in number(entries)] == [e.id for e in number(entries)]


def test_numbering_pads_to_three_digits():
    """`E9` and `E10` sort wrongly everywhere a reader meets them."""
    assert number([RawEvidence(locator="x", text="y")] * 1)[0].id == "E001"


# ── digests ────────────────────────────────────────────────────────────────────────────


def test_digest_parts_cannot_be_confused_by_concatenation():
    """`("ab", "c")` and `("a", "bc")` are different inputs and must not collide."""
    assert digest_of("ab", "c") != digest_of("a", "bc")


def test_digest_is_stable():
    assert digest_of("a", "b") == digest_of("a", "b")


# ── bundles ────────────────────────────────────────────────────────────────────────────


def _item(ref="a", source="rich"):
    return CatalogueItem(
        id=item_id(source, ref),
        source=source,
        ref=ref,
        display_name=ref,
        content_digest="d1",
        source_revision="rev1",
    )


@pytest.mark.asyncio
async def test_a_bundle_digests_its_files_and_sorts_them():
    bundle = RawBundle(
        source_revision="rev2",
        files=(
            BundleFile(path="module/main.nf", text="process A {}"),
            BundleFile(path="module/meta.yml", text="name: a"),
        ),
    )
    async with _client(_ok) as client:
        got = await Rich(client, bundle=bundle).bundle(_item())

    assert [f.path for f in got.files] == ["module/main.nf", "module/meta.yml"]
    assert all(f.digest for f in got.files)
    assert got.item.source_revision == "rev2", "the bundle's revision is the fetched one"


@pytest.mark.asyncio
async def test_the_source_digest_moves_when_a_file_moves():
    async with _client(_ok) as client:
        one = await Rich(
            client,
            bundle=RawBundle(
                source_revision="r", files=(BundleFile(path="a.nf", text="one"),)
            ),
        ).bundle(_item())
        two = await Rich(
            client,
            bundle=RawBundle(
                source_revision="r", files=(BundleFile(path="a.nf", text="two"),)
            ),
        ).bundle(_item())
    assert one.source_digest != two.source_digest


@pytest.mark.asyncio
async def test_a_fact_citing_missing_evidence_is_refused():
    """A citation a reviewer cannot follow is worse than no citation — they cannot tell a
    broken pointer from a fabricated one."""
    bundle = RawBundle(
        source_revision="r",
        evidence=(RawEvidence(locator="a", text="one"),),
        facts=(BundleFact(name="process", value="FASTQC", evidence_id="E014"),),
    )
    async with _client(_ok) as client:
        with pytest.raises(UpstreamError, match="MF0204"):
            await Rich(client, bundle=bundle).bundle(_item())


@pytest.mark.asyncio
async def test_a_derived_fact_needs_no_evidence_id():
    bundle = RawBundle(
        source_revision="r",
        facts=(BundleFact(name="nf_include", value="modules/x/main"),),
    )
    async with _client(_ok) as client:
        got = await Rich(client, bundle=bundle).bundle(_item())
    assert got.facts[0].evidence_id is None


# ── observe(): the adapter into the pre-existing Observation shape ─────────────────────


@pytest.mark.asyncio
async def test_observe_carries_the_cited_excerpt():
    bundle = RawBundle(
        source_revision="r",
        evidence=(RawEvidence(locator="main.nf:3", text="process FASTQC {", kind="source"),),
        facts=(BundleFact(name="process", value="FASTQC", evidence_id="E001"),),
    )
    async with _client(_ok) as client:
        adapter = Rich(client, bundle=bundle)
        observation = adapter.observe(await adapter.bundle(_item()))

    assert observation.fact("process") == "FASTQC"
    assert observation.facts["process"].evidence.locator == "main.nf:3"
    assert observation.facts["process"].evidence.text == "process FASTQC {"


@pytest.mark.asyncio
async def test_observe_says_a_derived_fact_was_not_quoted():
    """Never a fabricated quotation. The absence has to be legible rather than disguised."""
    bundle = RawBundle(
        source_revision="r",
        evidence=(RawEvidence(locator="main.nf:3", text="process FASTQC {"),),
        facts=(BundleFact(name="nf_include", value="modules/x/main"),),
    )
    async with _client(_ok) as client:
        adapter = Rich(client, bundle=bundle)
        observation = adapter.observe(await adapter.bundle(_item()))

    cited = observation.facts["nf_include"].evidence
    assert "not quoted" in cited.text
    assert cited.text != "process FASTQC {", "a derived fact borrowed an unrelated excerpt"


@pytest.mark.asyncio
async def test_observe_passes_prose_through_and_leaves_other_kinds_out():
    """`prose` is what a model reads for meaning; a container digest is not prose."""
    bundle = RawBundle(
        source_revision="r",
        evidence=(
            RawEvidence(locator="meta.yml:description", text="QCs reads", kind="prose"),
            RawEvidence(locator="manifest", text="sha256:abc", kind="container"),
        ),
    )
    async with _client(_ok) as client:
        adapter = Rich(client, bundle=bundle)
        observation = adapter.observe(await adapter.bundle(_item()))

    assert [e.text for e in observation.prose] == ["QCs reads"]


# ── HTTP: retries, and the statuses that will never change ─────────────────────────────


@pytest.mark.asyncio
async def test_a_transient_status_is_retried_and_then_succeeds(monkeypatch):
    seen: list[int] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        seen.append(1)
        if len(seen) < 3:
            return httpx.Response(503)
        return httpx.Response(200, json={"ok": True})

    async with _client(handler) as client:
        adapter = Rich(client)
        monkeypatch.setattr(adapter, "_sleep", _no_sleep)
        response = await adapter.get("https://example.test/x")

    assert response.status_code == 200
    assert len(seen) == 3


@pytest.mark.asyncio
async def test_a_404_is_not_retried(monkeypatch):
    """Retrying an answer that will never change turns one clear failure into three slow
    ones."""
    seen: list[int] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        seen.append(1)
        return httpx.Response(404)

    async with _client(handler) as client:
        adapter = Rich(client)
        monkeypatch.setattr(adapter, "_sleep", _no_sleep)
        with pytest.raises(UpstreamError, match="MF0201"):
            await adapter.get("https://example.test/x")

    assert len(seen) == 1, "a 404 was retried"


@pytest.mark.asyncio
async def test_a_403_is_not_retried_and_suggests_a_token(monkeypatch):
    """A 403 with no `Retry-After` is far more often a token problem than a rate limit."""
    seen: list[int] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        seen.append(1)
        return httpx.Response(403)

    async with _client(handler) as client:
        adapter = Rich(client)
        monkeypatch.setattr(adapter, "_sleep", _no_sleep)
        with pytest.raises(UpstreamError) as raised:
            await adapter.get("https://example.test/x")

    assert len(seen) == 1
    assert "token" in str(raised.value)


@pytest.mark.asyncio
async def test_a_persistent_transient_status_eventually_refuses(monkeypatch):
    seen: list[int] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        seen.append(1)
        return httpx.Response(503)

    async with _client(handler) as client:
        adapter = Rich(client)
        monkeypatch.setattr(adapter, "_sleep", _no_sleep)
        with pytest.raises(UpstreamError, match="MF0201"):
            await adapter.get("https://example.test/x")

    assert len(seen) == 4, "the attempt budget is not being honoured"


@pytest.mark.asyncio
async def test_a_transport_failure_is_retried_then_reported_with_its_cause(monkeypatch):
    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route to host")

    async with _client(handler) as client:
        adapter = Rich(client)
        monkeypatch.setattr(adapter, "_sleep", _no_sleep)
        with pytest.raises(UpstreamError) as raised:
            await adapter.get("https://example.test/x")

    assert "MF0202" in str(raised.value)
    assert "no route to host" in str(raised.value), (
        "the original transport error was swallowed — the MA0007 lesson, one package over"
    )


@pytest.mark.asyncio
async def test_retry_after_is_honoured_over_the_computed_backoff(monkeypatch):
    """Guessing a backoff against a server that has just said how long to wait is how a client
    earns a longer ban."""
    waited: list[float] = []
    seen: list[int] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        seen.append(1)
        if len(seen) == 1:
            return httpx.Response(429, headers={"Retry-After": "3"})
        return httpx.Response(200, json={})

    async def record(seconds: float) -> None:
        waited.append(seconds)

    async with _client(handler) as client:
        adapter = Rich(client)
        monkeypatch.setattr(adapter, "_sleep", record)
        await adapter.get("https://example.test/x")

    assert waited == [3.0]


@pytest.mark.asyncio
async def test_an_absurd_retry_after_is_capped(monkeypatch):
    """A source asking for an hour must not hang a worker for an hour."""
    waited: list[float] = []
    seen: list[int] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        seen.append(1)
        if len(seen) == 1:
            return httpx.Response(429, headers={"Retry-After": "3600"})
        return httpx.Response(200, json={})

    async def record(seconds: float) -> None:
        waited.append(seconds)

    async with _client(handler) as client:
        adapter = Rich(client)
        monkeypatch.setattr(adapter, "_sleep", record)
        await adapter.get("https://example.test/x")

    assert waited[0] <= 32.0


@pytest.mark.asyncio
async def test_an_etag_is_sent_as_a_conditional_request():
    seen: dict[str, str] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        seen.update(request.headers)
        return httpx.Response(304)

    async with _client(handler) as client:
        response = await Rich(client).get(
            "https://example.test/x", etag='W/"abc"', accept_304=True
        )

    assert seen["if-none-match"] == 'W/"abc"'
    assert response.status_code == 304


@pytest.mark.asyncio
async def test_a_304_is_an_error_unless_the_caller_asked_for_it():
    """A caller that did not send a validator and gets a 304 has met a confused server, and
    treating the empty body as content is how an empty catalogue gets published."""

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(304)

    async with _client(handler) as client:
        with pytest.raises(UpstreamError):
            await Rich(client).get("https://example.test/x")


# ── pagination ─────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_pagination_follows_next_to_the_end():
    pages = {
        "https://example.test/list?page_size=100": {
            "results": [{"name": "a"}],
            "next": "https://example.test/list?page=2",
        },
        "https://example.test/list?page=2": {"results": [{"name": "b"}], "next": None},
    }

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=pages[str(request.url)])

    async with _client(handler) as client:
        got = await Rich(client).paginate("https://example.test/list")

    assert [entry["name"] for entry in got] == ["a", "b"]


@pytest.mark.asyncio
async def test_pagination_refuses_rather_than_stopping_early():
    """The circuit breaker raises rather than returning what it collected. A truncated list
    that looks complete is exactly the failure `complete` exists to prevent."""

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"results": [{"n": 1}], "next": "https://example.test/again"}
        )

    async with _client(handler) as client:
        with pytest.raises(UpstreamError, match="MF0200"):
            await Rich(client).paginate("https://example.test/list", limit=3)


@pytest.mark.asyncio
async def test_pagination_appends_its_page_size_without_breaking_a_query():
    seen: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return httpx.Response(200, json={"results": [], "next": None})

    async with _client(handler) as client:
        await Rich(client).paginate("https://example.test/list?q=x")

    assert seen == ["https://example.test/list?q=x&page_size=100"]


# ── the snapshot's clock ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_the_sync_time_is_recorded():
    async with _client(_ok) as client:
        got = await Rich(client, catalogue=catalogue(raw("a"))).sync()
    assert got.synced_at == WHEN


@pytest.mark.asyncio
async def test_a_real_clock_is_read_at_sync_time_not_at_construction():
    """Freezing it in the constructor would date every future sync to process start."""
    async with _client(_ok) as client:
        adapter = Rich(client, catalogue=catalogue(raw("a")), now=None)
        first = await adapter.sync()
        second = await adapter.sync()
    assert first.synced_at <= second.synced_at
    assert first.synced_at.tzinfo is not None, "a naive timestamp cannot be compared across hosts"


async def _no_sleep(seconds: float) -> None:
    return None


def test_a_snapshot_is_frozen():
    """A record of what a source said at a revision. Mutating one would make the digests
    beside it describe something else."""
    snapshot = SourceSnapshot(
        source="rich", source_revision="r", synced_at=WHEN, items=(_item(),)
    )
    with pytest.raises(ValidationError):
        snapshot.source = "other"


def test_a_container_ref_survives_normalisation():
    ref = ContainerRef(registry="docker.io", repository="x/y", digest="sha256:a")
    assert raw("a", container_refs=(ref,)).container_refs == (ref,)
